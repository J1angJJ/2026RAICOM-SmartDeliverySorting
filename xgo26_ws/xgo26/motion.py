from __future__ import annotations

import math
import time
from collections.abc import Iterable

from .robot import Robot


class Motion:
    def __init__(self, robot: Robot):
        self.robot = robot
        self.start_yaw = robot.read_yaw()
        self.prev_error: float | None = None
        self.integral = 0.0

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
            elif kind == "turn_to":
                self.turn_to(float(step.get("yaw", 0)))
            elif kind == "wait":
                time.sleep(float(step.get("seconds", 0)))
            else:
                print(f"[motion] skip unknown route step: {step}")


def _angle_error(target: float, current: float) -> float:
    return math.degrees(
        math.atan2(
            math.sin(math.radians(target - current)),
            math.cos(math.radians(target - current)),
        )
    )


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))

