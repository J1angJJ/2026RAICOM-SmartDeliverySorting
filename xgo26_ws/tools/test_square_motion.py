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
    parser = argparse.ArgumentParser(description="Run a 50cm square motion test")
    parser.add_argument("--config", default="config.json", help="配置文件路径")
    parser.add_argument("--side-cm", type=float, help="正方形边长，默认读取 config.json")
    parser.add_argument("--speed", type=float, help="前进步长/速度参数，默认读取 config.json")
    parser.add_argument(
        "--turn-direction",
        choices=["left", "right"],
        help="转向方向，默认读取 config.json",
    )
    parser.add_argument(
        "--timed",
        action="store_true",
        help="不用厂家 move_x_by，改用定时 move_x；便于对比调试",
    )
    parser.add_argument(
        "--forward-seconds",
        type=float,
        help="--timed 模式下单边前进秒数；不填则按边长和速度估算",
    )
    parser.add_argument("--dry-run", action="store_true", help="只打印动作，不连接硬件")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    square_cfg = config.get("square_test", {})
    robot = Robot(
        serial_port=config["robot"].get("serial_port", "/dev/ttyAMA0"),
        dry_run=args.dry_run,
    )
    motion = Motion(robot)

    try:
        robot.initialize_control_mode(config["robot"].get("control", {}))
        motion.drive_square(
            side_cm=float(args.side_cm if args.side_cm is not None else square_cfg.get("side_cm", 50)),
            speed=float(args.speed if args.speed is not None else square_cfg.get("speed", 18)),
            turn_direction=str(args.turn_direction or square_cfg.get("turn_direction", "left")),
            settle_seconds=float(square_cfg.get("settle_seconds", 0.5)),
            use_builtin_distance=not args.timed and bool(square_cfg.get("use_builtin_distance", True)),
            forward_seconds=args.forward_seconds,
        )
    except KeyboardInterrupt:
        print("[square] interrupted")
        raise
    finally:
        robot.stop()


if __name__ == "__main__":
    main()
