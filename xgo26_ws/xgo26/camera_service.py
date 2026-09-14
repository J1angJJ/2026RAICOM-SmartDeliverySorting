from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from http import server
from socketserver import ThreadingMixIn
from typing import Any
from urllib.parse import parse_qs, urlsplit


@dataclass(frozen=True)
class CameraFrame:
    image: Any
    sequence: int
    sensor_timestamp_ns: int
    captured_monotonic: float
    metadata: dict[str, Any]


class CameraHub:
    """Own Picamera2 once and fan the latest frame out to every consumer."""

    def __init__(self, config: dict):
        self.config = config
        self._picam2: Any | None = None
        self._frames: dict[str, CameraFrame] = {}
        self._condition = threading.Condition()
        self._running = False
        self._thread: threading.Thread | None = None
        self._error = ""
        self._started_monotonic = 0.0

    def start(self) -> None:
        if self._running:
            return
        from picamera2 import Picamera2

        sensor_cfg = self.config.get("sensor", {})
        main_cfg = self.config.get("main", {})
        lores_cfg = self.config.get("lores", {})
        fps = float(self.config.get("fps", 30))

        self._picam2 = Picamera2(int(self.config.get("index", 0)))
        video_config = self._picam2.create_video_configuration(
            main={
                "size": _size(main_cfg, (1296, 972)),
                "format": "RGB888",
            },
            lores={
                "size": _size(lores_cfg, (640, 480)),
                "format": "YUV420",
            },
            controls=_camera_controls(self.config, fps),
            buffer_count=max(3, int(self.config.get("buffer_count", 4))),
            display=None,
            encode=None,
            sensor={
                "output_size": _size(sensor_cfg, (1296, 972)),
                "bit_depth": int(sensor_cfg.get("bit_depth", 10)),
            },
        )
        self._picam2.configure(video_config)
        self._picam2.start()
        self._running = True
        self._started_monotonic = time.monotonic()
        self._thread = threading.Thread(target=self._capture_loop, name="camera-capture", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._running = False
        with self._condition:
            self._condition.notify_all()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._picam2 is not None:
            try:
                self._picam2.stop()
            finally:
                self._picam2.close()
            self._picam2 = None

    def latest(self, stream: str, after_sequence: int = -1, timeout: float = 1.0) -> CameraFrame | None:
        if stream not in {"main", "lores"}:
            raise ValueError(f"unknown camera stream: {stream}")
        deadline = time.monotonic() + max(0.0, timeout)
        with self._condition:
            while self._running:
                frame = self._frames.get(stream)
                if frame is not None and frame.sequence > after_sequence:
                    return frame
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._condition.wait(remaining)
            frame = self._frames.get(stream)
            if frame is not None and frame.sequence > after_sequence:
                return frame
            return None

    def status(self) -> dict[str, Any]:
        now = time.monotonic()
        with self._condition:
            frames = {
                name: {
                    "sequence": frame.sequence,
                    "width": int(frame.image.shape[1]),
                    "height": int(frame.image.shape[0]),
                    "age_ms": round((now - frame.captured_monotonic) * 1000, 1),
                    "exposure_time_us": frame.metadata.get("ExposureTime"),
                    "analogue_gain": frame.metadata.get("AnalogueGain"),
                }
                for name, frame in self._frames.items()
            }
            error = self._error
        return {
            "ok": self._running and bool(frames) and not error,
            "running": self._running,
            "uptime_seconds": round(max(0.0, now - self._started_monotonic), 1),
            "error": error,
            "frames": frames,
        }

    def _capture_loop(self) -> None:
        import cv2

        sequence = 0
        while self._running and self._picam2 is not None:
            request = None
            try:
                request = self._picam2.capture_request()
                main_bgr = request.make_array("main")
                lores_yuv = request.make_array("lores")
                metadata = request.get_metadata()
                frame_metadata = {
                    key: _json_value(metadata.get(key))
                    for key in (
                        "ExposureTime",
                        "AnalogueGain",
                        "ColourGains",
                        "Lux",
                        "SensorBlackLevels",
                    )
                    if metadata.get(key) is not None
                }
                captured = time.monotonic()
                sequence += 1
                # Picamera2 RGB888 arrays use OpenCV's BGR byte order in memory.
                lores_bgr = cv2.cvtColor(lores_yuv, cv2.COLOR_YUV2BGR_I420)
                sensor_timestamp = int(metadata.get("SensorTimestamp", 0))
                with self._condition:
                    self._frames["main"] = CameraFrame(
                        main_bgr, sequence, sensor_timestamp, captured, frame_metadata
                    )
                    self._frames["lores"] = CameraFrame(
                        lores_bgr, sequence, sensor_timestamp, captured, frame_metadata
                    )
                    self._error = ""
                    self._condition.notify_all()
            except Exception as exc:
                with self._condition:
                    self._error = str(exc)
                    self._condition.notify_all()
                print(f"[camera-service] capture failed: {exc}")
                time.sleep(0.1)
            finally:
                if request is not None:
                    request.release()


class CameraHTTPServer(ThreadingMixIn, server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], hub: CameraHub, jpeg_quality: int = 80):
        self.hub = hub
        self.jpeg_quality = max(30, min(95, int(jpeg_quality)))
        super().__init__(address, CameraRequestHandler)


class CameraRequestHandler(server.BaseHTTPRequestHandler):
    server: CameraHTTPServer

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.path in {"/", "/index.html"}:
            self._send_index()
            return
        if parsed.path == "/health":
            self._send_json(self.server.hub.status())
            return

        query = parse_qs(parsed.query)
        stream = query.get("stream", ["lores"])[0]
        try:
            after_sequence = int(query.get("after", ["-1"])[0])
        except ValueError:
            self.send_error(400, "invalid after sequence")
            return
        if parsed.path == "/frame.raw":
            self._send_raw(stream, after_sequence)
            return
        if parsed.path in {"/frame.jpg", "/snapshot.jpg"}:
            self._send_jpeg(stream, after_sequence)
            return
        if parsed.path == "/stream.mjpg":
            self._send_mjpeg(stream)
            return
        self.send_error(404)

    def _send_index(self) -> None:
        body = b"<html><body><img src='/stream.mjpg?stream=lores' style='max-width:100%;height:auto'></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_common_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_raw(self, stream: str, after_sequence: int) -> None:
        frame = self._get_frame(stream, after_sequence)
        if frame is None:
            return
        image = frame.image
        body = image.tobytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Frame-Width", str(image.shape[1]))
        self.send_header("X-Frame-Height", str(image.shape[0]))
        self.send_header("X-Frame-Channels", str(image.shape[2]))
        self.send_header("X-Frame-Format", "BGR888")
        self.send_header("X-Frame-Sequence", str(frame.sequence))
        self.send_header("X-Sensor-Timestamp-Ns", str(frame.sensor_timestamp_ns))
        self._send_capture_headers(frame)
        self._send_common_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_jpeg(self, stream: str, after_sequence: int) -> None:
        frame = self._get_frame(stream, after_sequence)
        if frame is None:
            return
        body = self._encode_jpeg(frame.image)
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Frame-Sequence", str(frame.sequence))
        self.send_header("X-Sensor-Timestamp-Ns", str(frame.sensor_timestamp_ns))
        self._send_capture_headers(frame)
        self._send_common_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_mjpeg(self, stream: str) -> None:
        if stream not in {"main", "lores"}:
            self.send_error(400, "unknown stream")
            return
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=FRAME")
        self._send_common_headers()
        self.end_headers()
        sequence = -1
        try:
            while True:
                frame = self.server.hub.latest(stream, after_sequence=sequence, timeout=2.0)
                if frame is None or frame.sequence == sequence:
                    continue
                sequence = frame.sequence
                body = self._encode_jpeg(frame.image)
                self.wfile.write(b"--FRAME\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"))
                self.wfile.write(body)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _get_frame(self, stream: str, after_sequence: int = -1) -> CameraFrame | None:
        try:
            frame = self.server.hub.latest(
                stream, after_sequence=after_sequence, timeout=1.0
            )
        except ValueError as exc:
            self.send_error(400, str(exc))
            return None
        if frame is None:
            self.send_error(503, "camera frame unavailable")
        return frame

    def _encode_jpeg(self, image: Any) -> bytes:
        import cv2

        ok, encoded = cv2.imencode(
            ".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, self.server.jpeg_quality]
        )
        if not ok:
            raise RuntimeError("JPEG encode failed")
        return encoded.tobytes()

    def _send_json(self, value: dict[str, Any]) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(200 if value.get("ok") else 503)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_common_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_common_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")

    def _send_capture_headers(self, frame: CameraFrame) -> None:
        exposure = frame.metadata.get("ExposureTime")
        gain = frame.metadata.get("AnalogueGain")
        colour_gains = frame.metadata.get("ColourGains")
        lux = frame.metadata.get("Lux")
        if exposure is not None:
            self.send_header("X-Exposure-Time-Us", str(exposure))
        if gain is not None:
            self.send_header("X-Analogue-Gain", str(gain))
        if isinstance(colour_gains, list):
            self.send_header("X-Colour-Gains", ",".join(str(value) for value in colour_gains))
        if lux is not None:
            self.send_header("X-Lux", str(lux))

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[camera-service] {self.address_string()} {fmt % args}")


def serve_camera(config: dict, host: str = "0.0.0.0", port: int = 8090) -> None:
    hub = CameraHub(config)
    hub.start()
    httpd: CameraHTTPServer | None = None
    try:
        httpd = CameraHTTPServer(
            (host, port), hub, jpeg_quality=int(config.get("jpeg_quality", 80))
        )
        print(f"[camera-service] listening on {host}:{port}")
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("[camera-service] interrupted")
    finally:
        if httpd is not None:
            httpd.server_close()
        hub.close()


def _size(config: dict, default: tuple[int, int]) -> tuple[int, int]:
    return int(config.get("width", default[0])), int(config.get("height", default[1]))


def _camera_controls(config: dict, fps: float) -> dict[str, Any]:
    controls: dict[str, Any] = {"FrameRate": fps}
    configured = config.get("controls", {})
    names = {
        "ae_enable": "AeEnable",
        "awb_enable": "AwbEnable",
        "exposure_time_us": "ExposureTime",
        "analogue_gain": "AnalogueGain",
        "colour_gains": "ColourGains",
    }
    for source, target in names.items():
        value = configured.get(source)
        if value is not None:
            controls[target] = tuple(value) if source == "colour_gains" else value
    return controls


def _json_value(value: Any) -> Any:
    if isinstance(value, tuple):
        return list(value)
    if hasattr(value, "tolist"):
        return value.tolist()
    return value
