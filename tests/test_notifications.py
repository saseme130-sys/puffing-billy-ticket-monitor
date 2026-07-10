import json
import os
import unittest
from unittest.mock import patch

import check_ticket
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

    def test_environment_key_overrides_config(self):
        cfg = {"notify": {"serverchan_key": "old"}}

        with patch.dict(os.environ, {"SERVERCHAN_KEY": "new"}, clear=False):
            result = monitor.apply_secret_overrides(cfg)

        self.assertEqual(result["notify"]["serverchan_key"], "new")

    @patch("monitor.notify_pushplus")
    @patch("monitor.notify_wxpusher")
    @patch("monitor.notify_serverchan", return_value=(True, "SUCCESS"))
    def test_send_all_stops_after_serverchan_success(
            self, serverchan, wxpusher, pushplus):
        cfg = {
            "notify": {
                "serverchan_key": "SCT_test",
                "macos_notification": False,
                "terminal_bell": False,
            },
        }

        result = monitor.send_all(cfg, "title", "subtitle", ["body"])

        self.assertTrue(result)
        serverchan.assert_called_once()
        wxpusher.assert_not_called()
        pushplus.assert_not_called()

    @patch("monitor.notify_serverchan", return_value=(False, "rejected"))
    def test_send_all_returns_false_when_delivery_fails(self, serverchan):
        cfg = {
            "notify": {
                "serverchan_key": "SCT_test",
                "macos_notification": False,
                "terminal_bell": False,
            },
        }

        result = monitor.send_all(cfg, "title", "subtitle", ["body"])

        self.assertFalse(result)
        serverchan.assert_called_once()

    @patch("check_ticket.monitor.send_all", return_value=False)
    @patch("check_ticket.monitor.fetch_availability")
    @patch("check_ticket.monitor.fetch_oid_token", return_value="oid")
    def test_cloud_check_fails_when_bookable_alert_is_not_delivered(
            self, _token, availability, send_all):
        availability.return_value = [{
            "date": "29/08/2026",
            "status": "Available",
            "detailedAvailability": [{
                "code": "BEL-LAK",
                "available": "Available",
            }],
        }]
        cfg = {
            "target_dates": ["29/08/2026"],
            "route_code": "BEL-LAK",
            "route_name_hint": "Belgrave to Lakeside",
            "passengers": {"adult": 2, "child": 1},
            "notify": {},
        }

        with patch("check_ticket.monitor.load_json", return_value=cfg), \
                patch("check_ticket.monitor.apply_secret_overrides",
                      side_effect=lambda value: value), \
                patch.dict(os.environ, {}, clear=True):
            result = check_ticket.main()

        self.assertEqual(result, 3)
        send_all.assert_called_once()


if __name__ == "__main__":
    unittest.main()
