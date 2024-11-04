import datetime
import tarfile

from glob import glob
from os import path, makedirs, walk, remove
from threading import Event
from time import sleep
from zipfile import ZipFile, ZIP_DEFLATED

from .logger import log


class BackupManager:
    def __init__(self, stop_event: Event, backup_dir: str, backup_destination: str, interval_in_hours=24, copies=5,
                 backup_format="zip"):
        self.stop_event = stop_event
        makedirs(backup_destination, exist_ok=True)
        if backup_format != "zip" and backup_format != "tar" and backup_format != "both":
            raise ValueError(f"Backup format must be 'zip', 'tar' or 'both'!. Given: {backup_format}")
        self.backup_dir = backup_dir
        self.backup_dest = backup_destination
        if interval_in_hours < 1:
            log("Backup interval cannot be under 1 hour! It is set to 1.")
            interval_in_hours = 1
        self.interval_in_hours = interval_in_hours
        self.copies = copies
        self.backup_format = backup_format
        self.last_backup = None

    @staticmethod
    def write_zip_archive(folder_path, zip_file_path):
        with ZipFile(zip_file_path, 'w', ZIP_DEFLATED) as zipf:
            for root, dirs, files in walk(folder_path):
                for file in files:
                    file_path = path.join(root, file)
                    arcname = path.relpath(str(file_path), path.dirname(folder_path))
                    zipf.write(str(file_path), arcname)

    @staticmethod
    def write_tar_archive(folder_path, tar_file_path):
        with tarfile.open(tar_file_path, "w:gz") as tar:
            tar.add(folder_path, arcname=path.basename(folder_path))

    def backup(self):
        if self.backup_format == "zip" or self.backup_format == "both":
            archive_path = path.join(self.backup_dest, f"{datetime.datetime.now().isoformat()}.zip")
            self.write_zip_archive(self.backup_dir, archive_path)
        if self.backup_format == "tar" or self.backup_format == "both":
            archive_path = path.join(self.backup_dest, f"{datetime.datetime.now().isoformat()}.tar.gz")
            self.write_tar_archive(self.backup_dir, archive_path)
        log(f"Backup created at '{archive_path}'.")

    def remove_old_backups(self):
        files = glob(path.join(self.backup_dest, "*"))

        target_files = [f for f in files if f.endswith(".zip") or f.endswith(".tar.gz")]
        target_files.sort(key=path.getctime)

        while len(target_files) > self.copies:
            oldest_file = target_files.pop(0)
            try:
                remove(oldest_file)
                log(f"Removed old backup: '{oldest_file}'")
            except Exception as e:
                log(f"Failed to remove '{oldest_file}': {e}")

    def run(self):
        while not self.stop_event.is_set():
            need_backup = self.last_backup is None
            if not need_backup:
                elapsed_seconds = (datetime.datetime.now() - self.last_backup).total_seconds()
                need_backup = elapsed_seconds >= (self.interval_in_hours * 1 * 1)  # TODO: Multiply with * 60 * 60
            if need_backup:
                self.last_backup = datetime.datetime.now()
                self.backup()
                self.remove_old_backups()

            sleep(2)  # Check every 2 seconds
