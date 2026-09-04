#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from xgo26.camera import capture_frame
from xgo26.config import load_config


def main() -> None:
    config = load_config()
    cam = config["camera"]
    ok, frame = capture_frame(
        camera_index=int(cam.get("index", 0)),
        width=int(cam.get("width", 640)),
        height=int(cam.get("height", 480)),
        warmup_frames=int(cam.get("warmup_frames", 5)),
    )
    if not ok:
        raise SystemExit("camera failed")
    print(f"camera ok: {frame.shape[1]}x{frame.shape[0]}")


if __name__ == "__main__":
    main()
