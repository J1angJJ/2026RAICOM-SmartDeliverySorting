from __future__ import annotations

import time
from typing import Any


class Robot:
    def __init__(self, serial_port: str = "/dev/ttyAMA0", dry_run: bool = False):
        self.serial_port = serial_port
        self.dry_run = dry_run
        self.dog: Any | None = None
        if dry_run:
            print(f"[robot] dry-run mode, serial={serial_port}")
            return
        try:
            import xgolib

            self.dog = xgolib.XGO(serial_port)
            print(f"[robot] connected serial={serial_port}")
        except Exception as exc:
            raise RuntimeError(f"无法初始化 XGO({serial_port}): {exc}") from exc

    def reset(self) -> None:
        self._call("reset")
        time.sleep(0.5)

    def stop(self) -> None:
        self._call("move_x", 0)
        self._call("move_y", 0)
        self._call("turn", 0)
        if self.dog is not None:
            try:
                self.dog.stop()
            except Exception:
                pass

    def move(self, axis: str, speed: float, seconds: float) -> None:
        if axis == "x":
            self._call("move_x", speed)
        elif axis == "y":
            self._call("move_y", speed)
        else:
            raise ValueError(f"未知移动轴: {axis}")
        time.sleep(max(0.0, seconds))
        self.stop()
        time.sleep(0.2)

    def turn(self, speed: float) -> None:
        self._call("turn", speed)

    def read_yaw(self) -> float:
        if self.dry_run or self.dog is None:
            return 0.0
        try:
            return float(self.dog.read_yaw())
        except Exception as exc:
            print(f"[robot] read_yaw failed: {exc}")
            return 0.0

    def read_battery(self) -> int | None:
        if self.dry_run or self.dog is None:
            return None
        try:
            return int(self.dog.read_battery())
        except Exception as exc:
            print(f"[robot] read_battery failed: {exc}")
            return None

    def attitude(self, direction: str | list[str], value: float | list[float]) -> None:
        self._call("attitude", direction, value)

    def translation(self, direction: str | list[str], value: float | list[float]) -> None:
        self._call("translation", direction, value)

    def arm(self, x: float, z: float) -> None:
        self._call("arm", x, z)

    def arm_mode(self, mode: int) -> None:
        self._call("arm_mode", mode)

    def claw(self, pos: int) -> None:
        self._call("claw", pos)

    def motor(self, motor_id: int, angle: float) -> None:
        self._call("motor", motor_id, angle)

    def _call(self, name: str, *args: Any) -> None:
        if self.dry_run or self.dog is None:
            print(f"[robot] {name}{args}")
            return
        method = getattr(self.dog, name)
        method(*args)

