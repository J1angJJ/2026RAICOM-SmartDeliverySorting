#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from xgo26.camera import CameraReader
from xgo26.config import load_config
from xgo26.line_following import LineTracker
from xgo26.motion import Motion
from xgo26.robot import Robot


def main() -> None:
    config = load_config("config.json")
    robot_cfg = config["robot"]
    line_cfg = config["line_following"]
    route_cfg = config["three_segment_route"]
    camera_cfg = {**config["camera"], **line_cfg.get("camera", {})}

    robot = Robot(
        serial_port=robot_cfg.get("serial_port", "/dev/ttyAMA0"),
        model=robot_cfg.get("model", "auto"),
    )
    motion = Motion(
        robot,
        robot_cfg.get("drive", {}),
        config.get("camera", {}),
        line_cfg,
    )

    try:
        robot.initialize_control_mode(robot_cfg.get("control", {}))
        motion.reset_yaw_origin()
        print(f"[three-segment] battery={robot.read_battery()}%")
        with CameraReader(
            camera_index=int(camera_cfg.get("index", 0)),
            width=int(camera_cfg.get("width", 320)),
            height=int(camera_cfg.get("height", 240)),
            warmup_frames=int(camera_cfg.get("warmup_frames", 3)),
            source=str(camera_cfg.get("source", "service")),
            service_url=str(camera_cfg.get("service_url", "http://127.0.0.1:8090")),
            stream=str(camera_cfg.get("stream", "lores")),
            request_timeout=float(camera_cfg.get("request_timeout", 2.0)),
        ) as reader:
            for corner_index in range(2):
                print(f"[three-segment] follow segment {corner_index + 1}/3")
                _follow_to_corner(
                    reader,
                    motion,
                    line_cfg,
                    route_cfg,
                    blind_seconds=(
                        0.0
                        if corner_index == 0
                        else float(route_cfg.get("after_turn_blind_seconds", 0.35))
                    ),
                )
                _forward_pulse(
                    motion,
                    speed=float(route_cfg.get("compensation_speed", 28)),
                    seconds=float(route_cfg.get("compensation_seconds", 0.12)),
                    posture=str(route_cfg.get("posture", "view_down")),
                )
                direction = str(route_cfg.get("corner_direction", "right"))
                angle = abs(float(route_cfg.get("corner_angle", 90)))
                motion.turn_relative_low(
                    angle if direction == "left" else -angle,
                    timeout=float(route_cfg.get("turn_timeout", 8.0)),
                    posture=str(route_cfg.get("posture", "view_down")),
                    coarse_speed=float(route_cfg.get("turn_coarse_speed", 40)),
                    fine_speed=float(route_cfg.get("turn_fine_speed", 20)),
                    tolerance=float(route_cfg.get("turn_tolerance", 2)),
                )

            print("[three-segment] follow segment 3/3")
            _follow_final_segment(reader, motion, line_cfg, route_cfg)
        print("[three-segment] complete")
    finally:
        motion.stop()
        try:
            motion.drive.use_gait_mode()
        finally:
            robot.stop()
            robot.close()


def _follow_to_corner(
    reader: CameraReader,
    motion: Motion,
    line_cfg: dict,
    route_cfg: dict,
    blind_seconds: float,
) -> None:
    speed = float(route_cfg.get("straight_speed", 30))
    posture = str(route_cfg.get("posture", "view_down"))
    expected_direction = str(route_cfg.get("corner_direction", "right"))
    corner_confidence = float(route_cfg.get("corner_confidence", 0.65))
    near_corner_y_ratio = float(route_cfg.get("near_corner_y_ratio", 0.60))
    timeout = float(route_cfg.get("corner_timeout", 12.0))
    sample_seconds = float(route_cfg.get("sample_seconds", 0.08))
    max_initial_lost = int(route_cfg.get("max_initial_lost_frames", 5))

    motion.drive.use_wheel_posture(posture)
    if blind_seconds > 0:
        motion.drive.forward(speed)
        time.sleep(blind_seconds)
        motion.stop()

    tracker = LineTracker(line_cfg)
    corner_seen = False
    initial_lost = 0
    last_correction = 0.0
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        frame = reader.read()
        detection = tracker.process(frame) if frame is not None else None
        corner = tracker.last_corner
        if (
            corner is not None
            and corner.direction == expected_direction
            and corner.confidence >= corner_confidence
        ):
            corner_seen = True
            print(f"[three-segment] latch {corner.summary()}")
        elif (
            corner is not None
            and frame is not None
            and corner.y >= frame.shape[0] * near_corner_y_ratio
            and corner.confidence >= corner_confidence
        ):
            corner_seen = True
            print(f"[three-segment] latch near mapped corner {corner.summary()}")

        if detection is None:
            motion.stop()
            if corner_seen:
                print("[three-segment] corner passed below camera")
                return
            initial_lost += 1
            if initial_lost >= max_initial_lost:
                raise RuntimeError("到达角点前丢失循迹线")
        else:
            initial_lost = 0
            if corner_seen:
                motion.drive.wheel_drive(speed, 0)
            else:
                corrected, last_correction = _correct_heading(
                    motion,
                    detection.steering_error,
                    posture,
                    route_cfg,
                    last_correction,
                )
                if corrected:
                    tracker = LineTracker(line_cfg)
                else:
                    motion.drive.wheel_drive(speed, 0)
        time.sleep(sample_seconds)

    motion.stop()
    raise TimeoutError("等待右角点超时")


def _follow_final_segment(
    reader: CameraReader,
    motion: Motion,
    line_cfg: dict,
    route_cfg: dict,
) -> None:
    speed = float(route_cfg.get("straight_speed", 30))
    posture = str(route_cfg.get("posture", "view_down"))
    blind_seconds = float(route_cfg.get("after_turn_blind_seconds", 0.35))
    final_seconds = float(route_cfg.get("final_segment_seconds", 2.5))
    sample_seconds = float(route_cfg.get("sample_seconds", 0.08))
    max_lost = int(route_cfg.get("final_lost_frames", 4))

    motion.drive.use_wheel_posture(posture)
    motion.drive.forward(speed)
    time.sleep(blind_seconds)
    tracker = LineTracker(line_cfg)
    lost_frames = 0
    last_correction = 0.0
    started = time.monotonic()
    while time.monotonic() - started < final_seconds:
        frame = reader.read()
        detection = tracker.process(frame) if frame is not None else None
        if detection is None:
            lost_frames += 1
            if lost_frames >= max_lost:
                print("[three-segment] final line ended or lost")
                break
        else:
            lost_frames = 0
            corrected, last_correction = _correct_heading(
                motion,
                detection.steering_error,
                posture,
                route_cfg,
                last_correction,
            )
            if corrected:
                tracker = LineTracker(line_cfg)
                time.sleep(sample_seconds)
                continue
        motion.drive.wheel_drive(speed, 0)
        time.sleep(sample_seconds)
    motion.stop()


def _forward_pulse(motion: Motion, speed: float, seconds: float, posture: str) -> None:
    print(f"[three-segment] corner compensation speed={speed:.1f} seconds={seconds:.2f}")
    motion.drive.use_wheel_posture(posture)
    motion.drive.forward(speed)
    try:
        time.sleep(max(0.0, seconds))
    finally:
        motion.stop()
        time.sleep(0.15)


def _correct_heading(
    motion: Motion,
    steering_error: float,
    posture: str,
    route_cfg: dict,
    last_correction: float,
) -> tuple[bool, float]:
    threshold = abs(float(route_cfg.get("correction_threshold", 0.08)))
    interval = max(0.0, float(route_cfg.get("correction_interval", 0.35)))
    now = time.monotonic()
    if abs(steering_error) < threshold or now - last_correction < interval:
        return False, last_correction

    turn_speed = abs(float(route_cfg.get("correction_turn_speed", 20)))
    seconds = max(0.0, float(route_cfg.get("correction_seconds", 0.25)))
    yaw = -turn_speed if steering_error > 0 else turn_speed
    direction = "right" if yaw < 0 else "left"
    print(
        f"[three-segment] line correction {direction} "
        f"steering={steering_error:+.3f} seconds={seconds:.2f}"
    )
    motion.stop()
    motion.drive.gait_drive(0, yaw, posture=posture)
    try:
        time.sleep(seconds)
    finally:
        motion.stop()
        time.sleep(0.10)
    return True, time.monotonic()


if __name__ == "__main__":
    main()
