#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from xgo26.competition_drive import CompetitionDrive
from xgo26.config import load_config
from xgo26.robot import Robot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="低头步态单步微调测试（单次最长 0.5 秒）")
    parser.add_argument(
        "direction",
        choices=["left", "right", "shift-left", "shift-right"],
    )
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--turn-speed", type=float, default=20.0)
    parser.add_argument("--lateral-speed", type=float, default=8.0)
    parser.add_argument("--forward", type=float, default=0.0, help="设为正值可测试前进弧线")
    parser.add_argument("--seconds", type=float, default=0.18)
    parser.add_argument("--posture", default="view_down")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 0 < args.seconds <= 0.5:
        raise SystemExit("--seconds 必须在 (0, 0.5] 范围内")

    config = load_config(args.config)
    robot_cfg = config["robot"]
    robot = Robot(
        serial_port=robot_cfg.get("serial_port", "/dev/ttyAMA0"),
        model=robot_cfg.get("model", "auto"),
    )
    drive = CompetitionDrive(robot, robot_cfg.get("drive", {}))
    yaw = 0.0
    lateral = 0.0
    if args.direction == "left":
        yaw = abs(args.turn_speed)
    elif args.direction == "right":
        yaw = -abs(args.turn_speed)
    elif args.direction == "shift-left":
        lateral = abs(args.lateral_speed)
    else:
        lateral = -abs(args.lateral_speed)

    try:
        robot.initialize_control_mode(robot_cfg.get("control", {}))
        before_yaw = robot.read_yaw()
        drive.gait_drive(args.forward, yaw, posture=args.posture, lateral=lateral)
        time.sleep(args.seconds)
        drive.stop()
        time.sleep(0.25)
        print(
            f"direction={args.direction} seconds={args.seconds:.2f} "
            f"yaw={before_yaw:.1f}->{robot.read_yaw():.1f} pitch={robot.read_pitch():.1f}"
        )
    finally:
        drive.stop()
        robot.close()


if __name__ == "__main__":
    main()
