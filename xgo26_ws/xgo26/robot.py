from __future__ import annotations

import fcntl
import os
from pathlib import Path
import time
from typing import Any


class Robot:
    def __init__(
        self,
        serial_port: str = "/dev/ttyAMA0",
        model: str = "auto",
        dry_run: bool = False,
        lock_serial: bool = True,
    ):
        self.serial_port = serial_port
        self.model = model
        self.dry_run = dry_run
        self.dog: Any | None = None
        self._serial_lock_file: Any | None = None
        self.wheel_control_enabled = False
        if dry_run:
            print(f"[robot] dry-run mode, serial={serial_port}, model={model}")
            return
        if lock_serial:
            self._acquire_serial_lock()
        try:
            import xgolib

            self.dog = xgolib.XGO(port=serial_port, version=model)
            print(f"[robot] connected serial={serial_port}, model={model}")
        except Exception as exc:
            self.close()
            raise RuntimeError(f"无法初始化 XGO({serial_port}): {exc}") from exc

    def close(self) -> None:
        self.dog = None
        if self._serial_lock_file is not None:
            try:
                fcntl.flock(self._serial_lock_file, fcntl.LOCK_UN)
            finally:
                self._serial_lock_file.close()
                self._serial_lock_file = None

    def _acquire_serial_lock(self) -> None:
        lock_name = Path(self.serial_port).name.replace("/", "_")
        lock_path = Path(f"/tmp/xgo26-serial-{lock_name}.lock")
        lock_file = lock_path.open("w", encoding="ascii")
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            lock_file.close()
            raise RuntimeError(
                f"控制串口正被另一个 XGO26 程序使用: {self.serial_port}"
            ) from exc
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        self._serial_lock_file = lock_file

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
        if self.wheel_control_enabled:
            self._try_call("wheel_control", [128, 128, 128, 128])
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
        enabled = int(mode)
        if self._try_call("enable_wheel_control", enabled):
            self.wheel_control_enabled = bool(enabled)

    def wheel_control(self, values: list[int]) -> None:
        if len(values) != 4:
            raise ValueError("四轮控制必须提供 4 个速度值")
        self._call("wheel_control", [max(0, min(255, int(value))) for value in values])

    def read_yaw(self) -> float:
        if self.dry_run or self.dog is None:
            return 0.0
        try:
            return float(self.dog.read_yaw())
        except Exception as exc:
            print(f"[robot] read_yaw failed: {exc}")
            return 0.0

    def read_roll(self) -> float:
        return self._read_float("read_roll")

    def read_pitch(self) -> float:
        return self._read_float("read_pitch")

    def read_imu(self) -> list[float]:
        value = self._read_value("read_imu", [])
        return [float(item) for item in value] if isinstance(value, list) else []

    def read_motors(self) -> list[float]:
        if self.dry_run or self.dog is None:
            return []
        method = getattr(self.dog, "read_motor", None)
        if method is None:
            return []
        try:
            value = method()
            return [float(item) for item in value] if isinstance(value, list) else []
        except IndexError:
            # M-7.0.0b8 returns 16 bytes for this 15-register read. The
            # bundled xgolib loops over all 16 and indexes past MOTOR_LIMIT.
            raw = getattr(self.dog, "rx_data", b"")
            rx_len = int(getattr(self.dog, "rx_LEN", 0))
            if rx_len >= 23 and len(raw) >= 15:
                print("[robot] applying M-7.0.0b8 15-motor feedback workaround")
                return _decode_motor_feedback(raw[:15])
            return []
        except Exception as exc:
            print(f"[robot] read_motor failed: {exc}")
            return []

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

    def _read_float(self, name: str) -> float:
        value = self._read_value(name, 0.0)
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _read_value(self, name: str, default: Any) -> Any:
        if self.dry_run or self.dog is None:
            return default
        method = getattr(self.dog, name, None)
        if method is None:
            print(f"[robot] skip unsupported reader: {name}")
            return default
        try:
            return method()
        except Exception as exc:
            print(f"[robot] {name} failed: {exc}")
            return default


def _decode_motor_feedback(raw: bytes | bytearray) -> list[float]:
    limits = [
        *([[-73, 57], [-66, 93], [-31, 31]] * 4),
        [-65, 65],
        [-85, 50],
        [-75, 90],
    ]
    return [
        round(value / 255.0 * (limit[1] - limit[0]) + limit[0], 2)
        for value, limit in zip(raw, limits)
    ]
