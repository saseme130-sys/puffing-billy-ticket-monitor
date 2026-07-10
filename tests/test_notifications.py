import json
import unittest
from unittest.mock import patch

import monitor


class ServerChanTests(unittest.TestCase):
    def test_successful_send(self):
        cfg = {"notify": {"serverchan_key": "SCT_test"}}
        response = json.dumps({
            "code": 0,
            "message": "SUCCESS",
            "data": {"pushid": "1"},
        })

        with patch("monitor.http", return_value=response):
            result = monitor.notify_serverchan(
                cfg, "Ticket alert", "Available")

        self.assertEqual(result, (True, "SUCCESS"))

    def test_rejected_send(self):
        cfg = {"notify": {"serverchan_key": "SCT_test"}}
        response = json.dumps({"code": 40001, "message": "bad sendkey"})

        with patch("monitor.http", return_value=response):
            result = monitor.notify_serverchan(
                cfg, "Ticket alert", "Available")

        self.assertEqual(result, (False, "bad sendkey"))

    def test_missing_key_is_skipped(self):
        result = monitor.notify_serverchan(
            {"notify": {}}, "Ticket alert", "Available")

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
