from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .mission import MissionRunner
from .motion import Motion
from .robot import Robot


class RuntimeState:
    def __init__(self, config: dict, dry_run: bool = False):
        self.config = config
        self.dry_run = dry_run
        self.robot = Robot(
            serial_port=config["robot"].get("serial_port", "/dev/ttyAMA0"),
            model=config["robot"].get("model", "auto"),
            dry_run=dry_run,
        )
        self.motion = Motion(self.robot)
        self.lock = threading.Lock()
        self.job_name = "idle"
        self.job_started_at: float | None = None
        self.job_error = ""
        self.job_thread: threading.Thread | None = None

    def initialize(self) -> None:
        self.robot.initialize_control_mode(self.config["robot"].get("control", {}))

    def status(self) -> dict[str, Any]:
        running = self.job_thread is not None and self.job_thread.is_alive()
        return {
            "ok": True,
            "running": running,
            "job": self.job_name,
            "job_started_at": self.job_started_at,
            "job_error": self.job_error,
            "dry_run": self.dry_run,
        }

    def start_square(self, payload: dict[str, Any]) -> bool:
        square_cfg = self.config.get("square_test", {})

        def job() -> None:
            self.motion.drive_square(
                side_cm=float(payload.get("side_cm", square_cfg.get("side_cm", 50))),
                speed=float(payload.get("speed", square_cfg.get("speed", 18))),
                turn_direction=str(payload.get("turn_direction", square_cfg.get("turn_direction", "left"))),
                settle_seconds=float(payload.get("settle_seconds", square_cfg.get("settle_seconds", 0.5))),
                use_builtin_distance=bool(payload.get("use_builtin_distance", square_cfg.get("use_builtin_distance", True))),
                forward_seconds=payload.get("forward_seconds", square_cfg.get("forward_seconds")),
                distance_scale=float(payload.get("distance_scale", square_cfg.get("distance_scale", 1.0))),
            )

        return self._start_job("square", job)

    def start_mission(self, payload: dict[str, Any]) -> bool:
        use_expected = bool(payload.get("use_expected", False))

        def job() -> None:
            runner = MissionRunner(
                self.config,
                dry_run=self.dry_run,
                use_expected=use_expected,
                robot=self.robot,
                motion=self.motion,
            )
            runner.run()

        return self._start_job("mission", job)

    def stop(self) -> None:
        self.robot.stop()

    def _start_job(self, name: str, target: Any) -> bool:
        with self.lock:
            if self.job_thread is not None and self.job_thread.is_alive():
                return False
            self.job_name = name
            self.job_started_at = time.time()
            self.job_error = ""
            self.job_thread = threading.Thread(target=self._run_job, args=(target,), daemon=True)
            self.job_thread.start()
            return True

    def _run_job(self, target: Any) -> None:
        try:
            target()
        except Exception as exc:
            self.job_error = str(exc)
            print(f"[server] job failed: {exc}")
        finally:
            self.robot.stop()
            self.job_name = "idle"


def make_handler(state: RuntimeState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/health":
                self._send_json(state.status())
                return
            self._send_json({"ok": False, "error": "unknown endpoint"}, status=404)

        def do_POST(self) -> None:
            payload = self._read_json()
            if self.path == "/square":
                started = state.start_square(payload)
                status = 202 if started else 409
                self._send_json({**state.status(), "ok": started}, status=status)
                return
            if self.path == "/mission":
                started = state.start_mission(payload)
                status = 202 if started else 409
                self._send_json({**state.status(), "ok": started}, status=status)
                return
            if self.path == "/stop":
                state.stop()
                self._send_json({**state.status(), "ok": True})
                return
            self._send_json({"ok": False, "error": "unknown endpoint"}, status=404)

        def log_message(self, fmt: str, *args: Any) -> None:
            print(f"[server] {self.address_string()} {fmt % args}")

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                return {}
            raw = self.rfile.read(length)
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))

        def _send_json(self, data: dict[str, Any], status: int = 200) -> None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def serve(config: dict, host: str = "0.0.0.0", port: int = 8767, dry_run: bool = False) -> None:
    state = RuntimeState(config, dry_run=dry_run)
    state.initialize()
    server = ThreadingHTTPServer((host, port), make_handler(state))
    print(f"[server] listening on {host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[server] interrupted")
    finally:
        state.stop()
        server.server_close()
