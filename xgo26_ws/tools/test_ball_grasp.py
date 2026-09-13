#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from xgo26.actions import align_ball, grasp_once, prepare_for_grasp
from xgo26.camera import capture_frame_from_config
from xgo26.config import load_config, resolve_path
from xgo26.motion import Motion
from xgo26.perception import detect_colored_ball, save_ball_debug_image
from xgo26.robot import Robot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="分段测试红/蓝球检测、对准和抓取")
    parser.add_argument(
        "mode",
        choices=["detect", "align", "grasp-once", "catch"],
        help="detect 只拍照识别；align 只移动对准；grasp-once 只执行夹爪；catch 对准后抓取",
    )
    parser.add_argument("--color", choices=["red", "blue"], default="red")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--dry-run", action="store_true", help="只打印硬件动作")
    parser.add_argument("--save-image", action="store_true", help="保存带目标点和检测圆的调试图")
    return parser.parse_args()


def detect_once(color: str, config: dict, save_image: bool) -> bool:
    camera_cfg = config["camera"]
    grasp_cfg = config.get("grasp", {})
    ok, frame = capture_frame_from_config(
        camera_cfg,
        stream=str(grasp_cfg.get("camera_stream", "lores")),
        width=int(grasp_cfg.get("camera_width", 320)),
        height=int(grasp_cfg.get("camera_height", 240)),
        warmup_frames=int(grasp_cfg.get("warmup_frames", 2)),
    )
    if not ok:
        print("[ball-test] camera capture failed")
        return False

    threshold = config["ball_thresholds_lab"][color]
    detection = detect_colored_ball(frame, color, threshold)
    if detection is None:
        print(f"[ball-test] {color} ball not found")
    else:
        target_x = float(grasp_cfg.get("target_x", 0.0))
        target_y = float(grasp_cfg.get("target_y", -0.85))
        tolerance_x = float(grasp_cfg.get("tolerance_x", 0.15))
        tolerance_y = float(grasp_cfg.get("tolerance_y", 0.18))
        centered = detection.centered(target_x, target_y, tolerance_x, tolerance_y)
        print(f"[ball-test] {detection.summary()} centered={centered}")

    if save_image:
        debug_dir = resolve_path(grasp_cfg.get("debug_dir", "logs/ball_debug"))
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output = debug_dir / f"{stamp}-{color}.jpg"
        path = save_ball_debug_image(
            frame,
            output,
            detection,
            target_x=float(grasp_cfg.get("target_x", 0.0)),
            target_y=float(grasp_cfg.get("target_y", -0.85)),
        )
        print(f"[ball-test] saved {path}")

    return detection is not None


def main() -> None:
    args = parse_args()
    config = load_config(args.config)

    if args.mode == "detect":
        raise SystemExit(0 if detect_once(args.color, config, args.save_image) else 1)

    robot = Robot(config["robot"].get("serial_port", "/dev/ttyAMA0"), dry_run=args.dry_run)
    motion = Motion(
        robot,
        config["robot"].get("drive", {}),
        config.get("camera", {}),
        config.get("line_following", {}),
    )

    if args.mode == "align":
        if not args.dry_run:
            prepare_for_grasp(robot)
        raise SystemExit(0 if align_ball(robot, motion, args.color, config) else 1)

    if args.mode == "grasp-once":
        grasp_once(robot)
        return

    if args.mode == "catch":
        if not args.dry_run:
            prepare_for_grasp(robot)
        aligned = align_ball(robot, motion, args.color, config)
        if aligned:
            grasp_once(robot)
        else:
            print("[ball-test] align failed, skip grasp-once")
        raise SystemExit(0 if aligned else 1)


if __name__ == "__main__":
    main()
