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
class CubeEstimate:
    valid: bool
    sensor_distance_m: float | None
    robot_distance_m: float | None
    yaw_deg: float | None
    lateral_center_m: float | None
    face_width_m: float
    point_count: int
    rmse_m: float | None
    confidence: float
    reason: str = ""

    def summary(self) -> str:
        if not self.valid:
            return (
                f"invalid points={self.point_count} face_width={self.face_width_m:.3f}m "
                f"confidence={self.confidence:.2f} reason={self.reason}"
            )
        return (
            f"distance={self.robot_distance_m:.3f}m "
            f"sensor_distance={self.sensor_distance_m:.3f}m "
            f"yaw={self.yaw_deg:+.2f}deg lateral={self.lateral_center_m:+.3f}m "
            f"face_width={self.face_width_m:.3f}m points={self.point_count} "
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


class CubeLandmarkEstimator:
    """Locate the finite 30 cm front face of a recognition cube."""

    def __init__(self, config: dict[str, Any]):
        self.config = config

    def estimate(self, scan: LidarScan) -> CubeEstimate:
        scan = filter_self_returns(scan, self.config)
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

        min_points = max(2, int(self.config.get("minimum_face_points", 8)))
        if len(points) < min_points:
            return self._invalid(len(points), "前向有效点不足")

        clusters = _split_point_clusters(
            points,
            maximum_gap_m=float(self.config.get("cluster_gap_m", 0.08)),
            maximum_depth_jump_m=float(
                self.config.get("cluster_depth_jump_m", 0.12)
            ),
        )
        residual_limit = max(
            0.005,
            float(self.config.get("face_residual_limit_m", 0.035)),
        )
        expected_width = float(self.config.get("cube_face_width_m", 0.30))
        width_tolerance = float(self.config.get("cube_face_width_tolerance_m", 0.10))
        minimum_width = max(0.02, expected_width - width_tolerance)
        maximum_width = expected_width + width_tolerance
        maximum_rmse = float(self.config.get("maximum_face_rmse_m", 0.03))
        maximum_yaw = abs(float(self.config.get("maximum_face_yaw_deg", 45.0)))
        minimum_confidence = float(self.config.get("minimum_cube_confidence", 0.45))

        candidates: list[CubeEstimate] = []
        for cluster in clusters:
            if len(cluster) < min_points:
                continue
            slope, intercept, inliers = _fit_line_ransac(cluster, residual_limit)
            if slope is None or intercept is None or len(inliers) < min_points:
                continue
            ys = [y for y, _ in inliers]
            lateral_span = max(ys) - min(ys)
            face_width = lateral_span * math.sqrt(1.0 + slope * slope)
            residuals = [x - (slope * y + intercept) for y, x in inliers]
            rmse = math.sqrt(sum(value * value for value in residuals) / len(residuals))
            yaw = math.degrees(math.atan(slope))
            if not (
                intercept > 0
                and minimum_width <= face_width <= maximum_width
                and rmse <= maximum_rmse
                and abs(yaw) <= maximum_yaw
            ):
                continue

            count_score = min(1.0, len(inliers) / max(min_points * 2, 1))
            width_score = max(
                0.0,
                1.0 - abs(face_width - expected_width) / max(width_tolerance, 0.01),
            )
            residual_score = max(0.0, 1.0 - rmse / max(maximum_rmse, 0.001))
            lateral_center = sum(ys) / len(ys)
            center_score = max(0.0, 1.0 - abs(lateral_center) / max(maximum_width, 0.01))
            confidence = (
                0.25 * count_score
                + 0.35 * width_score
                + 0.25 * residual_score
                + 0.15 * center_score
            )
            sensor_forward_offset = float(
                self.config.get("sensor_forward_offset_m", 0.0)
            )
            sensor_left_offset = float(self.config.get("sensor_left_offset_m", 0.0))
            candidates.append(
                CubeEstimate(
                    valid=confidence >= minimum_confidence,
                    sensor_distance_m=intercept,
                    robot_distance_m=intercept + sensor_forward_offset,
                    yaw_deg=yaw,
                    lateral_center_m=lateral_center + sensor_left_offset,
                    face_width_m=face_width,
                    point_count=len(inliers),
                    rmse_m=rmse,
                    confidence=confidence,
                    reason=(
                        "" if confidence >= minimum_confidence else "箱体置信度不足"
                    ),
                )
            )

        valid_candidates = [candidate for candidate in candidates if candidate.valid]
        if not valid_candidates:
            return self._invalid(len(points), "未找到符合30cm尺寸先验的箱体平面")
        return max(valid_candidates, key=lambda candidate: candidate.confidence)

    @staticmethod
    def _invalid(point_count: int, reason: str) -> CubeEstimate:
        return CubeEstimate(
            valid=False,
            sensor_distance_m=None,
            robot_distance_m=None,
            yaw_deg=None,
            lateral_center_m=None,
            face_width_m=0.0,
            point_count=point_count,
            rmse_m=None,
            confidence=0.0,
            reason=reason,
        )


def filter_self_returns(scan: LidarScan, config: dict[str, Any]) -> LidarScan:
    sectors = config.get("self_return_sectors", [])
    if not sectors:
        return scan
    points = tuple(
        point
        for point in scan.points
        if not any(_point_matches_self_sector(point, sector) for sector in sectors)
    )
    return LidarScan(
        points=points,
        captured_at=scan.captured_at,
        scan_frequency_hz=scan.scan_frequency_hz,
    )


def _point_matches_self_sector(point: LidarPoint, sector: dict[str, Any]) -> bool:
    if point.range_m > float(sector["max_range_m"]):
        return False
    angle = math.degrees(point.angle_rad)
    start = float(sector["start_deg"])
    end = float(sector["end_deg"])
    if start <= end:
        return start <= angle <= end
    return angle >= start or angle <= end


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


def _split_point_clusters(
    points: list[tuple[float, float]],
    maximum_gap_m: float,
    maximum_depth_jump_m: float,
) -> list[list[tuple[float, float]]]:
    ordered = sorted(points, key=lambda point: math.atan2(point[0], point[1]))
    if not ordered:
        return []
    clusters = [[ordered[0]]]
    for current in ordered[1:]:
        previous = clusters[-1][-1]
        spatial_gap = math.hypot(current[0] - previous[0], current[1] - previous[1])
        depth_jump = abs(current[1] - previous[1])
        if spatial_gap > maximum_gap_m or depth_jump > maximum_depth_jump_m:
            clusters.append([current])
        else:
            clusters[-1].append(current)
    return clusters


def _least_squares(points: Iterable[tuple[float, float]]) -> tuple[float, float]:
    values = list(points)
    mean_y = sum(y for y, _ in values) / len(values)
    mean_x = sum(x for _, x in values) / len(values)
    denominator = sum((y - mean_y) ** 2 for y, _ in values)
    if denominator <= 1e-9:
        return 0.0, mean_x
    slope = sum((y - mean_y) * (x - mean_x) for y, x in values) / denominator
    return slope, mean_x - slope * mean_y


def _normalize_angle(angle: float) -> float:
    return (angle + math.pi) % (2 * math.pi) - math.pi
