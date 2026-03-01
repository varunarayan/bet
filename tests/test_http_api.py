from __future__ import annotations

import json
import threading
import unittest
from datetime import datetime, timedelta, timezone
from urllib import request

from app.http_api import LivePredictionRequestHandler, create_server
from app.live_prediction_system import LivePredictionSystem


class HttpApiTests(unittest.TestCase):
    def setUp(self) -> None:
        LivePredictionRequestHandler.system = LivePredictionSystem()
        self.server = create_server(port=0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)

    def _request(self, method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = request.Request(
            url=f"http://127.0.0.1:{self.port}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        with request.urlopen(req) as response:
            body = json.loads(response.read().decode("utf-8"))
            return response.status, body

    def test_full_api_prediction_lifecycle(self) -> None:
        status, body = self._request("POST", "/auth/signup", {"user_id": "u1"})
        self.assertEqual(status, 201)
        self.assertEqual(body["coins"], 100)

        status, _ = self._request(
            "POST",
            "/events",
            {
                "event_id": "e1",
                "match_id": "m1",
                "model_type": "next_over_runs",
                "option_a": "Over 9.5",
                "option_b": "Under 9.5",
                "prob_a": 0.55,
                "prob_b": 0.45,
                "lock_in_seconds": 100,
            },
        )
        self.assertEqual(status, 201)

        status, body = self._request(
            "POST",
            "/predictions",
            {
                "prediction_id": "p1",
                "user_id": "u1",
                "event_id": "e1",
                "selected_option": "Under 9.5",
            },
        )
        self.assertEqual(status, 201)
        self.assertEqual(body["status"], "open")

        status, body = self._request("PATCH", "/predictions/p1", {"selected_option": "Over 9.5"})
        self.assertEqual(status, 200)
        self.assertEqual(body["selected_option"], "Over 9.5")

        # lock + settle using backend internals to simulate scheduler/domain trigger
        event = LivePredictionRequestHandler.system.events["e1"]
        event.lock_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        LivePredictionRequestHandler.system.lock_started_events()

        status, body = self._request("POST", "/events/e1/settle", {"result_option": "Over 9.5"})
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "settled")

        status, body = self._request("GET", "/dashboard/u1")
        self.assertEqual(status, 200)
        self.assertEqual(body["total_points"], 55)
        self.assertEqual(body["accuracy_percent"], 100.0)

    def test_get_open_events(self) -> None:
        self._request("POST", "/auth/signup", {"user_id": "u1"})
        self._request(
            "POST",
            "/events",
            {
                "event_id": "e2",
                "match_id": "m1",
                "model_type": "match_winner",
                "option_a": "Team A",
                "option_b": "Team B",
                "prob_a": 0.4,
                "prob_b": 0.6,
                "lock_in_seconds": 100,
            },
        )

        status, body = self._request("GET", "/events?status=open")
        self.assertEqual(status, 200)
        self.assertEqual(len(body["events"]), 1)
        self.assertEqual(body["events"][0]["event_id"], "e2")


    def test_docs_alias_endpoints_and_not_found_payload(self) -> None:
        self._request("POST", "/auth/signup", {"user_id": "u2"})
        self._request(
            "POST",
            "/events",
            {
                "event_id": "e3",
                "match_id": "m2",
                "model_type": "next_over_runs",
                "option_a": "Over 8.5",
                "option_b": "Under 8.5",
                "prob_a": 0.51,
                "prob_b": 0.49,
                "lock_in_seconds": 100,
            },
        )

        status, body = self._request("GET", "/matches/m2/prediction-events?status=open")
        self.assertEqual(status, 200)
        self.assertEqual(len(body["events"]), 1)

        status, body = self._request(
            "POST",
            "/prediction-events/e3/picks",
            {
                "prediction_id": "p3",
                "user_id": "u2",
                "selected_option": "Over 8.5",
            },
        )
        self.assertEqual(status, 201)
        self.assertEqual(body["status"], "open")

        status, body = self._request("PATCH", "/picks/p3", {"selected_option": "Under 8.5"})
        self.assertEqual(status, 200)
        self.assertEqual(body["selected_option"], "Under 8.5")

    def test_root_and_health_routes(self) -> None:
        status, body = self._request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("routes", body)

        status, body = self._request("GET", "/healthz")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")


if __name__ == "__main__":
    unittest.main()
