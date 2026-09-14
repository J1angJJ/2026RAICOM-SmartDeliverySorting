#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import signal
import sys
import time
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from xgo26.competition_drive import CompetitionDrive
from xgo26.config import load_config
from xgo26.robot import Robot
from xgo26.terminal_keys import TerminalKeys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="通过 SSH 终端按键连续控制 XGO26")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--speed", type=float, default=8.0, help="四轮前后速度")
    parser.add_argument("--turn-speed", type=float, default=20.0, help="正常步态转向速度")
    parser.add_argument("--gait-forward", type=float, default=8.0, help="低头步态弧线前进速度")
    parser.add_argument("--gait-turn", type=float, default=8.0, help="低头步态微调转向速度")
    parser.add_argument("--rate", type=float, default=10.0, help="指令重复发送频率")
    parser.add_argument("--deadman", type=float, default=0.65, help="停止接收按键后的停车延迟")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.rate <= 0 or args.deadman <= 0:
        raise SystemExit("--rate 和 --deadman 必须大于 0")
    config = load_config(args.config)
    robot_cfg = config["robot"]
    robot = Robot(
        serial_port=robot_cfg.get("serial_port", "/dev/ttyAMA0"),
        model=robot_cfg.get("model", "auto"),
        dry_run=args.dry_run,
    )
    drive = CompetitionDrive(robot, robot_cfg.get("drive", {}))
    speed = min(abs(args.speed), drive.forward_input_max)
    turn_speed = min(abs(args.turn_speed), drive.turn_input_max)
    gait_forward = min(abs(args.gait_forward), drive.forward_input_max)
    gait_turn = min(abs(args.gait_turn), drive.turn_input_max)
    posture = "neutral"
    command: Callable[[], None] | None = None
    command_name = "stop"
    deadline = 0.0
    period = 1.0 / args.rate

    def interrupt_on_disconnect(signum: int, frame: object) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGHUP, interrupt_on_disconnect)
    signal.signal(signal.SIGTERM, interrupt_on_disconnect)

    print("[teleop] 按住按键才持续运动，松开后自动停车")
    print("[teleop] W/S=四轮前后  A/D=低头步态前进弧线  Q/E=低头步态原地微调")
    print("[teleop] J/L=正常步态左转/右转（会先恢复中立姿态）")
    print("[teleop] 1/2/3=抬头/中立/低头  +/-=调速  空格=停车  X=退出")

    def set_motion(name: str, action: Callable[[], None]) -> None:
        nonlocal command, command_name, deadline
        command = action
        command_name = name
        deadline = time.monotonic() + args.deadman

    def wheel_motion(forward: float, yaw: float = 0.0) -> None:
        drive.use_wheel_posture(posture)
        drive.wheel_drive(forward, yaw)

    def gait_motion(forward: float, yaw: float) -> None:
        drive.gait_drive(forward, yaw, posture=posture)

    def show_status() -> None:
        print(
            f"\r[teleop] command={command_name:<14} posture={posture:<9} "
            f"speed={speed:>4.1f} wheels={drive.last_wheel_values}   ",
            end="",
            flush=True,
        )

    try:
        robot.initialize_control_mode(robot_cfg.get("control", {}))
        drive.use_wheel_posture(posture)
        with TerminalKeys() as keys:
            while True:
                key = keys.read(period)
                lower = key.lower() if key else ""
                if lower == "x":
                    break
                if key == " ":
                    command = None
                    command_name = "stop"
                    drive.stop()
                elif lower == "w":
                    set_motion("wheel-forward", lambda: wheel_motion(speed))
                elif lower == "s":
                    set_motion("wheel-backward", lambda: wheel_motion(-speed))
                elif lower == "a":
                    set_motion("gait-arc-left", lambda: gait_motion(gait_forward, gait_turn))
                elif lower == "d":
                    set_motion("gait-arc-right", lambda: gait_motion(gait_forward, -gait_turn))
                elif lower == "q":
                    set_motion("gait-fine-left", lambda: gait_motion(0, gait_turn))
                elif lower == "e":
                    set_motion("gait-fine-right", lambda: gait_motion(0, -gait_turn))
                elif lower == "j":
                    set_motion("gait-left", lambda: drive.turn(turn_speed))
                elif lower == "l":
                    set_motion("gait-right", lambda: drive.turn(-turn_speed))
                elif key in {"1", "2", "3"}:
                    command = None
                    command_name = "stop"
                    drive.stop()
                    posture = {"1": "view_up", "2": "neutral", "3": "view_down"}[key]
                    drive.use_wheel_posture(posture)
                elif key in {"+", "="}:
                    speed = min(drive.forward_input_max, speed + 1)
                elif key in {"-", "_"}:
                    speed = max(1.0, speed - 1)

                now = time.monotonic()
                if command is not None and now <= deadline:
                    command()
                elif command is not None:
                    command = None
                    command_name = "stop"
                    drive.stop()
                show_status()
    except KeyboardInterrupt:
        pass
    finally:
        print("\n[teleop] stopping")
        try:
            drive.stop()
        finally:
            try:
                drive.use_gait_mode()
            finally:
                try:
                    robot.stop()
                finally:
                    robot.close()


if __name__ == "__main__":
    main()
