from __future__ import annotations

import time
from typing import Any


def capture_frame(
    camera_index: int = 0,
    width: int = 640,
    height: int = 480,
    warmup_frames: int = 5,
) -> tuple[bool, Any | None]:
    frame = _capture_with_picamera2(width, height)
    if frame is not None:
        return True, frame
    frame = _capture_with_opencv(camera_index, width, height, warmup_frames)
    if frame is not None:
        return True, frame
    return False, None


def _capture_with_picamera2(width: int, height: int) -> Any | None:
    try:
        from picamera2 import Picamera2
    except Exception:
        return None

    picam2 = None
    try:
        picam2 = Picamera2()
        config = picam2.create_preview_configuration(
            main={"size": (width, height), "format": "RGB888"}
        )
        picam2.configure(config)
        picam2.start()
        time.sleep(0.4)
        rgb = picam2.capture_array()
        if rgb is None:
            return None
        try:
            import cv2

            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        except Exception:
            return rgb
    except Exception as exc:
        print(f"[camera] Picamera2 failed: {exc}")
        return None
    finally:
        if picam2 is not None:
            try:
                picam2.stop()
                picam2.close()
            except Exception:
                pass


def _capture_with_opencv(
    camera_index: int,
    width: int,
    height: int,
    warmup_frames: int,
) -> Any | None:
    try:
        import cv2
    except Exception as exc:
        print(f"[camera] cv2 unavailable: {exc}")
        return None

    backends = [cv2.CAP_V4L2] if hasattr(cv2, "CAP_V4L2") else []
    backends.append(0)
    for backend in backends:
        cap = cv2.VideoCapture(camera_index, backend)
        try:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            if hasattr(cv2, "CAP_PROP_FOURCC"):
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc("M", "J", "P", "G"))
            if not cap.isOpened():
                continue
            frame = None
            for _ in range(max(1, warmup_frames)):
                ok, current = cap.read()
                if ok and current is not None:
                    frame = current
            return frame
        finally:
            cap.release()
    return None

