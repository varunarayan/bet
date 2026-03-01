from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from .live_prediction_system import EventStatus, LivePredictionSystem, ModelType


class LivePredictionRequestHandler(BaseHTTPRequestHandler):
    system = LivePredictionSystem()

    def _json_response(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def _route_match(self, prefix: str) -> Optional[str]:
        path = urlparse(self.path).path
        if path.startswith(prefix):
            return path[len(prefix):]
        return None

    def do_POST(self) -> None:  # noqa: N802
        try:
            path = urlparse(self.path).path
            if path == "/auth/signup":
                payload = self._read_json()
                profile = self.system.signup(payload["user_id"])
                self._json_response(
                    201,
                    {
                        "user_id": profile.user_id,
                        "coins": profile.coins,
                        "level": profile.level,
                    },
                )
                return

            if path == "/events":
                payload = self._read_json()
                event = self.system.create_prediction_event(
                    event_id=payload["event_id"],
                    match_id=payload["match_id"],
                    model_type=ModelType(payload["model_type"]),
                    option_a=payload["option_a"],
                    option_b=payload["option_b"],
                    prob_a=float(payload["prob_a"]),
                    prob_b=float(payload["prob_b"]),
                    lock_in_seconds=int(payload["lock_in_seconds"]),
                )
                self._json_response(
                    201,
                    {
                        "event_id": event.event_id,
                        "status": event.status.value,
                        "lock_at": event.lock_at.isoformat(),
                    },
                )
                return

            if path == "/predictions":
                payload = self._read_json()
                prediction = self.system.make_prediction(
                    prediction_id=payload["prediction_id"],
                    user_id=payload["user_id"],
                    event_id=payload["event_id"],
                    selected_option=payload["selected_option"],
                )
                self._json_response(
                    201,
                    {
                        "prediction_id": prediction.prediction_id,
                        "status": prediction.status.value,
                    },
                )
                return

            remainder = self._route_match("/events/")
            if remainder and remainder.endswith("/settle"):
                event_id = remainder[: -len("/settle")]
                payload = self._read_json()
                self.system.settle_event(event_id, payload["result_option"])
                self._json_response(200, {"event_id": event_id, "status": EventStatus.SETTLED.value})
                return

            self._json_response(404, {"error": "not found"})
        except Exception as exc:  # pragma: no cover - mapped to API errors
            self._json_response(400, {"error": str(exc)})

    def do_PATCH(self) -> None:  # noqa: N802
        try:
            remainder = self._route_match("/predictions/")
            if remainder:
                prediction_id = remainder
                payload = self._read_json()
                prediction = self.system.edit_prediction(prediction_id, payload["selected_option"])
                self._json_response(
                    200,
                    {
                        "prediction_id": prediction.prediction_id,
                        "selected_option": prediction.selected_option,
                    },
                )
                return
            self._json_response(404, {"error": "not found"})
        except Exception as exc:  # pragma: no cover
            self._json_response(400, {"error": str(exc)})

    def do_GET(self) -> None:  # noqa: N802
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/events":
                query = parse_qs(parsed.query)
                status_filter = query.get("status", [None])[0]
                events = []
                for event in self.system.events.values():
                    if status_filter and event.status.value != status_filter:
                        continue
                    events.append(
                        {
                            "event_id": event.event_id,
                            "match_id": event.match_id,
                            "model_type": event.model_type.value,
                            "status": event.status.value,
                        }
                    )
                self._json_response(200, {"events": events})
                return

            remainder = self._route_match("/dashboard/")
            if remainder:
                user_id = remainder
                dashboard = self.system.dashboard(user_id)
                self._json_response(200, dashboard)
                return

            self._json_response(404, {"error": "not found"})
        except Exception as exc:  # pragma: no cover
            self._json_response(400, {"error": str(exc)})


def create_server(host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), LivePredictionRequestHandler)


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = create_server(host, port)
    print(f"LivePrediction API serving on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
