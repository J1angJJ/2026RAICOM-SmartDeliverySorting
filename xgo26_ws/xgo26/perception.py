from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .camera import camera_reader_from_config
from .config import resolve_path
from .yolo import YoloDetection, YoloDetector


RED_PACKAGES = {"clothes", "paper", "toothbrush"}
BLUE_PACKAGES = {"apple", "orange", "banana"}
PACKAGE_CN = {
    "clothes": "衣服",
    "paper": "卫生纸",
    "toothbrush": "牙刷",
    "apple": "苹果",
    "orange": "橘子",
    "banana": "香蕉",
}


@dataclass(frozen=True)
class DeliveryTask:
    letter: str
    package: str
    ball_color: str
    confidence: float = 1.0

    @property
    def package_cn(self) -> str:
        return PACKAGE_CN.get(self.package, self.package)

    def summary(self) -> str:
        return f"{self.letter} {self.package_cn} {self.ball_color}"


@dataclass(frozen=True)
class BallDetection:
    color: str
    x: int
    y: int
    radius: int
    width: int
    height: int
    normalized_x: float
    normalized_y: float
    box_x: int
    box_y: int
    box_width: int
    box_height: int
    area: float
    touches_bottom: bool

    @property
    def box_center_x_normalized(self) -> float:
        return 2 * (self.box_x + self.box_width / 2) / self.width - 1

    @property
    def box_top_ratio(self) -> float:
        return self.box_y / self.height

    @property
    def box_width_ratio(self) -> float:
        return self.box_width / self.width

    @property
    def box_aspect_ratio(self) -> float:
        return self.box_width / max(1, self.box_height)

    def centered(self, target_x: float, target_y: float, tolerance_x: float, tolerance_y: float) -> bool:
        return (
            abs(self.normalized_x - target_x) <= tolerance_x
            and abs(self.normalized_y - target_y) <= tolerance_y
        )

    def ready_for_grasp(
        self,
        target_x: float,
        tolerance_x: float,
        target_top_ratio: float,
        tolerance_top_ratio: float,
        target_width_ratio: float,
        tolerance_width_ratio: float,
        min_width_ratio: float,
        require_bottom: bool = True,
    ) -> bool:
        return (
            abs(self.box_center_x_normalized - target_x) <= tolerance_x
            and abs(self.box_top_ratio - target_top_ratio) <= tolerance_top_ratio
            and abs(self.box_width_ratio - target_width_ratio) <= tolerance_width_ratio
            and self.box_width_ratio >= min_width_ratio
            and (self.touches_bottom or not require_bottom)
        )

    def summary(self) -> str:
        return (
            f"{self.color} pixel=({self.x},{self.y}) radius={self.radius} "
            f"norm=({self.normalized_x:.2f},{self.normalized_y:.2f}) "
            f"box=({self.box_x},{self.box_y},{self.box_width},{self.box_height}) "
            f"box_x={self.box_center_x_normalized:.2f} top={self.box_top_ratio:.2f} "
            f"width={self.box_width_ratio:.2f} bottom={self.touches_bottom}"
        )


def ball_color_for_package(package: str) -> str:
    if package in RED_PACKAGES:
        return "red"
    if package in BLUE_PACKAGES:
        return "blue"
    raise ValueError(f"未知包裹类别: {package}")


class PackageDetector:
    def __init__(
        self,
        model_path: str | Path,
        conf: float = 0.45,
        *,
        iou: float = 0.45,
        image_size: int = 640,
        device: str = "cpu",
        max_detections: int = 20,
        detector: YoloDetector | None = None,
    ):
        self.model_path = resolve_path(model_path)
        self.detector = detector or YoloDetector(
            self.model_path,
            confidence=conf,
            iou=iou,
            image_size=image_size,
            device=device,
            max_detections=max_detections,
        )

    def available(self) -> bool:
        return self.detector.available()

    def detect_objects(self, frame: Any) -> tuple[YoloDetection, ...]:
        return self.detector.predict(frame).detections

    def detect_frame(self, frame: Any) -> DeliveryTask | None:
        if not self.available():
            return None
        packages: list[tuple[str, float]] = []
        letters: list[tuple[str, float]] = []
        for detection in self.detect_objects(frame):
            name = detection.class_name.strip()
            canonical_package = name.lower()
            if canonical_package in RED_PACKAGES | BLUE_PACKAGES:
                packages.append((canonical_package, detection.confidence))
            elif name.upper() in {"A", "B", "C", "D"}:
                letters.append((name.upper(), detection.confidence))
        if not packages or not letters:
            return None
        package, package_confidence = max(packages, key=lambda item: item[1])
        letter, letter_confidence = max(letters, key=lambda item: item[1])
        return DeliveryTask(
            letter=letter,
            package=package,
            ball_color=ball_color_for_package(package),
            confidence=min(package_confidence, letter_confidence),
        )

    def detect_or_expected(self, expected: dict[str, str] | None = None) -> DeliveryTask:
        if expected:
            package = expected["package"]
            return DeliveryTask(
                letter=expected["letter"].upper(),
                package=package,
                ball_color=ball_color_for_package(package),
            )

        if not self.available():
            raise RuntimeError(f"包裹模型不存在，且未提供 expected task: {self.model_path}")

        raise RuntimeError("真实包裹识别需要传入相机画面")


def capture_and_vote_expected(
    config: dict,
    expected: dict[str, str] | None,
) -> DeliveryTask:
    detector = PackageDetector(
        config["models"]["package_model"],
        conf=float(config["detection"].get("confidence", 0.45)),
        iou=float(config["detection"].get("iou", 0.45)),
        image_size=int(config["detection"].get("image_size", 640)),
        device=str(config["detection"].get("device", "cpu")),
        max_detections=int(config["detection"].get("max_detections", 20)),
    )
    if expected is not None or not detector.available():
        task = detector.detect_or_expected(expected)
        print(f"[perception] use expected/dry result: {task.summary()}")
        return task

    camera_cfg = config["camera"]
    votes: list[DeliveryTask] = []
    with camera_reader_from_config(
        camera_cfg,
        stream=str(config["detection"].get("camera_stream", "main")),
        width=int(camera_cfg.get("width", 1296)),
        height=int(camera_cfg.get("height", 972)),
        warmup_frames=int(camera_cfg.get("warmup_frames", 5)),
    ) as reader:
        for _ in range(int(config["detection"].get("frames", 3))):
            frame = reader.read()
            if frame is None:
                continue
            task = detector.detect_frame(frame)
            if task is not None:
                votes.append(task)
    if not votes:
        raise RuntimeError("多帧识别未得到有效包裹任务")
    key = Counter((task.letter, task.package) for task in votes).most_common(1)[0][0]
    matching = [task.confidence for task in votes if (task.letter, task.package) == key]
    return DeliveryTask(
        letter=key[0],
        package=key[1],
        ball_color=ball_color_for_package(key[1]),
        confidence=sum(matching) / len(matching),
    )


def find_colored_ball(
    frame: Any,
    threshold: list[int],
    roi_top_ratio: float = 0.0,
) -> tuple[int, int, int] | None:
    found = _find_colored_ball_contour(frame, threshold, roi_top_ratio)
    return found[1] if found is not None else None


def _find_colored_ball_contour(
    frame: Any,
    threshold: list[int],
    roi_top_ratio: float = 0.0,
) -> tuple[Any, tuple[int, int, int]] | None:
    found = _find_colored_ball_contours(frame, threshold, roi_top_ratio)
    return found[0] if found else None


def _find_colored_ball_contours(
    frame: Any,
    threshold: list[int],
    roi_top_ratio: float = 0.0,
) -> list[tuple[Any, tuple[int, int, int]]]:
    import cv2
    import numpy as np

    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    mask = cv2.inRange(
        lab,
        (threshold[0], threshold[2], threshold[4]),
        (threshold[1], threshold[3], threshold[5]),
    )
    roi_top = int(frame.shape[0] * max(0.0, min(1.0, roi_top_ratio)))
    mask[:roi_top, :] = 0
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    found: list[tuple[Any, tuple[int, int, int]]] = []
    for contour in sorted(contours, key=cv2.contourArea, reverse=True):
        (x, y), radius = cv2.minEnclosingCircle(contour)
        if radius >= 5:
            found.append((contour, (int(x), int(y), int(radius))))
    return found


def _ball_detection_from_contour(
    frame: Any,
    color: str,
    contour: Any,
    circle: tuple[int, int, int],
) -> BallDetection:
    import cv2

    x, y, radius = circle
    height, width = frame.shape[:2]
    box_x, box_y, box_width, box_height = cv2.boundingRect(contour)
    nx, ny = normalize_center(x, y, width, height)
    return BallDetection(
        color=color,
        x=x,
        y=y,
        radius=radius,
        width=width,
        height=height,
        normalized_x=nx,
        normalized_y=ny,
        box_x=box_x,
        box_y=box_y,
        box_width=box_width,
        box_height=box_height,
        area=float(cv2.contourArea(contour)),
        touches_bottom=box_y + box_height >= height - 1,
    )


def detect_colored_balls(
    frame: Any,
    color: str,
    threshold: list[int],
    roi_top_ratio: float = 0.0,
) -> list[BallDetection]:
    return [
        _ball_detection_from_contour(frame, color, contour, circle)
        for contour, circle in _find_colored_ball_contours(
            frame,
            threshold,
            roi_top_ratio,
        )
    ]


def detect_colored_ball(
    frame: Any,
    color: str,
    threshold: list[int],
    roi_top_ratio: float = 0.0,
) -> BallDetection | None:
    detections = detect_colored_balls(frame, color, threshold, roi_top_ratio)
    return detections[0] if detections else None


def normalize_center(x: int, y: int, width: int, height: int) -> tuple[float, float]:
    return 2 * x / width - 1, 1 - 2 * y / height


def save_ball_debug_image(
    frame: Any,
    output_path: str | Path,
    detection: BallDetection | None,
    target_x: float = 0.0,
    target_y: float = -0.85,
) -> Path:
    import cv2

    path = resolve_path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    annotated = frame.copy()
    height, width = annotated.shape[:2]
    tx = int((target_x + 1) * width / 2)
    ty = int((1 - target_y) * height / 2)
    cv2.drawMarker(annotated, (tx, ty), (0, 255, 255), cv2.MARKER_CROSS, 18, 2)
    if detection is not None:
        cv2.rectangle(
            annotated,
            (detection.box_x, detection.box_y),
            (detection.box_x + detection.box_width - 1, detection.box_y + detection.box_height - 1),
            (255, 0, 255),
            2,
        )
        cv2.circle(annotated, (detection.x, detection.y), detection.radius, (0, 255, 0), 2)
        cv2.circle(annotated, (detection.x, detection.y), 3, (0, 0, 255), -1)
        cv2.line(annotated, (detection.x, detection.y), (tx, ty), (255, 255, 0), 1)
    cv2.imwrite(str(path), annotated)
    return path
