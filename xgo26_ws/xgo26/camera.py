from __future__ import annotations

import time
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen


class CameraServiceClient:
    """Read fresh BGR frames from the single-owner camera service."""

    def __init__(self, base_url: str, timeout: float = 2.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = max(0.1, timeout)
        self._sequences = {"main": -1, "lores": -1}
        self.last_frame_info: dict[str, Any] = {}

    def read(
        self,
        stream: str = "lores",
        width: int | None = None,
        height: int | None = None,
    ) -> Any:
        import numpy as np

        if stream not in self._sequences:
            raise ValueError(f"unknown camera stream: {stream}")
        query = urlencode({"stream": stream, "after": self._sequences[stream]})
        try:
            with urlopen(f"{self.base_url}/frame.raw?{query}", timeout=self.timeout) as response:
                raw = response.read()
                source_width = int(response.headers["X-Frame-Width"])
                source_height = int(response.headers["X-Frame-Height"])
                channels = int(response.headers["X-Frame-Channels"])
                sequence = int(response.headers["X-Frame-Sequence"])
                self._sequences[stream] = sequence
                self.last_frame_info = {
                    "stream": stream,
                    "sequence": sequence,
                    "sensor_timestamp_ns": _optional_int(
                        response.headers.get("X-Sensor-Timestamp-Ns")
                    ),
                    "exposure_time_us": _optional_int(
                        response.headers.get("X-Exposure-Time-Us")
                    ),
                    "analogue_gain": _optional_float(
                        response.headers.get("X-Analogue-Gain")
                    ),
                    "colour_gains": _optional_float_list(
                        response.headers.get("X-Colour-Gains")
                    ),
                    "lux": _optional_float(response.headers.get("X-Lux")),
                }
        except HTTPError as exc:
            if exc.code != 404:
                raise
            return self._read_mjpeg_frame(stream, width, height)
        expected = source_width * source_height * channels
        if len(raw) != expected:
            raise RuntimeError(f"camera frame size mismatch: got {len(raw)}, expected {expected}")
        image = np.frombuffer(raw, dtype=np.uint8).reshape(
            source_height, source_width, channels
        ).copy()
        if width and height and (source_width != width or source_height != height):
            import cv2

            image = cv2.resize(image, (int(width), int(height)), interpolation=cv2.INTER_AREA)
        return image

    def _read_mjpeg_frame(
        self,
        stream: str,
        width: int | None,
        height: int | None,
    ) -> Any:
        import cv2
        import numpy as np

        query = urlencode({"stream": stream})
        with urlopen(f"{self.base_url}/stream.mjpg?{query}", timeout=self.timeout) as response:
            data = bytearray()
            while len(data) < 4 * 1024 * 1024:
                chunk = response.read(4096)
                if not chunk:
                    break
                data.extend(chunk)
                start = data.find(b"\xff\xd8")
                end = data.find(b"\xff\xd9", start + 2) if start >= 0 else -1
                if start >= 0 and end >= 0:
                    encoded = np.frombuffer(data[start : end + 2], dtype=np.uint8)
                    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
                    if image is None:
                        break
                    if width and height and image.shape[1::-1] != (width, height):
                        image = cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)
                    self.last_frame_info = {"stream": stream, "source": "mjpeg"}
                    return image
        raise RuntimeError("camera MJPEG stream did not yield a JPEG frame")


class CameraReader:
    def __init__(
        self,
        camera_index: int = 0,
        width: int = 640,
        height: int = 480,
        warmup_frames: int = 5,
        *,
        source: str = "direct",
        service_url: str = "http://127.0.0.1:8090",
        stream: str = "lores",
        request_timeout: float = 2.0,
    ):
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.warmup_frames = warmup_frames
        self.source = source
        self.service_url = service_url
        self.stream = stream
        self.request_timeout = request_timeout
        self._service: CameraServiceClient | None = None
        self._picam2: Any | None = None
        self._cap: Any | None = None
        self._mode = ""
        self._first_frame: Any | None = None

    def __enter__(self) -> "CameraReader":
        if self.source in {"service", "auto"} and self._open_service():
            return self
        if self.source == "service":
            raise RuntimeError(f"无法连接相机服务: {self.service_url}")
        if self._open_picamera2():
            return self
        if self._open_opencv():
            return self
        raise RuntimeError("无法打开摄像头")

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def read(self) -> Any | None:
        if self._first_frame is not None:
            frame = self._first_frame
            self._first_frame = None
            return frame
        if self._mode == "service" and self._service is not None:
            try:
                return self._service.read(self.stream, self.width, self.height)
            except Exception as exc:
                print(f"[camera] service read failed: {exc}")
                return None
        if self._mode == "picamera2" and self._picam2 is not None:
            frame = self._picam2.capture_array()
            if frame is None:
                return None
            # Picamera2 RGB888 arrays use OpenCV's BGR byte order in memory.
            return frame
        if self._mode == "opencv" and self._cap is not None:
            ok, frame = self._cap.read()
            return frame if ok else None
        return None

    def close(self) -> None:
        self._service = None
        self._first_frame = None
        if self._picam2 is not None:
            try:
                self._picam2.stop()
                self._picam2.close()
            except Exception:
                pass
            self._picam2 = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._mode = ""

    def _open_service(self) -> bool:
        try:
            client = CameraServiceClient(self.service_url, self.request_timeout)
            self._first_frame = client.read(self.stream, self.width, self.height)
            self._service = client
            self._mode = "service"
            return True
        except Exception as exc:
            print(f"[camera] service unavailable: {exc}")
            return False

    def _open_picamera2(self) -> bool:
        try:
            from picamera2 import Picamera2
        except Exception:
            return False
        picam2 = None
        try:
            picam2 = Picamera2(self.camera_index)
            config = picam2.create_preview_configuration(
                main={"size": (self.width, self.height), "format": "RGB888"}
            )
            picam2.configure(config)
            picam2.start()
            time.sleep(0.4)
            self._picam2 = picam2
            self._mode = "picamera2"
            for _ in range(max(0, self.warmup_frames - 1)):
                self.read()
            return True
        except Exception as exc:
            print(f"[camera] Picamera2 failed: {exc}")
            if picam2 is not None:
                try:
                    picam2.close()
                except Exception:
                    pass
            return False

    def _open_opencv(self) -> bool:
        try:
            import cv2
        except Exception as exc:
            print(f"[camera] cv2 unavailable: {exc}")
            return False
        backends = [cv2.CAP_V4L2] if hasattr(cv2, "CAP_V4L2") else []
        backends.append(0)
        for backend in backends:
            cap = cv2.VideoCapture(self.camera_index, backend)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            if hasattr(cv2, "CAP_PROP_FOURCC"):
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc("M", "J", "P", "G"))
            if cap.isOpened():
                self._cap = cap
                self._mode = "opencv"
                for _ in range(max(0, self.warmup_frames)):
                    self.read()
                return True
            cap.release()
        return False


def capture_frame(
    camera_index: int = 0,
    width: int = 640,
    height: int = 480,
    warmup_frames: int = 5,
    *,
    source: str = "direct",
    service_url: str = "http://127.0.0.1:8090",
    stream: str = "lores",
    request_timeout: float = 2.0,
) -> tuple[bool, Any | None]:
    try:
        with CameraReader(
            camera_index,
            width,
            height,
            warmup_frames,
            source=source,
            service_url=service_url,
            stream=stream,
            request_timeout=request_timeout,
        ) as reader:
            frame = reader.read()
            if frame is not None:
                return True, frame
    except Exception as exc:
        print(f"[camera] capture failed: {exc}")
    return False, None


def capture_frame_from_config(
    camera_config: dict,
    *,
    stream: str = "lores",
    width: int | None = None,
    height: int | None = None,
    warmup_frames: int | None = None,
) -> tuple[bool, Any | None]:
    try:
        with camera_reader_from_config(
            camera_config,
            stream=stream,
            width=width,
            height=height,
            warmup_frames=warmup_frames,
        ) as reader:
            frame = reader.read()
            return (frame is not None), frame
    except Exception as exc:
        print(f"[camera] capture failed: {exc}")
        return False, None


def camera_reader_from_config(
    camera_config: dict,
    *,
    stream: str = "lores",
    width: int | None = None,
    height: int | None = None,
    warmup_frames: int | None = None,
) -> CameraReader:
    stream_config = camera_config.get(stream, {})
    return CameraReader(
        camera_index=int(camera_config.get("index", 0)),
        width=int(
            width
            if width is not None
            else stream_config.get("width", camera_config.get("width", 640))
        ),
        height=int(
            height
            if height is not None
            else stream_config.get("height", camera_config.get("height", 480))
        ),
        warmup_frames=int(
            warmup_frames if warmup_frames is not None else camera_config.get("warmup_frames", 5)
        ),
        source=str(camera_config.get("source", "direct")),
        service_url=str(camera_config.get("service_url", "http://127.0.0.1:8090")),
        stream=stream,
        request_timeout=float(camera_config.get("request_timeout", 2.0)),
    )


def _optional_int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _optional_float(value: str | None) -> float | None:
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def _optional_float_list(value: str | None) -> list[float] | None:
    if value is None:
        return None
    try:
        return [float(item) for item in value.split(",")]
    except ValueError:
        return None
