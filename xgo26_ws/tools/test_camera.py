#!/usr/bin/env python3
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from xgo26.camera import capture_frame_from_config
from xgo26.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="测试共享相机服务或直接相机")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--stream", choices=["main", "lores"], default="lores")
    parser.add_argument("--direct", action="store_true", help="绕过相机服务直接打开 Picamera2")
    args = parser.parse_args()

    config = load_config(args.config)
    cam = config["camera"]
    if args.direct:
        cam = {**cam, "source": "direct"}
    stream_cfg = cam.get(args.stream, {})
    ok, frame = capture_frame_from_config(
        cam,
        stream=args.stream,
        width=int(stream_cfg.get("width", cam.get("width", 640))),
        height=int(stream_cfg.get("height", cam.get("height", 480))),
    )
    if not ok:
        raise SystemExit("camera failed")
    print(f"camera ok: source={cam.get('source')} stream={args.stream} {frame.shape[1]}x{frame.shape[0]}")


if __name__ == "__main__":
    main()
