from .backup import BackupManager
from .common import execute_cmd
from .distribution import Distribution
from .logger import log
from .server import ThreadedHTTPServer, AuthHandler

import os
from threading import Event, Thread
from typing import Dict

stop_threads = Event()


class DebianRepository:
    def __init__(self, config: Dict, repo_dir: str, no_watch=True) -> None:
        self.conf = config
        self.dir = repo_dir
        self.dists: Dict[str, Distribution] = {}
        for dist_name in config["dists"]:
            dist_dir = os.path.join(self.dists_dir, dist_name)
            self.dists[dist_name] = Distribution(dist_name, dist_dir, config["architectures"], self.keyring_dir,
                                                 self.debian_dir, config["description"])
        self.no_watch = no_watch
        if "backup" in config and "enable" in config["backup"] and config["backup"]["enable"]:
            log("Backup enabled.")
            interval_in_hours = config["backup"]["interval"] if "interval" in config["backup"] else 24
            copies = config["backup"]["copies"] if "copies" in config["backup"] else 5
            backup_format = config["backup"]["format"] if "format" in config["backup"] else "zip"
            self.backup_manager = BackupManager(stop_event=stop_threads, backup_dir=self.dir,
                                                backup_destination=os.path.join(self.root_dir, "backups"),
                                                interval_in_hours=interval_in_hours, copies=copies,
                                                backup_format=backup_format)
        else:
            log("Backup disabled.")
            self.backup_manager = None

    @property
    def port(self):
        return int(self.conf["port"])

    @property
    def root_dir(self):
        return os.path.dirname(self.dir)

    @property
    def keyring_dir(self):
        return os.path.join(self.root_dir, "keyring")

    @property
    def debian_dir(self):
        return os.path.join(self.dir, "debian")

    @property
    def dists_dir(self):
        return os.path.join(self.debian_dir, "dists")

    @property
    def gpg_key_ok(self):
        """Checks if GPG key exists."""
        if os.path.exists(self.keyring_dir):
            keys = execute_cmd(f'gpg --list-keys', env={'GNUPGHOME': self.keyring_dir})[0].decode('utf-8')
            return self.conf["email"] in keys
        return False

    def create_pool_directories(self):
        for dist_name, dist in self.dists.items():
            dist.create_pool_directory()

    def start(self):
        """Starts HTTP server and package pool watching. Generates GPG key automatically if it doesn't exist."""
        self.create_pool_directories()
        os.chdir(self.dir)

        if not self.gpg_key_ok:
            self.generate_gpg()

        self.__generate_connection_guide__()
        self.update_all_dists()

        server_address = ('', self.port)
        httpd = ThreadedHTTPServer(server_address, lambda *args, **kwargs: AuthHandler(*args, auth=self.conf["auth"],
                                                                                       users=self.conf["users"],
                                                                                       **kwargs))
        log(f"Serving directory '{self.dir}' on port {self.port} ...")
        try:
            if not self.no_watch:
                watch_thread = Thread(target=self.watch_pools)
                watch_thread.start()

            if self.backup_manager is not None:
                backup_thread = Thread(target=self.backup_manager.run)
                backup_thread.start()

            httpd.serve_forever()
        except KeyboardInterrupt:
            log(f"Requested termination.")
            stop_threads.set()
            httpd.shutdown()
            httpd.server_close()
        except Exception as e:
            log(f"Error: {e}")
            stop_threads.set()
            httpd.shutdown()
            httpd.server_close()

    def generate_gpg(self):
        """Generates GPS key for signing repository."""
        os.makedirs(self.dir, exist_ok=True)

        if not self.gpg_key_ok:
            log("Generating GPG key...")
            os.makedirs(self.keyring_dir, mode=0o700, exist_ok=True)

            cmd_input = "\n".join([
                "Key-Type: RSA",
                "Key-Length: 4096",
                "Expire-Date: 0",
                f"Name-Real: {self.conf['name']}",
                f"Name-Email: {self.conf['email']}",
                "%no-protection"
            ])

            out, err, rc = execute_cmd(
                f'gpgconf --kill gpg-agent && echo "{cmd_input}" | gpg --full-gen-key --batch --yes',
                env={'GNUPGHOME': self.keyring_dir})

            if "fail" in err.decode("utf-8"):
                raise Exception(err.decode("utf-8"))

            out, err, rc = execute_cmd(
                f'gpg --armor --export {self.conf["email"]} > {os.path.join(self.dir, "publickey.gpg")}',
                env={'GNUPGHOME': self.keyring_dir})

            if not self.gpg_key_ok:
                raise Exception("Couldn't generate GPG key!")

        else:
            log(f"Already exists. If you want to create a new key, run 'rm -r {self.keyring_dir}'")

    def update_dist(self, dist):
        self.dists[dist].update()

    def update_all_dists(self):
        for dist_name, dist in self.dists.items():
            dist.update()

    def watch_pools(self):
        """Watch package pool directories for any event (file create, delete, modify, move). Calls EventHandler's functions in case of events."""
        from .watcher import Watcher

        pool_paths = []
        for dist_name, dist in self.dists.items():
            pool_paths.append(dist.pool_dir)

        watcher = Watcher(stop_event=stop_threads, onupdate=self.update_dist, directories=pool_paths)

        watcher.start()

    def create_service(self, config_path):
        log("Creating systemd service...")
        service_file_path = f"/etc/systemd/system/{self.conf['short_name']}.service"
        service_file_content = f"""[Unit]
Description={self.conf['description']}

[Service]
WorkingDirectory={self.root_dir}
ExecStart=python3 debianrepo -c {os.path.realpath(config_path)}

[Install]
WantedBy=multi-user.target
"""

        with open(service_file_path, "w") as f:
            f.write(service_file_content)

        out, err, rc = execute_cmd("systemctl daemon-reload")
        if rc != 0:
            log(f"Error while reloading systemctl services: {err.decode('utf-8')}")

        out, err, rc = execute_cmd(f"systemctl enable {self.conf['short_name']}.service")
        if rc != 0:
            log(f"Error while enabling {self.conf['short_name']}.service: {err.decode('utf-8')}")

        out, err, rc = execute_cmd(f"systemctl start {self.conf['short_name']}.service")
        if rc != 0:
            log(f"Error while starting {self.conf['short_name']}.service: {err.decode('utf-8')}")

        log("Done.")

    def remove_service(self):
        service_file_path = f"/etc/systemd/system/{self.conf['short_name']}.service"

        if not os.path.exists(service_file_path):
            log(f"Service doesn't exist: {service_file_path}")
            return

        log("Removing systemd service...")

        out, err, rc = execute_cmd(f"systemctl stop {self.conf['short_name']}.service")
        if rc != 0:
            log(f"Error while starting {self.conf['short_name']}.service: {err.decode('utf-8')}")

        out, err, rc = execute_cmd(f"systemctl disable {self.conf['short_name']}.service")
        if rc != 0:
            log(f"Error while enabling {self.conf['short_name']}.service: {err.decode('utf-8')}")

        out, err, rc = execute_cmd("systemctl daemon-reload")
        if rc != 0:
            log(f"Error while reloading systemctl services: {err.decode('utf-8')}")

        os.remove(service_file_path)

        log("Done.")

    def __generate_connection_guide__(self):
        guide_file_path = os.path.join(self.root_dir, "CONNECTION_GUIDE.md")
        credentials = ""
        credential_vars = ""
        auth_conf_line = ""
        if "auth" in self.conf and self.conf["auth"].lower() == "basic":
            credentials = "$APT_USERNAME:$APT_PASSWORD@"
            credential_vars = "export APT_USERNAME=username\nexport APT_PASSWORD=password\n"
            auth_conf_line = f"\necho \"machine http://$APT_SERVER_IP:{self.port} login $APT_USERNAME password $APT_PASSWORD\" | sudo tee /etc/apt/auth.conf.d/{self.conf['short_name']}.conf\n"
        guide_content = f"""## Using Debian Repository

Available options:

* Distribution: **{', '.join(self.conf['dists'])}**
* Architecture: **{', '.join(self.conf['architectures'])}**

```shell
export APT_SERVER_IP="1.1.1.1"
export APT_DIST=jammy
export APT_ARCH=amd64
{credential_vars}
# Fetch GPG signature
wget -qO- http://{credentials}$APT_SERVER_IP:{self.port}/publickey.gpg | gpg --dearmor | sudo tee /usr/share/keyrings/{self.conf['short_name']}.gpg >/dev/null

# Fetch repository info
echo "deb [arch=$APT_ARCH, signed-by=/usr/share/keyrings/{self.conf['short_name']}.gpg] http://$APT_SERVER_IP:{self.port}/debian $APT_DIST stable" | sudo tee /etc/apt/sources.list.d/{self.conf['short_name']}.list
{auth_conf_line}
# Update sources
sudo apt update
```
"""

        with open(guide_file_path, "w") as f:
            f.write(guide_content)

        log(f"Connection guide created in {guide_file_path}")
