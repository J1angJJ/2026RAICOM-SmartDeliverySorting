from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib
import math
from pathlib import Path
import sys
import time
from typing import Any, Iterable


@dataclass(frozen=True)
class LidarPoint:
    angle_rad: float
    range_m: float
    intensity: float = 0.0


@dataclass(frozen=True)
class LidarScan:
    points: tuple[LidarPoint, ...]
    captured_at: float
    scan_frequency_hz: float = 0.0


@dataclass(frozen=True)
class WallEstimate:
    valid: bool
    sensor_distance_m: float | None
    robot_distance_m: float | None
    yaw_deg: float | None
    lateral_center_m: float | None
    span_m: float
    point_count: int
    rmse_m: float | None
    confidence: float
    reason: str = ""

    def summary(self) -> str:
        if not self.valid:
            return (
                f"invalid points={self.point_count} span={self.span_m:.3f}m "
                f"confidence={self.confidence:.2f} reason={self.reason}"
            )
        return (
            f"distance={self.robot_distance_m:.3f}m "
            f"sensor_distance={self.sensor_distance_m:.3f}m "
            f"yaw={self.yaw_deg:+.2f}deg lateral={self.lateral_center_m:+.3f}m "
            f"span={self.span_m:.3f}m points={self.point_count} "
            f"rmse={self.rmse_m:.3f}m confidence={self.confidence:.2f}"
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class YDLidarDevice:
    """Thin lifecycle adapter for the vendor YDLidar Python SDK."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.sdk: Any | None = None
        self.laser: Any | None = None
        self.port = ""

    def __enter__(self) -> YDLidarDevice:
        self.open()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def open(self) -> None:
        if self.laser is not None:
            return
        sdk = self._load_sdk()
        sdk.os_init()
        self.port = self._resolve_port(sdk)
        laser = sdk.CYdLidar()

        laser.setlidaropt(sdk.LidarPropSerialPort, self.port)
        laser.setlidaropt(sdk.LidarPropIgnoreArray, "")
        laser.setlidaropt(
            sdk.LidarPropSerialBaudrate,
            int(self.config.get("baudrate", 230400)),
        )
        laser.setlidaropt(sdk.LidarPropLidarType, sdk.TYPE_TRIANGLE)
        laser.setlidaropt(sdk.LidarPropDeviceType, sdk.YDLIDAR_TYPE_SERIAL)
        laser.setlidaropt(
            sdk.LidarPropSampleRate,
            int(self.config.get("sample_rate_khz", 4)),
        )
        laser.setlidaropt(sdk.LidarPropIntenstiyBit, 8)
        laser.setlidaropt(sdk.LidarPropFixedResolution, True)
        laser.setlidaropt(sdk.LidarPropReversion, False)
        laser.setlidaropt(sdk.LidarPropInverted, False)
        laser.setlidaropt(sdk.LidarPropAutoReconnect, True)
        laser.setlidaropt(sdk.LidarPropSingleChannel, False)
        laser.setlidaropt(sdk.LidarPropIntenstiy, True)
        laser.setlidaropt(sdk.LidarPropSupportMotorDtrCtrl, False)
        laser.setlidaropt(sdk.LidarPropSupportHeartBeat, False)
        laser.setlidaropt(sdk.LidarPropMaxAngle, 180.0)
        laser.setlidaropt(sdk.LidarPropMinAngle, -180.0)
        laser.setlidaropt(
            sdk.LidarPropMaxRange,
            float(self.config.get("max_range_m", 8.0)),
        )
        laser.setlidaropt(
            sdk.LidarPropMinRange,
            float(self.config.get("min_range_m", 0.08)),
        )
        laser.setlidaropt(
            sdk.LidarPropScanFrequency,
            float(self.config.get("scan_frequency_hz", 10.0)),
        )

        if not laser.initialize():
            error = laser.DescribeError()
            laser.disconnecting()
            raise RuntimeError(f"雷达初始化失败: {error}")
        if not laser.turnOn():
            laser.disconnecting()
            raise RuntimeError(f"雷达启动扫描失败: {laser.DescribeError()}")
        self.sdk = sdk
        self.laser = laser

    def read_scan(self) -> LidarScan | None:
        if self.sdk is None or self.laser is None:
            raise RuntimeError("雷达尚未打开")
        raw_scan = self.sdk.LaserScan()
        if not self.laser.doProcessSimple(raw_scan):
            return None

        direction = -1.0 if bool(self.config.get("clockwise_angles", False)) else 1.0
        offset = math.radians(float(self.config.get("angle_offset_deg", 0.0)))
        points = tuple(
            LidarPoint(
                angle_rad=_normalize_angle(direction * float(point.angle) + offset),
                range_m=float(point.range),
                intensity=float(point.intensity),
            )
            for point in raw_scan.points
            if float(point.range) > 0
        )
        return LidarScan(
            points=points,
            captured_at=time.monotonic(),
            scan_frequency_hz=float(getattr(raw_scan, "scanFreq", 0.0)),
        )

    def close(self) -> None:
        laser = self.laser
        self.laser = None
        if laser is None:
            return
        try:
            laser.turnOff()
        finally:
            laser.disconnecting()

    def _load_sdk(self) -> Any:
        sdk_path = str(self.config.get("sdk_python_path", "")).strip()
        if sdk_path and sdk_path not in sys.path:
            sys.path.insert(0, sdk_path)
        try:
            return importlib.import_module("ydlidar")
        except ImportError as exc:
            raise RuntimeError(
                "无法导入 ydlidar；请检查 config.json 的 lidar.sdk_python_path "
                "或在板端 xgovenv 中安装厂家 SDK"
            ) from exc

    def _resolve_port(self, sdk: Any) -> str:
        configured = str(self.config.get("port", "")).strip()
        fallback = str(self.config.get("fallback_port", "/dev/ttyUSB0")).strip()
        for candidate in (configured, fallback):
            if candidate and Path(candidate).exists():
                return candidate

        detected = sorted(set(sdk.lidarPortList().values()))
        detected = [port for port in detected if port != "/dev/ttyAMA0"]
        if len(detected) == 1:
            return detected[0]
        if detected:
            raise RuntimeError(f"检测到多个雷达候选串口，请在配置中指定: {detected}")
        raise RuntimeError(
            f"未找到雷达串口，已检查 {configured or '(未配置)'} 和 {fallback}"
        )


class FrontWallEstimator:
    """Estimate a nearby frontal planar target without ROS or global mapping."""

    def __init__(self, config: dict[str, Any]):
        self.config = config

    def estimate(self, scan: LidarScan) -> WallEstimate:
        center = math.radians(float(self.config.get("front_center_deg", 0.0)))
        half_width = math.radians(float(self.config.get("front_half_width_deg", 35.0)))
        min_range = float(self.config.get("min_range_m", 0.08))
        max_range = float(self.config.get("localization_max_range_m", 2.5))
        min_intensity = float(self.config.get("minimum_intensity", 0.0))

        points: list[tuple[float, float]] = []
        for point in scan.points:
            relative_angle = _normalize_angle(point.angle_rad - center)
            if abs(relative_angle) > half_width:
                continue
            if not min_range <= point.range_m <= max_range:
                continue
            if point.intensity < min_intensity:
                continue
            x = point.range_m * math.cos(relative_angle)
            y = point.range_m * math.sin(relative_angle)
            if x > 0:
                points.append((y, x))

        min_points = max(2, int(self.config.get("minimum_wall_points", 8)))
        if len(points) < min_points:
            return self._invalid(len(points), "前向有效点不足")

        nearest_quantile = _clamp(
            float(self.config.get("nearest_quantile", 0.3)),
            0.0,
            1.0,
        )
        depth_window = max(0.01, float(self.config.get("surface_depth_window_m", 0.15)))
        nearest_x = _quantile(sorted(x for _, x in points), nearest_quantile)
        surface = [(y, x) for y, x in points if x <= nearest_x + depth_window]
        if len(surface) < min_points:
            return self._invalid(len(surface), "最近表面点不足")

        residual_limit = max(
            0.005,
            float(self.config.get("wall_residual_limit_m", 0.035)),
        )
        slope, intercept, inliers = _fit_line_ransac(surface, residual_limit)
        if slope is None or intercept is None or len(inliers) < min_points:
            return self._invalid(len(inliers), "未找到稳定直线")

        ys = [y for y, _ in inliers]
        span = max(ys) - min(ys)
        minimum_span = float(self.config.get("minimum_wall_span_m", 0.12))
        residuals = [x - (slope * y + intercept) for y, x in inliers]
        rmse = math.sqrt(sum(value * value for value in residuals) / len(residuals))
        maximum_rmse = float(self.config.get("maximum_wall_rmse_m", 0.03))
        valid = intercept > 0 and span >= minimum_span and rmse <= maximum_rmse

        count_score = min(1.0, len(inliers) / max(min_points * 2, 1))
        span_score = min(1.0, span / max(minimum_span * 2, 0.01))
        residual_score = max(0.0, 1.0 - rmse / max(maximum_rmse, 0.001))
        confidence = 0.4 * count_score + 0.3 * span_score + 0.3 * residual_score
        sensor_forward_offset = float(self.config.get("sensor_forward_offset_m", 0.0))
        sensor_left_offset = float(self.config.get("sensor_left_offset_m", 0.0))
        reason = "" if valid else "直线跨度或拟合误差不满足要求"
        return WallEstimate(
            valid=valid,
            sensor_distance_m=intercept,
            robot_distance_m=intercept + sensor_forward_offset,
            yaw_deg=math.degrees(math.atan(slope)),
            lateral_center_m=sum(ys) / len(ys) + sensor_left_offset,
            span_m=span,
            point_count=len(inliers),
            rmse_m=rmse,
            confidence=confidence,
            reason=reason,
        )

    @staticmethod
    def _invalid(point_count: int, reason: str) -> WallEstimate:
        return WallEstimate(
            valid=False,
            sensor_distance_m=None,
            robot_distance_m=None,
            yaw_deg=None,
            lateral_center_m=None,
            span_m=0.0,
            point_count=point_count,
            rmse_m=None,
            confidence=0.0,
            reason=reason,
        )


def _fit_line_ransac(
    points: list[tuple[float, float]],
    residual_limit: float,
) -> tuple[float | None, float | None, list[tuple[float, float]]]:
    sample = points
    if len(sample) > 120:
        step = len(sample) / 120
        sample = [sample[int(index * step)] for index in range(120)]

    best: list[tuple[float, float]] = []
    for first_index, (y1, x1) in enumerate(sample):
        for y2, x2 in sample[first_index + 1 :]:
            if abs(y2 - y1) < 0.02:
                continue
            slope = (x2 - x1) / (y2 - y1)
            intercept = x1 - slope * y1
            inliers = [
                point
                for point in points
                if abs(point[1] - (slope * point[0] + intercept)) <= residual_limit
            ]
            if len(inliers) > len(best):
                best = inliers
    if len(best) < 2:
        return None, None, best
    slope, intercept = _least_squares(best)
    return slope, intercept, best


def _least_squares(points: Iterable[tuple[float, float]]) -> tuple[float, float]:
    values = list(points)
    mean_y = sum(y for y, _ in values) / len(values)
    mean_x = sum(x for _, x in values) / len(values)
    denominator = sum((y - mean_y) ** 2 for y, _ in values)
    if denominator <= 1e-9:
        return 0.0, mean_x
    slope = sum((y - mean_y) * (x - mean_x) for y, x in values) / denominator
    return slope, mean_x - slope * mean_y


def _quantile(sorted_values: list[float], ratio: float) -> float:
    index = round((len(sorted_values) - 1) * ratio)
    return sorted_values[index]


def _normalize_angle(angle: float) -> float:
    return (angle + math.pi) % (2 * math.pi) - math.pi


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
