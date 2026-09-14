#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from xgo26.config import load_config
from xgo26.robot import Robot


MOTOR_IDS = [11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 42, 43, 51, 52, 53]
IMU_FIELDS = [
    "accel_x",
    "accel_y",
    "accel_z",
    "gyro_x",
    "gyro_y",
    "gyro_z",
    "roll",
    "pitch",
    "yaw",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="只读检查 XGO 下位机 IMU 和舵机编码器反馈")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--interval", type=float, default=0.2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.samples < 1 or args.interval < 0:
        raise SystemExit("--samples 必须大于 0，--interval 不能小于 0")

    config = load_config(args.config)
    robot_cfg = config["robot"]
    robot = Robot(
        serial_port=robot_cfg.get("serial_port", "/dev/ttyAMA0"),
        model=robot_cfg.get("model", "auto"),
    )
    try:
        result = {
            "battery_percent": robot.read_battery(),
            "motor_angles_deg": _motor_values(robot.read_motors()),
            "samples": [],
        }
        for index in range(args.samples):
            imu = robot.read_imu()
            result["samples"].append(
                {
                    "index": index,
                    "pose_deg": {
                        "roll": robot.read_roll(),
                        "pitch": robot.read_pitch(),
                        "yaw": robot.read_yaw(),
                    },
                    "imu": _imu_values(imu),
                }
            )
            if index + 1 < args.samples:
                time.sleep(args.interval)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        robot.close()


def _motor_values(values: list[float]) -> dict[str, float] | dict[str, object]:
    if len(values) != len(MOTOR_IDS):
        return {"ok": False, "count": len(values), "values": values}
    return {str(motor_id): value for motor_id, value in zip(MOTOR_IDS, values)}


def _imu_values(values: list[float]) -> dict[str, float] | dict[str, object]:
    if len(values) != len(IMU_FIELDS):
        return {"ok": False, "count": len(values), "values": values}
    decoded = {name: value for name, value in zip(IMU_FIELDS, values)}
    finite = all(math.isfinite(value) for value in values)
    plausible = (
        all(abs(decoded[name]) <= 40 for name in IMU_FIELDS[:3])
        and all(abs(decoded[name]) <= 2500 for name in IMU_FIELDS[3:6])
        and all(abs(decoded[name]) <= 10 for name in IMU_FIELDS[6:])
    )
    if finite and plausible:
        return {"ok": True, **decoded}
    return {
        "ok": False,
        "reason": "当前固件不兼容 xgolib.read_imu() 批量解析",
        "values": decoded,
    }


if __name__ == "__main__":
    main()
