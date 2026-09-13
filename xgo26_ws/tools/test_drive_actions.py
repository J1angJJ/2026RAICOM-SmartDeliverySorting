#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from xgo26.config import load_config
from xgo26.motion import Motion
from xgo26.robot import Robot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="单独测试比赛前进和转向动作")
    parser.add_argument("action", choices=["forward", "backward", "turn-left", "turn-right"])
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--speed", type=float, default=8, help="前进/后退速度参数")
    parser.add_argument("--seconds", type=float, default=1.0, help="前进/后退持续时间")
    parser.add_argument("--angle", type=float, default=30, help="转向测试角度")
    parser.add_argument("--dry-run", action="store_true", help="只打印硬件动作")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    robot = Robot(
        serial_port=config["robot"].get("serial_port", "/dev/ttyAMA0"),
        model=config["robot"].get("model", "auto"),
        dry_run=args.dry_run,
    )
    motion = Motion(
        robot,
        config["robot"].get("drive", {}),
        config.get("camera", {}),
        config.get("line_following", {}),
    )

    try:
        robot.initialize_control_mode(config["robot"].get("control", {}))
        motion.reset_yaw_origin()
        if args.action == "forward":
            motion.move("x", abs(args.speed), args.seconds)
        elif args.action == "backward":
            motion.move("x", -abs(args.speed), args.seconds)
        elif args.action == "turn-left":
            motion.turn_to(abs(args.angle))
        else:
            motion.turn_to(-abs(args.angle))
    finally:
        motion.stop()
        motion.drive.use_gait_mode()
        robot.stop()


if __name__ == "__main__":
    main()
