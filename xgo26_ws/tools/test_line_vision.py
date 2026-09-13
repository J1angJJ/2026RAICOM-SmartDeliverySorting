#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from xgo26.camera import capture_frame_from_config
from xgo26.config import load_config, resolve_path
from xgo26.line_following import LineTracker, draw_line_debug


def main() -> None:
    parser = argparse.ArgumentParser(description="只测试循迹视觉，不初始化或控制机器狗")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--input", help="读取静态图片；省略时从共享相机服务取一帧")
    parser.add_argument("--output", default="debug/line_debug.jpg")
    args = parser.parse_args()

    import cv2

    config = load_config(args.config)
    if args.input:
        frame = cv2.imread(str(resolve_path(args.input)))
        if frame is None:
            raise SystemExit(f"无法读取图片: {args.input}")
    else:
        line_camera = config["line_following"].get("camera", {})
        ok, frame = capture_frame_from_config(
            config["camera"],
            stream=str(line_camera.get("stream", "lores")),
            width=int(line_camera.get("width", 320)),
            height=int(line_camera.get("height", 240)),
        )
        if not ok or frame is None:
            raise SystemExit("无法从共享相机服务读取画面")

    tracker = LineTracker(config["line_following"])
    detection = tracker.process(frame)
    debug = draw_line_debug(frame, detection, tracker.last_mask, config["line_following"])
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), debug):
        raise SystemExit(f"无法保存调试图: {output}")
    print(detection.summary() if detection is not None else "line lost")
    print(f"debug image: {output}")


if __name__ == "__main__":
    main()
