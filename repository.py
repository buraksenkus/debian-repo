import os
import socketserver
import subprocess
from common import execute_cmd
from datetime import datetime
from http.server import SimpleHTTPRequestHandler
from threading import Event, Thread
from typing import Dict

stop_threads = Event()


def do_hash(hash_name, hash_cmd, dist_path):
    hashes = []
    for root, _, files in os.walk(dist_path):
        for f in files:
            filepath = os.path.join(root, f)
            if f != "Release":
                filehash = subprocess.getoutput(f"{hash_cmd} {filepath}").split()[0]
                filesize = os.path.getsize(filepath)
                hashes.append(f" {filehash} {filesize} {os.path.relpath(filepath, dist_path)}")
    return "\n".join([f"{hash_name}:"] + hashes)


class DebianRepository:
    def __init__(self, config: Dict, dir: str, no_watch = True) -> None:
        self.conf = config
        self.dir = dir
        self.no_watch = no_watch
    
    @property
    def port(self):
        return int(self.conf["port"])
        
    @property
    def root_dir(self):
        return os.path.dirname(self.dir)
        
    @property
    def dists(self):
        return self.conf["dists"]

    @property
    def keyring_dir(self):
        return os.path.join(self.root_dir, "keyring")
    
    @property
    def dists_dir(self):
        return os.path.join(self.dir, "debian/dists")
    
    @property
    def gpg_key_ok(self):
        '''Checks if GPG key exists.'''
        if os.path.exists(self.keyring_dir):
            keys = execute_cmd(f'gpg --list-keys', env={'GNUPGHOME': self.keyring_dir})[0].decode('utf-8')
            return self.conf["email"] in keys
        return False
    
    def create_pool_directories(self):
        for dist in self.dists:
            dist_pool_path = os.path.join(self.dists_dir, dist, "pool")    
            os.makedirs(dist_pool_path, exist_ok=True)
            
    def __generate_release__(self, dist, key_id):
        date = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
        md5sums = do_hash("MD5Sum", "md5sum", os.path.join(self.dists_dir, dist))
        sha1sums = do_hash("SHA1", "sha1sum", os.path.join(self.dists_dir, dist))
        sha256sums = do_hash("SHA256", "sha256sum", os.path.join(self.dists_dir, dist))
        return f"""Origin: {self.conf['description']}
Suite: {dist}
Codename: {dist}
Version: 1.0
Architectures: {" ".join(self.conf["architectures"])}
Components: stable
Description: {self.conf['description']}
Date: {date}
SignWith: {key_id}
{md5sums}
{sha1sums}
{sha256sums}"""
        
    def start(self):
        '''Starts HTTP server and package pool watching. Generates GPG key automatically if it doesn't exist.'''
        self.create_pool_directories()
        os.chdir(self.dir)
        
        if not self.gpg_key_ok:
            self.generate_gpg()
            
        self.__generate_connection_guide__()
        self.update()

        with socketserver.TCPServer(("", self.port), SimpleHTTPRequestHandler) as httpd:
            print(f"Serving directory '{self.dir}' on port {self.port} ...")
            try:
                if not self.no_watch:
                    watch_thread = Thread(target=self.watch_pools)
                    watch_thread.start()
            
                httpd.serve_forever()
            except KeyboardInterrupt:
                print(f"Requested termination.")
                stop_threads.set()
                httpd.shutdown()
                httpd.server_close()
            except Exception as e:
                print(f"Error: {e}")
                stop_threads.set()
                httpd.shutdown()
                httpd.server_close()
                
    def generate_gpg(self):
        '''Generates GPS key for signing repository.'''
        os.makedirs(self.dir, exist_ok=True)

        if not self.gpg_key_ok:
            print("Generating GPG key...")
            os.makedirs(self.keyring_dir, mode=0o700, exist_ok=True)

            cmd_input = "\n".join([
                "Key-Type: RSA",
                "Key-Length: 4096",
                "Expire-Date: 0",
                f"Name-Real: {self.conf['name']}",
                f"Name-Email: {self.conf['email']}",
                "%no-protection"
            ])

            out, err, rc = execute_cmd(f'gpgconf --kill gpg-agent && echo "{cmd_input}" | gpg --full-gen-key --batch --yes', env={'GNUPGHOME': self.keyring_dir})
            
            if "fail" in err.decode("utf-8"):
                raise Exception(err.decode("utf-8"))
            
            out, err, rc = execute_cmd(f'gpg --armor --export {self.conf["email"]} > {os.path.join(self.dir, "publickey.gpg")}', env={'GNUPGHOME': self.keyring_dir})

            if not self.gpg_key_ok:
                raise Exception("Couldn't generate GPG key!")

        else:
            print(f"Already exists. If you want to create a new key, run 'rm -r {self.keyring_dir}'")
            
    def update(self):
        if not self.gpg_key_ok:
            self.generate_gpg()

        out, err, rc = execute_cmd(f"gpg --list-keys --with-colons | grep '^pub' | cut -d: -f5", env={'GNUPGHOME': self.keyring_dir})

        key_id = out.decode("utf-8").strip()
        
        for dist in os.listdir(self.dists_dir):
            for arch in self.conf["architectures"]:
                current_dist = os.path.join(self.dists_dir, dist)
                pool_path = os.path.join(current_dist, "pool", "stable", arch)
                packages_path = os.path.join(current_dist, "stable", f"binary-{arch}")
                os.makedirs(packages_path, exist_ok=True)
                os.makedirs(pool_path, exist_ok=True)
                
                packages_file_path = os.path.join(packages_path, 'Packages')
                packages_gz_file_path = os.path.join(packages_path, 'Packages.gz')
                
                out, err, rc = execute_cmd(f"dpkg-scanpackages -m --arch {arch} {pool_path} > {packages_file_path}", env={'GNUPGHOME': self.keyring_dir})
                out, err, rc = execute_cmd(f"gzip -9 -c {packages_file_path} > {packages_gz_file_path}", env={'GNUPGHOME': self.keyring_dir})

            release_file_path = os.path.join(current_dist, "Release")
            with open(release_file_path, "w") as f:
                f.write(self.__generate_release__(dist, key_id))
                
            out, err, rc = execute_cmd(f"gpg -abs -u {key_id} --yes -o {os.path.join(current_dist, 'Release.gpg')} {release_file_path}", env={'GNUPGHOME': self.keyring_dir})
            out, err, rc = execute_cmd(f"gpg --clearsign -u {key_id} --yes -o {os.path.join(current_dist, 'InRelease')} {release_file_path}", env={'GNUPGHOME': self.keyring_dir})
        print("Repository updated.")
    
    def watch_pools(self):
        '''Watch package pool directories for any event (file create, delete, modify, move). Calls EventHandler's functions in case of events.'''
        from watcher import Watcher
        
        pool_paths = []
        for dist in self.dists:
            pool_paths.append(os.path.join(self.dists_dir, dist, "pool") )

        watcher = Watcher(stop_event=stop_threads, onupdate=self.update, directories=pool_paths)
        
        watcher.start()
        
    def create_service(self, config_path):
        print("Creating systemd service...")
        service_file_path = f"/etc/systemd/system/{self.conf['short_name']}.service"
        service_file_content = f"""[Unit]
Description={self.conf['description']}

[Service]
WorkingDirectory={self.root_dir}
ExecStart=python3 debianrepo.py -c {os.path.realpath(config_path)}

[Install]
WantedBy=multi-user.target
"""

        with open(service_file_path, "w") as f:
            f.write(service_file_content)
            
        out, err, rc = execute_cmd("systemctl daemon-reload")
        if rc != 0:
            print(f"Error while reloading systemctl services: {err.decode('utf-8')}")
            
        out, err, rc = execute_cmd(f"systemctl enable {self.conf['short_name']}.service")
        if rc != 0:
            print(f"Error while enabling {self.conf['short_name']}.service: {err.decode('utf-8')}")
            
        out, err, rc = execute_cmd(f"systemctl start {self.conf['short_name']}.service")
        if rc != 0:
            print(f"Error while starting {self.conf['short_name']}.service: {err.decode('utf-8')}")

        print("Done.")
        
    def remove_service(self, config_path):
        service_file_path = f"/etc/systemd/system/{self.conf['short_name']}.service"
        
        if not os.path.exists(service_file_path):
            print(f"Service doesn't exist: {service_file_path}")
            return
        
        print("Removing systemd service...")
            
        out, err, rc = execute_cmd(f"systemctl stop {self.conf['short_name']}.service")
        if rc != 0:
            print(f"Error while starting {self.conf['short_name']}.service: {err.decode('utf-8')}")
            
        out, err, rc = execute_cmd(f"systemctl disable {self.conf['short_name']}.service")
        if rc != 0:
            print(f"Error while enabling {self.conf['short_name']}.service: {err.decode('utf-8')}")
            
        out, err, rc = execute_cmd("systemctl daemon-reload")
        if rc != 0:
            print(f"Error while reloading systemctl services: {err.decode('utf-8')}")
            
        os.remove(service_file_path)

        print("Done.")
        
    def __generate_connection_guide__(self):
        guide_file_path = os.path.join(self.root_dir, "CONNECTION_GUIDE.md")
        guide_content = f"""## Using Debian Repository

Available options:

* Distribution: **{', '.join(self.conf['dists'])}**
* Architecture: **{', '.join(self.conf['architectures'])}**

```shell
export APT_SERVER_IP="1.1.1.1"
export APT_DIST=jammy
export APT_ARCH=amd64

# Fetch GPG signature
wget -qO- http://$APT_SERVER_IP:{self.port}/publickey.gpg | gpg --dearmor | sudo tee /usr/share/keyrings/{self.conf['short_name']}.gpg >/dev/null

# Fetch repository info
echo "deb [arch=$APT_ARCH, signed-by=/usr/share/keyrings/{self.conf['short_name']}.gpg] http://$APT_SERVER_IP:{self.port}/debian $APT_DIST stable" | sudo tee /etc/apt/sources.list.d/{self.conf['short_name']}.list

# Update sources
sudo apt update
```
"""

        with open(guide_file_path, "w") as f:
            f.write(guide_content)
        
        print(f"Connection guide created in {guide_file_path}")
