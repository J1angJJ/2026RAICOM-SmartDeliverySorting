from __future__ import annotations

import time
from typing import Any


class Robot:
    def __init__(
        self,
        serial_port: str = "/dev/ttyAMA0",
        model: str = "auto",
        dry_run: bool = False,
    ):
        self.serial_port = serial_port
        self.model = model
        self.dry_run = dry_run
        self.dog: Any | None = None
        if dry_run:
            print(f"[robot] dry-run mode, serial={serial_port}, model={model}")
            return
        try:
            import xgolib

            self.dog = xgolib.XGO(port=serial_port, version=model)
            print(f"[robot] connected serial={serial_port}, model={model}")
        except Exception as exc:
            raise RuntimeError(f"无法初始化 XGO({serial_port}): {exc}") from exc

    def reset(self) -> None:
        self._call("reset")
        time.sleep(0.5)

    def initialize_control_mode(self, config: dict | None = None) -> None:
        cfg = config or {}
        print("[robot] initialize control mode")
        self.stop()
        if cfg.get("disable_wheel_control", True):
            self.enable_wheel_control(0)
        if cfg.get("load_all_motors", True):
            self.load_allmotor()
        gait = cfg.get("gait_type")
        if gait:
            self.gait_type(str(gait))
        pace = cfg.get("pace")
        if pace:
            self.pace(str(pace))
        self.reset()
        self.stop()

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
            self.set_move_x(speed)
        elif axis == "y":
            self.set_move_y(speed)
        else:
            raise ValueError(f"未知移动轴: {axis}")
        time.sleep(max(0.0, seconds))
        self.stop()
        time.sleep(0.2)

    def set_move_x(self, speed: float) -> None:
        self._call("move_x", speed)

    def set_move_y(self, speed: float) -> None:
        self._call("move_y", speed)

    def turn(self, speed: float) -> None:
        self._call("turn", speed)

    def move_x_by(
        self,
        distance: float,
        speed: float = 18,
        k: float = 0.035,
        min_time: float = 0.55,
    ) -> None:
        self._call("move_x_by", distance, speed, k, min_time)

    def move_y_by(
        self,
        distance: float,
        speed: float = 18,
        k: float = 0.0373,
        min_time: float = 0.5,
    ) -> None:
        self._call("move_y_by", distance, speed, k, min_time)

    def load_allmotor(self) -> None:
        self._try_call("load_allmotor")

    def gait_type(self, mode: str) -> None:
        self._try_call("gait_type", mode)

    def pace(self, mode: str) -> None:
        self._try_call("pace", mode)

    def enable_wheel_control(self, mode: int) -> None:
        self._try_call("enable_wheel_control", int(mode))

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

    def _try_call(self, name: str, *args: Any) -> bool:
        if self.dry_run or self.dog is None:
            print(f"[robot] {name}{args}")
            return True
        method = getattr(self.dog, name, None)
        if method is None:
            print(f"[robot] skip unsupported method: {name}")
            return False
        try:
            method(*args)
            return True
        except Exception as exc:
            print(f"[robot] {name} failed: {exc}")
            return False
