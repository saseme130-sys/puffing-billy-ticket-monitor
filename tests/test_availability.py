import json
import unittest
from unittest.mock import call, patch

import monitor


class PassengerAwareAvailabilityTests(unittest.TestCase):
    def test_configures_all_passengers_before_availability_query(self):
        availability = [{"date": "29/08/2026", "status": "Sold out"}]
        responses = [
            json.dumps({"result": "OK"}),
            json.dumps({"result": "OK"}),
            json.dumps({"result": "OK"}),
            json.dumps({"result": "OK", "availability": availability}),
        ]

        with patch("monitor.http", side_effect=responses) as request:
            result = monitor.fetch_availability(
                "token-123", {"adult": 2, "child": 1})

        self.assertEqual(result, availability)
        self.assertEqual(request.call_count, 4)
        bodies = [item.kwargs["data"] for item in request.call_args_list]
        self.assertEqual(bodies, [
            "&fare=2867_2810&roomtype=&increment=1",
            "&fare=2867_2810&roomtype=&increment=1",
            "&fare=2867_2812&roomtype=&increment=1",
            "BookingCategory=1",
        ])
        for item in request.call_args_list:
            self.assertIn(
                "oidToken=token-123",
                item.kwargs["headers"]["Cookie"],
            )

    def test_rejected_passenger_update_stops_the_check(self):
        response = json.dumps({"result": "ERROR", "message": "rejected"})

        with patch("monitor.http", return_value=response):
            with self.assertRaisesRegex(
                    RuntimeError, "设置乘客数量失败"):
                monitor.fetch_availability(
                    "token-123", {"adult": 1, "child": 0})

    def test_requires_at_least_one_supported_passenger(self):
        with self.assertRaisesRegex(RuntimeError, "未配置有效乘客"):
            monitor.fetch_availability(
                "token-123", {"adult": 0, "child": 0})

    @patch("monitor.save_json")
    @patch("monitor.fetch_availability", return_value=[])
    @patch("monitor.fetch_oid_token", return_value="token-123")
    def test_local_check_passes_configured_passengers(
            self, _token, availability, _save):
        cfg = {
            "target_dates": [],
            "route_code": "BEL-LAK",
            "passengers": {"adult": 2, "child": 1},
            "notify": {},
        }

        monitor.check_once(cfg, {}, do_notify=False)

        availability.assert_called_once_with(
            "token-123", {"adult": 2, "child": 1})


if __name__ == "__main__":
    unittest.main()
