from __future__ import annotations

import time

from .camera import camera_reader_from_config, capture_frame_from_config
from .motion import Motion
from .perception import BallDetection, DeliveryTask, detect_colored_ball
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

    prepare_for_grasp(robot)
    aligned = align_ball(robot, motion, color, config)
    if aligned:
        grasp_once(robot)
        return True

    print("[action] grasp fallback sequence")
    grasp_once(robot)
    return False


def prepare_for_grasp(robot: Robot) -> None:
    robot.reset()
    robot.attitude("p", 15)
    time.sleep(0.5)


def detect_ball_once(color: str, config: dict) -> tuple[bool, BallDetection | None]:
    thresholds = config["ball_thresholds_lab"]
    if color not in thresholds:
        raise ValueError(f"未配置小球颜色阈值: {color}")

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
        return False, None
    return True, detect_colored_ball(frame, color, thresholds[color])


def ball_ready_for_grasp(detection: BallDetection, config: dict) -> bool:
    grasp_cfg = config.get("grasp", {})
    return detection.ready_for_grasp(
        target_x=float(grasp_cfg.get("target_x", -0.14)),
        tolerance_x=float(grasp_cfg.get("tolerance_x", 0.15)),
        target_top_ratio=float(grasp_cfg.get("ready_target_top_ratio", 0.89)),
        tolerance_top_ratio=float(grasp_cfg.get("ready_tolerance_top_ratio", 0.07)),
        min_width_ratio=float(grasp_cfg.get("ready_min_width_ratio", 0.16)),
        require_bottom=bool(grasp_cfg.get("ready_require_bottom", True)),
    )


def align_ball(robot: Robot, motion: Motion, color: str, config: dict) -> bool:
    thresholds = config["ball_thresholds_lab"]
    if color not in thresholds:
        raise ValueError(f"未配置小球颜色阈值: {color}")

    camera_cfg = config["camera"]
    grasp_cfg = config.get("grasp", {})
    threshold = thresholds[color]
    target_x = float(grasp_cfg.get("target_x", 0.0))
    target_y = float(grasp_cfg.get("target_y", -0.85))
    tolerance_x = float(grasp_cfg.get("tolerance_x", 0.15))
    tolerance_y = float(grasp_cfg.get("tolerance_y", 0.18))
    max_steps = int(grasp_cfg.get("max_align_steps", 40))
    min_seconds = float(grasp_cfg.get("min_step_seconds", 0.4))
    max_seconds = float(grasp_cfg.get("max_step_seconds", 1.2))
    yaw_every = int(grasp_cfg.get("yaw_correction_every", 5))

    with camera_reader_from_config(
        camera_cfg,
        stream=str(grasp_cfg.get("camera_stream", "lores")),
        width=int(grasp_cfg.get("camera_width", 320)),
        height=int(grasp_cfg.get("camera_height", 240)),
        warmup_frames=int(grasp_cfg.get("warmup_frames", 2)),
    ) as reader:
        for index in range(max_steps):
            frame = reader.read()
            if frame is None:
                print("[action] camera failed while grasping")
                break
            detection = detect_colored_ball(frame, color, threshold)
            if detection is None:
                print("[action] ball not found, move forward")
                motion.move("x", float(grasp_cfg.get("search_speed", 12)), 0.7)
                continue

            print(f"[action] {detection.summary()}")
            if ball_ready_for_grasp(detection, config):
                return True

            err_x = detection.box_center_x_normalized - target_x
            if abs(err_x) >= tolerance_x:
                seconds = min(max_seconds, max(min_seconds, abs(err_x)))
                speed = float(grasp_cfg.get("lateral_speed", 10))
                motion.move("y", speed if err_x < 0 else -speed, seconds)
            else:
                if detection.touches_bottom:
                    distance_error = (
                        detection.box_top_ratio
                        - float(grasp_cfg.get("ready_target_top_ratio", 0.89))
                    )
                else:
                    distance_error = 1.0
                seconds = min(max_seconds, max(min_seconds, abs(distance_error)))
                if distance_error < 0:
                    speed = float(grasp_cfg.get("backward_speed", -10))
                else:
                    speed = float(grasp_cfg.get("forward_speed", 12))
                motion.move("x", speed, seconds)
            if yaw_every > 0 and index % yaw_every == yaw_every - 1:
                motion.turn_to(0)

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


def grasp_once(robot: Robot) -> None:
    print("[action] grasp once")
    robot.claw(0)
    robot.translation("x", 20)
    robot.motor(52, -40)
    time.sleep(0.5)
    robot.translation("z", 60)
    time.sleep(0.5)
    robot.motor(53, 85)
    robot.attitude("p", 20)
    time.sleep(1.5)
    close_grasp_claw(robot)
    retract_grasp_arm(robot)
    robot.reset()
    stow_grasp_arm(robot)


def lower_grasp_body(robot: Robot) -> None:
    print("[action] lower grasp body")
    robot.translation("x", 20)
    robot.translation("z", 60)
    time.sleep(0.5)
    robot.attitude("p", 20)
    time.sleep(1.0)


def restore_grasp_body(robot: Robot) -> None:
    print("[action] restore grasp body")
    robot.attitude("p", 0)
    robot.translation("z", 95)
    robot.translation("x", 0)
    time.sleep(1.0)


def lower_grasp_arm(robot: Robot) -> None:
    print("[action] lower grasp arm")
    robot.claw(0)
    robot.motor(52, -40)
    time.sleep(0.5)
    robot.motor(53, 85)
    time.sleep(1.5)


def close_grasp_claw(robot: Robot) -> None:
    print("[action] close grasp claw")
    robot.claw(255)
    time.sleep(2.0)


def retract_grasp_arm(robot: Robot) -> None:
    print("[action] retract grasp arm")
    robot.motor(53, 0)
    time.sleep(0.5)
    robot.motor(52, 0)
    time.sleep(0.5)


def stow_grasp_arm(robot: Robot) -> None:
    print("[action] stow grasp arm")
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
