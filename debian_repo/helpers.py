from .common import execute_cmd
from .logger import log

from os import path


def generate_release_gpg_file(key_id: str, keyring_dir: str, dist_dir: str, release_file_path: str):
    out, err, rc = execute_cmd(
        f"gpg -abs -u {key_id} --yes -o {path.join(dist_dir, 'Release.gpg')} {release_file_path}",
        env={'GNUPGHOME': keyring_dir})
    if rc != 0:
        log(f"Error while generating Release.gpg in {dist_dir}: {err.decode('utf-8')}")


def generate_inrelease_file(key_id: str, keyring_dir: str, dist_dir: str, release_file_path: str):
    out, err, rc = execute_cmd(
        f"gpg --clearsign -u {key_id} --yes -o {path.join(dist_dir, 'InRelease')} {release_file_path}",
        env={'GNUPGHOME': keyring_dir})
    if rc != 0:
        log(f"Error while generating InRelease in {dist_dir}: {err.decode('utf-8')}")


def generate_packages_file(keyring_dir: str, pool_dir: str, packages_folder: str, arch: str):
    packages_file_path = path.join(packages_folder, 'Packages')
    out, err, rc = execute_cmd(
        f"dpkg-scanpackages -m --arch {arch} {pool_dir} > {packages_file_path}",
        env={'GNUPGHOME': keyring_dir})
    if rc != 0:
        log(f"Error while scanning packages: {err.decode('utf-8')}")


def generate_packages_gz_file(keyring_dir: str, packages_folder: str):
    packages_file_path = path.join(packages_folder, 'Packages')
    packages_gz_file_path = path.join(packages_folder, 'Packages.gz')
    out, err, rc = execute_cmd(f"gzip -9 -c {packages_file_path} > {packages_gz_file_path}",
                               env={'GNUPGHOME': keyring_dir})
    if rc != 0:
        log(f"Error while zipping package info: {err.decode('utf-8')}")


def get_gpg_key_id(keyring_dir: str):
    out, err, rc = execute_cmd(f"gpg --list-keys --with-colons | grep '^pub' | cut -d: -f5",
                               env={'GNUPGHOME': keyring_dir})

    return out.decode("utf-8").strip()
