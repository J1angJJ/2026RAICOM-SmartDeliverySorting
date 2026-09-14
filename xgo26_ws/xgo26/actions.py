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
    return True, detect_colored_ball(
        frame,
        color,
        thresholds[color],
        roi_top_ratio=float(grasp_cfg.get("roi_top_ratio", 0.55)),
    )


def ball_ready_for_grasp(detection: BallDetection, config: dict) -> bool:
    grasp_cfg = config.get("grasp", {})
    return detection.ready_for_grasp(
        target_x=float(grasp_cfg.get("target_x", -0.09)),
        tolerance_x=float(grasp_cfg.get("tolerance_x", 0.08)),
        target_top_ratio=float(grasp_cfg.get("ready_target_top_ratio", 0.75)),
        tolerance_top_ratio=float(grasp_cfg.get("ready_tolerance_top_ratio", 0.05)),
        target_width_ratio=float(grasp_cfg.get("ready_target_width_ratio", 0.23)),
        tolerance_width_ratio=float(grasp_cfg.get("ready_tolerance_width_ratio", 0.04)),
        min_width_ratio=float(grasp_cfg.get("ready_min_width_ratio", 0.16)),
        require_bottom=bool(grasp_cfg.get("ready_require_bottom", True)),
    )


def ball_ready_for_body_down(detection: BallDetection, config: dict) -> bool:
    grasp_cfg = config.get("grasp", {})
    return detection.ready_for_grasp(
        target_x=float(grasp_cfg.get("approach_target_x", -0.17)),
        tolerance_x=float(grasp_cfg.get("approach_tolerance_x", 0.08)),
        target_top_ratio=float(grasp_cfg.get("approach_target_top_ratio", 0.78)),
        tolerance_top_ratio=float(
            grasp_cfg.get("approach_tolerance_top_ratio", 0.06)
        ),
        target_width_ratio=float(grasp_cfg.get("approach_target_width_ratio", 0.14)),
        tolerance_width_ratio=float(
            grasp_cfg.get("approach_tolerance_width_ratio", 0.03)
        ),
        min_width_ratio=float(grasp_cfg.get("approach_min_width_ratio", 0.1)),
        require_bottom=bool(grasp_cfg.get("approach_require_bottom", True)),
    )


def align_ball_for_body_down(
    robot: Robot,
    motion: Motion,
    color: str,
    config: dict,
) -> bool:
    grasp_cfg = config.get("grasp", {})
    threshold = config["ball_thresholds_lab"][color]
    camera_cfg = config["camera"]
    posture = str(grasp_cfg.get("approach_posture", "view_down"))
    target_x = float(grasp_cfg.get("approach_target_x", -0.17))
    tolerance_x = float(grasp_cfg.get("approach_tolerance_x", 0.08))
    target_width = float(grasp_cfg.get("approach_target_width_ratio", 0.14))
    width_tolerance = float(grasp_cfg.get("approach_tolerance_width_ratio", 0.03))
    max_steps = max(1, int(grasp_cfg.get("approach_max_steps", 10)))
    stable_required = max(1, int(grasp_cfg.get("approach_stable_frames", 2)))
    turn_speed = abs(float(grasp_cfg.get("approach_turn_speed", 20)))
    turn_seconds = max(0.0, float(grasp_cfg.get("approach_turn_seconds", 0.2)))
    forward_speed = abs(float(grasp_cfg.get("approach_forward_speed", 20)))
    forward_seconds = max(0.0, float(grasp_cfg.get("approach_forward_seconds", 0.15)))
    backward_speed = abs(float(grasp_cfg.get("approach_backward_speed", 15)))
    backward_seconds = max(0.0, float(grasp_cfg.get("approach_backward_seconds", 0.12)))
    settle_seconds = max(0.0, float(grasp_cfg.get("approach_settle_seconds", 0.25)))

    stable_frames = 0
    motion.drive.use_wheel_posture(posture)
    with camera_reader_from_config(
        camera_cfg,
        stream=str(grasp_cfg.get("camera_stream", "lores")),
        width=int(grasp_cfg.get("camera_width", 320)),
        height=int(grasp_cfg.get("camera_height", 240)),
        warmup_frames=int(grasp_cfg.get("warmup_frames", 2)),
    ) as reader:
        for step in range(1, max_steps + 1):
            frame = reader.read()
            detection = (
                detect_colored_ball(
                    frame,
                    color,
                    threshold,
                    roi_top_ratio=float(grasp_cfg.get("roi_top_ratio", 0.55)),
                )
                if frame is not None
                else None
            )
            if detection is None:
                motion.stop()
                print("[action] approach ball lost, stop")
                return False

            ready = ball_ready_for_body_down(detection, config)
            print(
                f"[action] approach step={step}/{max_steps} "
                f"{detection.summary()} approach_ready={ready}"
            )
            if ready:
                stable_frames += 1
                motion.stop()
                if stable_frames >= stable_required:
                    return True
                time.sleep(settle_seconds)
                continue
            stable_frames = 0

            horizontal_error = detection.box_center_x_normalized - target_x
            if step == max_steps:
                motion.stop()
                print("[action] approach alignment reached step limit")
                return False
            if abs(horizontal_error) > tolerance_x:
                yaw = turn_speed if horizontal_error > 0 else -turn_speed
                direction = "right" if yaw < 0 else "left"
                pulse_seconds = min(
                    turn_seconds,
                    max(0.1, abs(horizontal_error) * 0.8),
                )
                print(f"[action] approach pulse turn-{direction} {pulse_seconds:.2f}s")
                motion.stop()
                motion.drive.gait_drive(0, yaw, posture=posture)
                time.sleep(pulse_seconds)
                motion.stop()
            elif (
                not detection.touches_bottom
                or detection.box_width_ratio < target_width - width_tolerance
            ):
                print(f"[action] approach pulse forward {forward_seconds:.2f}s")
                motion.drive.wheel_drive(forward_speed, 0)
                time.sleep(forward_seconds)
                motion.stop()
            elif detection.box_width_ratio > target_width + width_tolerance:
                print(f"[action] approach pulse backward {backward_seconds:.2f}s")
                motion.drive.wheel_drive(-backward_speed, 0)
                time.sleep(backward_seconds)
                motion.stop()
            else:
                motion.stop()
                print("[action] approach geometry is outside vertical tolerance")
                return False
            time.sleep(settle_seconds)

    return False


def grasp_from_body_view(robot: Robot, color: str, config: dict) -> bool:
    print(f"[action] lower body and verify {color} ball")
    lower_grasp_body(robot)
    camera_ok, detection = detect_ball_once(color, config)
    if not camera_ok:
        print("[action] camera failed after body-down, restore body")
        restore_grasp_body(robot)
        return False
    if detection is None:
        print(f"[action] {color} ball not found after body-down, restore body")
        restore_grasp_body(robot)
        return False

    ready = ball_ready_for_grasp(detection, config)
    print(f"[action] {detection.summary()} grasp_ready={ready}")
    if not ready:
        print("[action] ball is visible but not ready, restore body without grasping")
        restore_grasp_body(robot)
        return False

    lower_grasp_arm(robot)
    close_grasp_claw(robot)
    retract_grasp_arm(robot)
    restore_grasp_body(robot)
    stow_grasp_arm(robot)
    return True


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
            detection = detect_colored_ball(
                frame,
                color,
                threshold,
                roi_top_ratio=float(grasp_cfg.get("roi_top_ratio", 0.55)),
            )
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
                    distance_error = float(
                        grasp_cfg.get("ready_target_width_ratio", 0.23)
                    ) - detection.box_width_ratio
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
