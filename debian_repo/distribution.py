from datetime import datetime
from os import path, makedirs
from typing import List
from threading import Lock

from .helpers import generate_packages_file, generate_packages_gz_file, generate_inrelease_file, \
    generate_release_gpg_file, get_gpg_key_id
from .logger import log
from .ops import do_hash


class Distribution:
    def __init__(self, name: str, dist_dir: str, architectures: List[str], keyring_dir: str, debian_dir: str,
                 description: str):
        self.name = name
        self.dist_dir = dist_dir
        self.pool_dir = path.join(dist_dir, 'pool')
        self.archs = architectures
        self.keyring_dir = keyring_dir
        self.debian_dir = debian_dir
        self.description = description
        self.key_id = get_gpg_key_id(self.keyring_dir)
        self.update_mutex = Lock()
        self.update_wait_mutex = Lock()
        self.queued_update_requests = 0

    def create_pool_directory(self):
        makedirs(self.pool_dir, exist_ok=True)

    def update(self):
        with self.update_wait_mutex:
            if self.queued_update_requests >= 2:
                log(f"There are already queued updates for {self.name} distribution. Discarded.")
                return
            self.queued_update_requests += 1
        log(f"{self.name}: Waiting update lock...")
        with self.update_mutex:
            log(f"{self.name}: Acquired lock.")
            log(f"{self.name}: Updating...")
            try:
                self.__update_packages__()
                self.__generate_release_files__()
                log(f"{self.name}: Updated.")
            except Exception as e:
                log(f"Error during {self.name} update: {e}")
                with self.update_wait_mutex:
                    self.queued_update_requests -= 1
                raise e
        with self.update_wait_mutex:
            self.queued_update_requests -= 1

    def __update_packages__(self):
        for arch in self.archs:
            pool_path = path.join(self.pool_dir, "stable", arch)
            packages_path = path.join(self.dist_dir, "stable", f"binary-{arch}")
            makedirs(packages_path, exist_ok=True)
            makedirs(pool_path, exist_ok=True)

            generate_packages_file(self.keyring_dir, path.relpath(pool_path, self.debian_dir), packages_path, arch)

            generate_packages_gz_file(self.keyring_dir, packages_path)

    def __generate_release_files__(self):
        release_file_path = path.join(self.dist_dir, "Release")
        with open(release_file_path, "w") as f:
            f.write(self.__generate_release_content__())

        release_gpg_file_path = path.join(self.dist_dir, "Release.gpg")
        generate_release_gpg_file(self.key_id, self.keyring_dir, release_gpg_file_path, release_file_path)

        inrelease_file_path = path.join(self.dist_dir, "InRelease")
        generate_inrelease_file(self.key_id, self.keyring_dir, inrelease_file_path, release_file_path)

    def __generate_release_content__(self):
        date = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
        md5sums = do_hash("MD5Sum", "md5sum", self.dist_dir)
        sha1sums = do_hash("SHA1", "sha1sum", self.dist_dir)
        sha256sums = do_hash("SHA256", "sha256sum", self.dist_dir)
        return f"""Origin: {self.description}
Suite: {self.name}
Codename: {self.name}
Version: 1.0
Architectures: {" ".join(self.archs)}
Components: stable
Description: {self.description}
Date: {date}
SignWith: {self.key_id}
{md5sums}
{sha1sums}
{sha256sums}"""
