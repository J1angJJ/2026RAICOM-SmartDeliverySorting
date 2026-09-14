from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LineDetection:
    near_x: float
    far_x: float
    target_x: float
    width: int
    height: int
    points: tuple[tuple[int, int], ...]
    line_width: float
    center_error: float
    heading_error: float
    steering_error: float
    confidence: float

    def summary(self) -> str:
        return (
            f"line near={self.near_x:.1f} far={self.far_x:.1f} "
            f"center={self.center_error:+.3f} heading={self.heading_error:+.3f} "
            f"steering={self.steering_error:+.3f} confidence={self.confidence:.2f}"
        )


@dataclass(frozen=True)
class CornerDetection:
    direction: str
    x: int
    y: int
    horizontal_span: int
    confidence: float

    def summary(self) -> str:
        return (
            f"corner direction={self.direction} pixel=({self.x},{self.y}) "
            f"span={self.horizontal_span} confidence={self.confidence:.2f}"
        )


class LineTracker:
    """Track a dark floor strip using several horizontal scan bands."""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self._last_near_x: float | None = None
        self._smoothed_steering: float | None = None
        self._lost_frames = 0
        self.last_mask: Any | None = None
        self.last_corner: CornerDetection | None = None

    def process(self, frame: Any) -> LineDetection | None:
        import cv2
        import numpy as np

        cfg = self.config
        height, width = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur_size = _odd(int(cfg.get("blur_size", 5)), minimum=1)
        if blur_size > 1:
            gray = cv2.GaussianBlur(gray, (blur_size, blur_size), 0)

        threshold = int(cfg.get("dark_threshold", 105))
        mask = cv2.inRange(gray, 0, threshold)
        roi_top = int(height * float(cfg.get("roi_top_ratio", 0.48)))
        roi_bottom = int(height * float(cfg.get("roi_bottom_ratio", 0.98)))
        mask[: max(0, roi_top), :] = 0
        mask[min(height, roi_bottom) :, :] = 0

        margin = int(width * float(cfg.get("side_margin_ratio", 0.04)))
        if margin > 0:
            mask[:, :margin] = 0
            mask[:, width - margin :] = 0

        kernel_size = max(1, int(cfg.get("kernel_size", 3)))
        kernel = np.ones((kernel_size, kernel_size), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        self.last_mask = mask

        target_x = width * float(cfg.get("target_x_ratio", 0.5))
        expected_x = self._last_near_x if self._last_near_x is not None else target_x
        initial_expected_x = expected_x
        points: list[tuple[int, int]] = []
        line_widths: list[int] = []
        scores: list[float] = []

        bands = cfg.get(
            "scan_bands",
            [[0.58, 0.66], [0.72, 0.80], [0.86, 0.96]],
        )
        for top_ratio, bottom_ratio in reversed(bands):
            y0 = max(0, min(height - 1, int(height * float(top_ratio))))
            y1 = max(y0 + 1, min(height, int(height * float(bottom_ratio))))
            candidate = _find_band_candidate(mask[y0:y1], expected_x, width, cfg)
            if candidate is None:
                continue
            center_x, run_width, score = candidate
            center_y = (y0 + y1) // 2
            points.append((int(round(center_x)), center_y))
            line_widths.append(run_width)
            scores.append(score)
            expected_x = center_x

        line_reference_x = points[0][0] if points else initial_expected_x
        corner_hint = _detect_corner(mask, line_reference_x, cfg)
        if corner_hint is not None:
            keep = [
                index
                for index, point in enumerate(points)
                if point[1] >= corner_hint.y
            ]
            points = [points[index] for index in keep]
            line_widths = [line_widths[index] for index in keep]
            scores = [scores[index] for index in keep]
            if not points or abs(points[-1][1] - corner_hint.y) > 3:
                points.append((corner_hint.x, corner_hint.y))
                line_widths.append(line_widths[-1] if line_widths else 1)
                scores.append(corner_hint.confidence)

        minimum_bands = max(1, int(cfg.get("minimum_bands", 2)))
        if len(points) < minimum_bands:
            self.last_corner = corner_hint
            self._mark_lost()
            return None

        near_x = float(points[0][0])
        far_x = float(points[-1][0])
        half_width = max(width * 0.5, 1.0)
        center_error = (near_x - target_x) / half_width
        heading_error = (far_x - near_x) / half_width
        raw_steering = (
            center_error * float(cfg.get("center_weight", 0.75))
            + heading_error * float(cfg.get("heading_weight", 0.55))
        )
        alpha = min(1.0, max(0.0, float(cfg.get("smoothing_alpha", 0.45))))
        if self._smoothed_steering is None:
            steering_error = raw_steering
        else:
            steering_error = alpha * raw_steering + (1.0 - alpha) * self._smoothed_steering

        band_ratio = len(points) / max(len(bands), 1)
        confidence = min(1.0, band_ratio * sum(scores) / max(len(scores), 1))
        if confidence < float(cfg.get("minimum_confidence", 0.35)):
            self.last_corner = corner_hint
            self._mark_lost()
            return None

        self._last_near_x = near_x
        self._smoothed_steering = steering_error
        self._lost_frames = 0
        self.last_corner = corner_hint
        return LineDetection(
            near_x=near_x,
            far_x=far_x,
            target_x=target_x,
            width=width,
            height=height,
            points=tuple(points),
            line_width=sum(line_widths) / len(line_widths),
            center_error=center_error,
            heading_error=heading_error,
            steering_error=steering_error,
            confidence=confidence,
        )

    def _mark_lost(self) -> None:
        self._lost_frames += 1
        keep_frames = max(0, int(self.config.get("memory_frames", 4)))
        if self._lost_frames > keep_frames:
            self._last_near_x = None
            self._smoothed_steering = None


def draw_line_debug(frame: Any, detection: LineDetection | None, mask: Any, config: dict) -> Any:
    import cv2

    output = frame.copy()
    height, width = output.shape[:2]
    roi_top = int(height * float(config.get("roi_top_ratio", 0.48)))
    roi_bottom = int(height * float(config.get("roi_bottom_ratio", 0.98)))
    target_x = int(width * float(config.get("target_x_ratio", 0.5)))
    cv2.rectangle(output, (0, roi_top), (width - 1, roi_bottom), (255, 180, 0), 1)
    cv2.line(output, (target_x, roi_top), (target_x, roi_bottom), (0, 255, 255), 1)

    if detection is not None:
        ordered = sorted(detection.points, key=lambda point: point[1])
        for point in detection.points:
            cv2.circle(output, point, 5, (0, 255, 0), -1)
        for first, second in zip(ordered, ordered[1:]):
            cv2.line(output, first, second, (0, 255, 0), 2)
        label = (
            f"steer={detection.steering_error:+.3f} "
            f"heading={detection.heading_error:+.3f} conf={detection.confidence:.2f}"
        )
    else:
        label = "LINE LOST"
    cv2.putText(output, label, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 255), 1)

    mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
    return cv2.hconcat([output, mask_bgr])


def draw_corner_debug(output: Any, corner: CornerDetection | None) -> Any:
    import cv2

    if corner is None:
        return output
    color = (255, 0, 255)
    cv2.circle(output, (corner.x, corner.y), 7, color, 2)
    arrow = 45 if corner.direction == "right" else -45
    cv2.arrowedLine(
        output,
        (corner.x, corner.y),
        (corner.x + arrow, corner.y),
        color,
        3,
        tipLength=0.3,
    )
    return output


def _detect_corner(mask: Any, line_x: float, config: dict) -> CornerDetection | None:
    import cv2

    height, width = mask.shape
    min_span = max(9, int(width * float(config.get("corner_minimum_span_ratio", 0.22))))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (min_span, 3))
    horizontal = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    contours, _ = cv2.findContours(horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    join_tolerance = width * float(config.get("corner_join_tolerance_ratio", 0.08))
    minimum_side = width * float(config.get("corner_minimum_side_ratio", 0.16))
    minimum_y = height * float(config.get("corner_minimum_y_ratio", 0.52))
    maximum_y = height * float(config.get("corner_maximum_y_ratio", 0.90))
    maximum_height = height * float(config.get("corner_maximum_height_ratio", 0.14))

    best: CornerDetection | None = None
    for contour in contours:
        x, y, span, thickness = cv2.boundingRect(contour)
        center_y = y + thickness // 2
        if (
            span < min_span
            or thickness > maximum_height
            or center_y < minimum_y
            or center_y > maximum_y
        ):
            continue
        if x > line_x + join_tolerance or x + span < line_x - join_tolerance:
            continue
        left_span = max(0.0, line_x - x)
        right_span = max(0.0, x + span - line_x)
        if right_span >= minimum_side and right_span > left_span * 1.25:
            direction = "right"
            side_span = right_span
        elif left_span >= minimum_side and left_span > right_span * 1.25:
            direction = "left"
            side_span = left_span
        else:
            continue
        confidence = min(1.0, side_span / max(width * 0.5, 1.0))
        candidate = CornerDetection(
            direction=direction,
            x=int(round(line_x)),
            y=center_y,
            horizontal_span=span,
            confidence=confidence,
        )
        if best is None or candidate.confidence > best.confidence:
            best = candidate
    return best


def _find_band_candidate(
    band: Any,
    expected_x: float,
    frame_width: int,
    config: dict,
) -> tuple[float, int, float] | None:
    import numpy as np

    if band.size == 0:
        return None
    coverage = np.count_nonzero(band, axis=0) / float(band.shape[0])
    active = coverage >= float(config.get("minimum_column_fill", 0.25))
    min_width = max(2, int(frame_width * float(config.get("minimum_width_ratio", 0.006))))
    max_width = max(min_width, int(frame_width * float(config.get("maximum_width_ratio", 0.18))))
    expected_width = max(min_width, frame_width * float(config.get("expected_width_ratio", 0.06)))
    max_jump = max(1.0, frame_width * float(config.get("maximum_jump_ratio", 0.28)))

    best: tuple[float, int, float] | None = None
    for start, end in _true_runs(active):
        run_width = end - start
        if run_width < min_width or run_width > max_width:
            continue
        weights = coverage[start:end]
        center = float(np.average(np.arange(start, end), weights=weights))
        distance = abs(center - expected_x)
        if distance > max_jump:
            continue
        fill_score = float(np.mean(weights))
        width_score = min(run_width / expected_width, expected_width / run_width)
        distance_score = 1.0 - distance / max_jump
        score = 0.45 * distance_score + 0.35 * fill_score + 0.20 * width_score
        if best is None or score > best[2]:
            best = center, run_width, score
    return best


def _true_runs(values: Any) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for index, value in enumerate(values):
        if value and start is None:
            start = index
        elif not value and start is not None:
            runs.append((start, index))
            start = None
    if start is not None:
        runs.append((start, len(values)))
    return runs


def _odd(value: int, minimum: int = 1) -> int:
    value = max(minimum, value)
    return value if value % 2 else value + 1
