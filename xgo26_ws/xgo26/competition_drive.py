from __future__ import annotations

import time

from .robot import Robot


class CompetitionDrive:
    """比赛移动动作层：直线使用轮子，原地转向使用机器狗步态。"""

    def __init__(self, robot: Robot, config: dict | None = None):
        cfg = config or {}
        self.robot = robot
        self.forward_input_max = max(1.0, float(cfg.get("forward_input_max", 30)))
        self.turn_input_max = max(1.0, float(cfg.get("turn_input_max", 80)))
        self.wheel_speed_max = min(1.5, max(0.0, float(cfg.get("wheel_speed_max", 1.2))))
        self.switch_delay = max(0.0, float(cfg.get("switch_delay", 0.12)))
        self.wheel_postures = cfg.get("wheel_postures", {})
        self._mode = "gait"
        self._posture = "neutral"

    def forward(self, speed: float) -> None:
        """四轮同速前进/后退，不发送腿部平移命令。"""
        self.wheel_drive(forward=speed)

    def wheel_drive(self, forward: float, yaw: float = 0.0) -> None:
        """轮式直行并用左右轮差速做小幅航向修正。"""
        self._enter_wheel_mode()
        x = _clamp(forward / self.forward_input_max, -1.0, 1.0)
        z = _clamp(yaw / self.turn_input_max, -1.0, 1.0)
        left = x - z
        right = x + z
        peak = max(1.0, abs(left), abs(right))
        values = [left / peak, right / peak, left / peak, right / peak]
        self.robot.wheel_control([self._wheel_byte(value) for value in values])

    def move_forward(self, speed: float, seconds: float) -> None:
        if seconds <= 0:
            return
        self.forward(speed)
        try:
            time.sleep(seconds)
        finally:
            self.stop()
            time.sleep(0.2)

    def gait_lateral(self, speed: float, seconds: float) -> None:
        """保留厂家横移步态；轮式横移策略后续可在此替换。"""
        self._enter_gait_mode()
        self.robot.move("y", speed, seconds)

    def turn(self, speed: float) -> None:
        """使用机器狗原有转向步态，不使用四轮差速原地转向。"""
        self._enter_gait_mode()
        self.robot.turn(speed)

    def stop(self) -> None:
        if self._mode == "wheel":
            self.robot.wheel_control([128, 128, 128, 128])
        else:
            self.robot.stop()

    def use_gait_mode(self) -> None:
        self._enter_gait_mode()

    def use_wheel_posture(self, name: str) -> None:
        """Enter wheel mode and apply a stable body pose without driving the wheels."""
        if name not in self.wheel_postures:
            raise ValueError(f"未知四轮姿态: {name}")
        self._enter_wheel_mode()
        self.stop()
        self._apply_posture(name)

    def _enter_wheel_mode(self) -> None:
        if self._mode == "wheel":
            return
        self.robot.stop()
        self.robot.enable_wheel_control(1)
        self._mode = "wheel"
        time.sleep(self.switch_delay)

    def _enter_gait_mode(self) -> None:
        if self._mode == "gait":
            return
        self.robot.wheel_control([128, 128, 128, 128])
        self.robot.enable_wheel_control(0)
        self._mode = "gait"
        if self._posture != "neutral" and "neutral" in self.wheel_postures:
            self._apply_posture("neutral")
        time.sleep(self.switch_delay)

    def _apply_posture(self, name: str) -> None:
        config = self.wheel_postures[name]
        height = _clamp(float(config.get("height", 100)), 75, 115)
        pitch = _clamp(float(config.get("pitch", 0)), -15, 15)
        self._posture = name
        self.robot.translation("z", height)
        self.robot.attitude("p", pitch)
        time.sleep(max(0.0, float(config.get("settle_seconds", 0.4))))

    def _wheel_byte(self, value: float) -> int:
        speed = _clamp(value * self.wheel_speed_max, -1.5, 1.5)
        return max(0, min(255, int(round(128 + speed / 1.5 * 127))))


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
