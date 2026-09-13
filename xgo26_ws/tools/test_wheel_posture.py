#!/usr/bin/env python3
from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from xgo26.competition_drive import CompetitionDrive
from xgo26.config import load_config
from xgo26.robot import Robot


def main() -> None:
    parser = argparse.ArgumentParser(description="原地测试四轮机身姿态，不让轮子转动")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--pitch", type=float, help="覆盖 view_down 俯仰角，范围 -15 至 15")
    parser.add_argument("--seconds", type=float, default=5.0, help="姿态保持时间")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = load_config(args.config)
    drive_config = deepcopy(config["robot"].get("drive", {}))
    profile = drive_config["wheel_postures"]["view_down"]
    if args.pitch is not None:
        if not -15 <= args.pitch <= 15:
            raise SystemExit("pitch 必须在 -15 至 15 之间")
        profile["pitch"] = args.pitch

    robot = Robot(
        serial_port=config["robot"].get("serial_port", "/dev/ttyAMA0"),
        model=config["robot"].get("model", "auto"),
        dry_run=args.dry_run,
    )
    drive = CompetitionDrive(robot, drive_config)
    try:
        drive.use_wheel_posture("view_down")
        print(
            f"[posture] view_down height={profile['height']} pitch={profile['pitch']} "
            f"hold={max(0.0, args.seconds):.1f}s"
        )
        time.sleep(max(0.0, args.seconds))
    finally:
        drive.stop()
        drive.use_gait_mode()
        robot.stop()


if __name__ == "__main__":
    main()
