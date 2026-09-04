from __future__ import annotations

import time

from .camera import capture_frame
from .motion import Motion
from .perception import DeliveryTask, find_colored_ball, normalize_center
from .robot import Robot


def prepare_for_mission(robot: Robot) -> None:
    print("[action] prepare")
    robot.reset()
    robot.claw(0)
    robot.arm(0, 100)
    time.sleep(0.5)


def grasp_ball(robot: Robot, motion: Motion, color: str, config: dict) -> bool:
    print(f"[action] grasp {color} ball")
    if robot.dry_run:
        time.sleep(0.2)
        return True

    thresholds = config["ball_thresholds_lab"]
    if color not in thresholds:
        raise ValueError(f"未配置小球颜色阈值: {color}")

    robot.reset()
    robot.attitude("p", 15)
    time.sleep(0.5)

    camera_cfg = config["camera"]
    threshold = thresholds[color]
    for index in range(40):
        ok, frame = capture_frame(
            camera_index=int(camera_cfg.get("index", 0)),
            width=320,
            height=240,
            warmup_frames=2,
        )
        if not ok:
            print("[action] camera failed while grasping")
            break
        found = find_colored_ball(frame, threshold)
        if found is None:
            print("[action] ball not found, move forward")
            robot.move("x", 12, 0.7)
            continue

        x, y, radius = found
        h, w = frame.shape[:2]
        nx, ny = normalize_center(x, y, w, h)
        print(f"[action] ball center=({nx:.2f}, {ny:.2f}), radius={radius}")
        if abs(nx) < 0.15 and abs(ny + 0.85) < 0.18:
            _grasp_sequence(robot)
            return True
        if abs(nx) >= 0.15:
            robot.move("y", 10 if nx < 0 else -10, min(1.2, max(0.4, abs(nx))))
        else:
            robot.move("x", -10 if ny < -0.85 else 12, min(1.2, max(0.4, abs(ny + 0.85))))
        if index % 5 == 4:
            motion.turn_to(0)

    print("[action] grasp fallback sequence")
    _grasp_sequence(robot)
    return False


def place_task(robot: Robot, task: DeliveryTask, config: dict) -> bool:
    print(f"[action] place to {task.letter}")
    if robot.dry_run:
        time.sleep(0.2)
        return True
    _place_sequence(robot)
    return True


def speak_task(task: DeliveryTask, dry_run: bool = False) -> None:
    message = f"{task.letter}区 {task.package_cn} {task.ball_color}球"
    print(f"[speak] {message}")
    if dry_run:
        return
    try:
        from xgoedu import XGOEDU

        edu = XGOEDU()
        edu.xgoSpeaker(message)
    except Exception as exc:
        print(f"[speak] speaker unavailable: {exc}")


def _grasp_sequence(robot: Robot) -> None:
    robot.claw(0)
    robot.translation("x", 20)
    robot.motor(52, -55)
    time.sleep(0.5)
    robot.translation("z", 60)
    time.sleep(0.5)
    robot.motor(53, 80)
    robot.attitude("p", 20)
    time.sleep(1.5)
    robot.claw(255)
    time.sleep(2.0)
    robot.arm(100, 0)
    robot.reset()
    robot.claw(255)
    robot.arm(-90, 90)
    robot.arm_mode(1)
    time.sleep(1.0)


def _place_sequence(robot: Robot) -> None:
    robot.translation("x", 20)
    robot.arm_mode(0)
    robot.motor(52, -55)
    time.sleep(0.5)
    robot.translation("z", 60)
    time.sleep(0.5)
    robot.motor(53, 80)
    robot.attitude("p", 20)
    time.sleep(1.5)
    robot.claw(0)
    time.sleep(1.5)
    robot.reset()
    time.sleep(0.5)

