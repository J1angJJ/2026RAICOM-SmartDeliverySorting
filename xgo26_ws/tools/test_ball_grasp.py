#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from xgo26.actions import (
    align_ball,
    ball_ready_for_grasp,
    close_grasp_claw,
    grasp_from_body_view,
    grasp_once,
    lower_grasp_arm,
    lower_grasp_body,
    prepare_for_grasp,
    restore_grasp_body,
    retract_grasp_arm,
    stow_grasp_arm,
)
from xgo26.camera import capture_frame_from_config
from xgo26.config import load_config, resolve_path
from xgo26.motion import Motion
from xgo26.perception import detect_colored_ball, save_ball_debug_image
from xgo26.robot import Robot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="分段测试红/蓝球检测、对准和抓取")
    parser.add_argument(
        "mode",
        choices=[
            "detect",
            "align",
            "body-down",
            "arm-down",
            "claw-close",
            "arm-up",
            "body-up",
            "arm-stow",
            "staged",
            "body-grasp",
            "grasp-once",
            "catch",
        ],
        help="分步调整本体/机械臂，或运行完整对准与抓取流程",
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
    detection = detect_colored_ball(
        frame,
        color,
        threshold,
        roi_top_ratio=float(grasp_cfg.get("roi_top_ratio", 0.55)),
    )
    if detection is None:
        print(f"[ball-test] {color} ball not found")
    else:
        target_x = float(grasp_cfg.get("target_x", 0.0))
        target_y = float(grasp_cfg.get("target_y", -0.85))
        tolerance_x = float(grasp_cfg.get("tolerance_x", 0.15))
        tolerance_y = float(grasp_cfg.get("tolerance_y", 0.18))
        centered = detection.centered(target_x, target_y, tolerance_x, tolerance_y)
        ready = ball_ready_for_grasp(detection, config)
        print(f"[ball-test] {detection.summary()} centered={centered} grasp_ready={ready}")

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


def run_staged_grasp(robot: Robot, color: str, config: dict) -> None:
    stages = (
        ("body-down", "本体进入抓取观察姿态", lower_grasp_body),
        ("arm-down", "机械臂张爪并下探", lower_grasp_arm),
        ("claw-close", "闭合夹爪", close_grasp_claw),
        ("arm-up", "机械臂按 53 -> 52 回收", retract_grasp_arm),
        ("body-up", "本体恢复中立姿态", restore_grasp_body),
        ("arm-stow", "机械臂进入携球姿态", stow_grasp_arm),
    )
    print("[ball-test] 单会话分步抓取；等待输入时机器人保持当前状态")
    for name, description, action in stages:
        while True:
            answer = input(
                f"[ball-test] 回车执行 {name}：{description}；"
                "v 检查小球；q 保持当前状态并退出 > "
            )
            if not answer.strip():
                action(robot)
                break
            if answer.strip().lower() == "v":
                detect_once(color, config, save_image=False)
                continue
            if answer.strip().lower() == "q":
                print("[ball-test] 已退出，未复位机器人")
                return
            print("[ball-test] 无效输入，请直接回车或输入 q")
    print("[ball-test] 分步抓取完成")


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

    try:
        if args.mode == "align":
            if not args.dry_run:
                prepare_for_grasp(robot)
            raise SystemExit(0 if align_ball(robot, motion, args.color, config) else 1)

        stages = {
            "body-down": lower_grasp_body,
            "arm-down": lower_grasp_arm,
            "claw-close": close_grasp_claw,
            "arm-up": retract_grasp_arm,
            "body-up": restore_grasp_body,
            "arm-stow": stow_grasp_arm,
        }
        if args.mode in stages:
            stages[args.mode](robot)
            return

        if args.mode == "staged":
            run_staged_grasp(robot, args.color, config)
            return

        if args.mode == "grasp-once":
            grasp_once(robot)
            return

        if args.mode == "body-grasp":
            raise SystemExit(0 if grasp_from_body_view(robot, args.color, config) else 1)

        if args.mode == "catch":
            if not args.dry_run:
                prepare_for_grasp(robot)
            aligned = align_ball(robot, motion, args.color, config)
            if aligned:
                grasp_once(robot)
            else:
                print("[ball-test] align failed, skip grasp-once")
            raise SystemExit(0 if aligned else 1)
    finally:
        robot.close()


if __name__ == "__main__":
    main()
