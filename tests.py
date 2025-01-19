from datetime import datetime, timedelta
import unittest

from debian_repo.common import execute_cmd
from debian_repo.server import AuthHandler, unauthorized_access_map


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