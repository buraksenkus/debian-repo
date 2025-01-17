import unittest
from debian_repo.common import execute_cmd


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

if __name__ == '__main__':
    unittest.main()