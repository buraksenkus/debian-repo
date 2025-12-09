from datetime import datetime, timedelta
import unittest
import os
import shutil
import hashlib
import tarfile
from zipfile import ZipFile

from debian_repo.common import execute_cmd
from debian_repo.server import AuthHandler, unauthorized_access_map
from debian_repo.ops import calculate_hashes
from debian_repo.backup import BackupManager


class TestOps(unittest.TestCase):

    def test_execute_cmd(self):
        out, err, rc = execute_cmd("ls -al")
        self.assertEqual(rc, 0, f'Return value is: {rc}')
        self.assertTrue(out.decode("utf-8").find("..") != -1)
        self.assertEqual(len(err.decode("utf-8")), 0)

        out, err, rc = execute_cmd("asdasd")
        self.assertNotEqual(rc, 0)
        self.assertTrue(len(err.decode("utf-8")) > 0)
        self.assertEqual(len(out.decode("utf-8")), 0)

class TestHashing(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_dist"
        os.makedirs(self.test_dir, exist_ok=True)
        with open(os.path.join(self.test_dir, "file1.txt"), "w") as f:
            f.write("This is a test file.")
        with open(os.path.join(self.test_dir, "file2.txt"), "w") as f:
            f.write("This is another test file.")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_calculate_hashes(self):
        md5sum, sha1sum, sha256sum = calculate_hashes(self.test_dir)

        with open(os.path.join(self.test_dir, "file1.txt"), 'rb') as f:
            file1_content = f.read()
        with open(os.path.join(self.test_dir, "file2.txt"), 'rb') as f:
            file2_content = f.read()

        file1_md5 = hashlib.md5(file1_content).hexdigest()
        file1_sha1 = hashlib.sha1(file1_content).hexdigest()
        file1_sha256 = hashlib.sha256(file1_content).hexdigest()
        file1_size = len(file1_content)

        file2_md5 = hashlib.md5(file2_content).hexdigest()
        file2_sha1 = hashlib.sha1(file2_content).hexdigest()
        file2_sha256 = hashlib.sha256(file2_content).hexdigest()
        file2_size = len(file2_content)

        self.assertIn(f"{file1_md5} {file1_size} file1.txt", md5sum)
        self.assertIn(f"{file2_md5} {file2_size} file2.txt", md5sum)

        self.assertIn(f"{file1_sha1} {file1_size} file1.txt", sha1sum)
        self.assertIn(f"{file2_sha1} {file2_size} file2.txt", sha1sum)

        self.assertIn(f"{file1_sha256} {file1_size} file1.txt", sha256sum)
        self.assertIn(f"{file2_sha256} {file2_size} file2.txt", sha256sum)


class TestBackup(unittest.TestCase):
    def setUp(self):
        self.backup_dir = "test_backup_src"
        self.backup_dest = "test_backup_dest"
        os.makedirs(self.backup_dir, exist_ok=True)
        os.makedirs(self.backup_dest, exist_ok=True)
        with open(os.path.join(self.backup_dir, "file1.txt"), "w") as f:
            f.write("This is a test file.")
        with open(os.path.join(self.backup_dir, "file2.txt"), "w") as f:
            f.write("This is another test file.")

    def tearDown(self):
        shutil.rmtree(self.backup_dir)
        shutil.rmtree(self.backup_dest)

    def test_write_zip_archive(self):
        zip_path = os.path.join(self.backup_dest, "test.zip")
        BackupManager.write_zip_archive(self.backup_dir, zip_path)
        self.assertTrue(os.path.exists(zip_path))
        with ZipFile(zip_path, 'r') as zipf:
            self.assertEqual(len(zipf.namelist()), 2)

    def test_write_tar_archive(self):
        tar_path = os.path.join(self.backup_dest, "test.tar.gz")
        BackupManager.write_tar_archive(self.backup_dir, tar_path)
        self.assertTrue(os.path.exists(tar_path))
        with tarfile.open(tar_path, 'r:gz') as tar:
            self.assertEqual(len(tar.getnames()), 2)

    def test_archive_consistency(self):
        zip_path = os.path.join(self.backup_dest, "test.zip")
        tar_path = os.path.join(self.backup_dest, "test.tar.gz")

        BackupManager.write_zip_archive(self.backup_dir, zip_path)
        BackupManager.write_tar_archive(self.backup_dir, tar_path)

        with ZipFile(zip_path, 'r') as zipf:
            zip_contents = sorted(zipf.namelist())

        with tarfile.open(tar_path, 'r:gz') as tar:
            tar_contents = sorted(tar.getnames())

        self.assertEqual(zip_contents, tar_contents)

    def test_remove_old_backups(self):
        for i in range(7):
            with open(os.path.join(self.backup_dest, f"backup{i}.zip"), "w") as f:
                f.write("test")
        manager = BackupManager(None, self.backup_dir, self.backup_dest, copies=5)
        manager.remove_old_backups()
        self.assertEqual(len(os.listdir(self.backup_dest)), 5)


class TestAuthorization(unittest.TestCase):
    def test_no_unauthorized_attempts(self):
        client_ip = "192.168.1.1"
        result = AuthHandler.check_multiple_unauthorized_access(client_ip)
        self.assertFalse(result, "Should return False for an IP not in unauthorized_access_map")

    def test_below_threshold_attempts(self):
        client_ip = "192.168.1.2"
        unauthorized_access_map[client_ip] = {"count": 4, "first": datetime.now()}
        result = AuthHandler.check_multiple_unauthorized_access(client_ip)
        self.assertFalse(result, "Should return False for IP with attempts below the threshold")

    def test_exceed_threshold_within_30_minutes(self):
        client_ip = "192.168.1.3"
        unauthorized_access_map[client_ip] = {"count": 5, "first": datetime.now() - timedelta(minutes=29)}
        result = AuthHandler.check_multiple_unauthorized_access(client_ip)
        self.assertTrue(result, "Should return True for IP exceeding the threshold within 30 minutes")

    def test_exceed_threshold_beyond_30_minutes(self):
        client_ip = "192.168.1.4"
        first_attempt_time = datetime.now() - timedelta(minutes=31)
        unauthorized_access_map[client_ip] = {"count": 5, "first": first_attempt_time}

        result = AuthHandler.check_multiple_unauthorized_access(client_ip)
        self.assertFalse(result, "Should return False for IP exceeding threshold beyond 30 minutes")
        self.assertNotIn(client_ip, unauthorized_access_map,
                         "Should remove IP from unauthorized_access_map after 30 minutes")

    def test_exceed_threshold_exactly_at_30_minutes(self):
        client_ip = "192.168.1.5"
        unauthorized_access_map[client_ip] = {"count": 5, "first": datetime.now() - timedelta(minutes=30)}
        result = AuthHandler.check_multiple_unauthorized_access(client_ip)
        self.assertFalse(result, "Should return True for IP exceeding threshold exactly at 30 minutes")


if __name__ == '__main__':
    unittest.main()