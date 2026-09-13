from __future__ import annotations

import math
import time
from collections.abc import Iterable

from .camera import CameraReader
from .perception import detect_black_line
from .robot import Robot


class Motion:
    def __init__(self, robot: Robot):
        self.robot = robot
        self.start_yaw = robot.read_yaw()
        self.prev_error: float | None = None
        self.integral = 0.0

    def reset_yaw_origin(self) -> None:
        self.start_yaw = self.robot.read_yaw()
        self.prev_error = None
        self.integral = 0.0
        print(f"[motion] yaw origin reset: {self.start_yaw:.1f}")

    def turn_to(self, target_deg: float, timeout: float = 6.0) -> None:
        if self.robot.dry_run:
            print(f"[motion] turn_to {target_deg}")
            return

        start = time.time()
        while True:
            current = self.robot.read_yaw() - self.start_yaw
            error = _angle_error(target_deg, current)
            if abs(error) < 1.0:
                self.robot.turn(0)
                break
            speed = _clamp(error * 1.2, -80, 80)
            if abs(speed) < 15:
                speed = 15 if speed > 0 else -15
            self.robot.turn(speed)
            if time.time() - start > timeout:
                print(f"[motion] turn_to timeout, target={target_deg}, error={error:.1f}")
                self.robot.turn(0)
                break
            time.sleep(0.08)
        time.sleep(0.3)

    def run_route(self, name: str, steps: Iterable[dict]) -> None:
        print(f"[motion] route {name}")
        for step in steps:
            kind = step.get("kind")
            if kind == "move":
                self.robot.move(
                    axis=str(step.get("axis", "x")),
                    speed=float(step.get("speed", 0)),
                    seconds=float(step.get("seconds", 0)),
                )
            elif kind == "move_by":
                self.move_by(step)
            elif kind == "yaw_hold_move":
                self.yaw_hold_move(
                    axis=str(step.get("axis", "x")),
                    speed=float(step.get("speed", 0)),
                    seconds=float(step.get("seconds", 0)),
                    yaw=float(step.get("yaw", 0)),
                    turn_gain=float(step.get("turn_gain", 1.0)),
                    max_turn=float(step.get("max_turn", 28)),
                    sample_seconds=float(step.get("sample_seconds", 0.08)),
                )
            elif kind == "turn_to":
                self.turn_to(float(step.get("yaw", 0)), timeout=float(step.get("timeout", 6.0)))
            elif kind == "line_follow":
                self.follow_line(
                    seconds=float(step.get("seconds", 0)),
                    speed=float(step.get("speed", 10)),
                    config=step,
                )
            elif kind == "wait":
                time.sleep(float(step.get("seconds", 0)))
            elif kind == "stop":
                self.robot.stop()
                time.sleep(float(step.get("seconds", 0.2)))
            elif kind == "mark":
                print(f"[motion] mark {step.get('name', '')}".rstrip())
            else:
                print(f"[motion] skip unknown route step: {step}")

    def move_by(self, step: dict) -> None:
        axis = str(step.get("axis", "x"))
        distance = float(step.get("distance_cm", 0))
        speed = float(step.get("speed", 18))
        scale = float(step.get("distance_scale", 1.0))
        if axis == "x":
            self.robot.move_x_by(distance * scale, speed=speed)
            return
        if axis == "y":
            self.robot.move_y_by(distance * scale, speed=speed)
            return
        raise ValueError(f"未知移动轴: {axis}")

    def yaw_hold_move(
        self,
        axis: str,
        speed: float,
        seconds: float,
        yaw: float,
        turn_gain: float = 1.0,
        max_turn: float = 28,
        sample_seconds: float = 0.08,
    ) -> None:
        print(
            f"[motion] yaw_hold_move axis={axis} speed={speed:.1f} "
            f"seconds={seconds:.1f} yaw={yaw:.1f}"
        )
        if seconds <= 0:
            return
        if axis not in {"x", "y"}:
            raise ValueError(f"未知移动轴: {axis}")
        if self.robot.dry_run:
            time.sleep(min(seconds, 0.2))
            return

        start = time.time()
        try:
            while time.time() - start < seconds:
                current = self.robot.read_yaw() - self.start_yaw
                error = _angle_error(yaw, current)
                turn_speed = _clamp(error * turn_gain, -abs(max_turn), abs(max_turn))
                if axis == "x":
                    self.robot.set_move_x(speed)
                    self.robot.set_move_y(0)
                else:
                    self.robot.set_move_y(speed)
                    self.robot.set_move_x(0)
                self.robot.turn(turn_speed)
                time.sleep(sample_seconds)
        finally:
            self.robot.stop()
            time.sleep(0.2)

    def follow_line(self, seconds: float, speed: float, config: dict) -> None:
        print(f"[motion] line_follow seconds={seconds:.1f} speed={speed:.1f}")
        if seconds <= 0:
            return
        if self.robot.dry_run:
            time.sleep(min(seconds, 0.2))
            return

        camera_cfg = config.get("camera", {})
        line_cfg = config.get("line", {})
        turn_gain = float(config.get("turn_gain", 45))
        max_turn = abs(float(config.get("max_turn", 35)))
        sample_seconds = float(config.get("sample_seconds", 0.08))
        lost_speed = float(config.get("lost_speed", 0))
        lost_turn = float(config.get("lost_turn", 0))
        max_lost_frames = int(config.get("max_lost_frames", 12))

        lost_frames = 0
        start = time.time()
        try:
            with CameraReader(
                camera_index=int(camera_cfg.get("index", 0)),
                width=int(camera_cfg.get("width", 320)),
                height=int(camera_cfg.get("height", 240)),
                warmup_frames=int(camera_cfg.get("warmup_frames", 5)),
            ) as reader:
                while time.time() - start < seconds:
                    frame = reader.read()
                    detection = detect_black_line(frame, line_cfg) if frame is not None else None
                    if detection is None:
                        lost_frames += 1
                        self.robot.set_move_x(lost_speed)
                        self.robot.turn(lost_turn)
                        if lost_frames >= max_lost_frames:
                            print("[motion] line lost, stop this segment")
                            break
                    else:
                        lost_frames = 0
                        turn_speed = _clamp(detection.normalized_x * turn_gain, -max_turn, max_turn)
                        self.robot.set_move_x(speed)
                        self.robot.turn(turn_speed)
                    time.sleep(sample_seconds)
        finally:
            self.robot.stop()
            time.sleep(0.2)

    def drive_square(
        self,
        side_cm: float = 50,
        speed: float = 18,
        turn_direction: str = "left",
        settle_seconds: float = 0.5,
        use_builtin_distance: bool = True,
        forward_seconds: float | None = None,
        distance_scale: float = 1.0,
    ) -> None:
        print(
            f"[motion] square side={side_cm:.1f}cm speed={speed:.1f} "
            f"turn={turn_direction} builtin_distance={use_builtin_distance} "
            f"distance_scale={distance_scale:.2f}"
        )
        sign = 1 if turn_direction == "left" else -1
        if self.robot.dry_run:
            for index in range(4):
                print(f"[motion] square side {index + 1}/4")
                self._drive_square_side(side_cm, speed, use_builtin_distance, forward_seconds, distance_scale)
                self.turn_to(sign * 90 * (index + 1))
            return

        try:
            for index in range(4):
                print(f"[motion] square side {index + 1}/4")
                self._drive_square_side(side_cm, speed, use_builtin_distance, forward_seconds, distance_scale)
                time.sleep(max(0.0, settle_seconds))
                self.turn_to(sign * 90 * (index + 1))
                time.sleep(max(0.0, settle_seconds))
        finally:
            self.robot.stop()

    def _drive_square_side(
        self,
        side_cm: float,
        speed: float,
        use_builtin_distance: bool,
        forward_seconds: float | None,
        distance_scale: float,
    ) -> None:
        if use_builtin_distance:
            self.robot.move_x_by(side_cm * distance_scale, speed=speed)
            return
        seconds = forward_seconds if forward_seconds is not None else _distance_seconds(side_cm, speed)
        self.robot.move("x", speed, seconds)


def _angle_error(target: float, current: float) -> float:
    return math.degrees(
        math.atan2(
            math.sin(math.radians(target - current)),
            math.cos(math.radians(target - current)),
        )
    )


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _distance_seconds(distance_cm: float, speed: float) -> float:
    return max(0.2, 0.035 * abs(distance_cm) * 18 / max(1.0, abs(speed)) + 0.55)
