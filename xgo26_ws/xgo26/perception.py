from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .camera import capture_frame
from .config import ROOT, resolve_path


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

    def centered(self, target_x: float, target_y: float, tolerance_x: float, tolerance_y: float) -> bool:
        return (
            abs(self.normalized_x - target_x) <= tolerance_x
            and abs(self.normalized_y - target_y) <= tolerance_y
        )

    def summary(self) -> str:
        return (
            f"{self.color} pixel=({self.x},{self.y}) radius={self.radius} "
            f"norm=({self.normalized_x:.2f},{self.normalized_y:.2f})"
        )


@dataclass(frozen=True)
class LineDetection:
    x: int
    y: int
    width: int
    height: int
    roi_top: int
    area: float
    normalized_x: float

    def summary(self) -> str:
        return (
            f"line pixel=({self.x},{self.y}) norm_x={self.normalized_x:.2f} "
            f"area={self.area:.0f}"
        )


def ball_color_for_package(package: str) -> str:
    if package in RED_PACKAGES:
        return "red"
    if package in BLUE_PACKAGES:
        return "blue"
    raise ValueError(f"未知包裹类别: {package}")


class PackageDetector:
    class_names = {
        0: "clothes",
        1: "paper",
        2: "toothbrush",
        3: "apple",
        4: "orange",
        5: "banana",
        6: "A",
        7: "B",
        8: "C",
        9: "D",
    }

    def __init__(self, model_path: str | Path, conf: float = 0.45):
        self.model_path = resolve_path(model_path)
        self.conf = conf
        self.session: Any | None = None
        self.input_name = ""
        self.output_names: list[str] = []
        if self.model_path.exists():
            import onnxruntime as ort

            options = ort.SessionOptions()
            options.intra_op_num_threads = 2
            options.inter_op_num_threads = 1
            self.session = ort.InferenceSession(
                str(self.model_path),
                sess_options=options,
                providers=["CPUExecutionProvider"],
            )
            self.input_name = self.session.get_inputs()[0].name
            self.output_names = [out.name for out in self.session.get_outputs()]

    def available(self) -> bool:
        return self.session is not None

    def detect_frame(self, frame: Any) -> DeliveryTask | None:
        if self.session is None:
            return None
        # 模型训练后在这里补充正式后处理。当前骨架先保留接口。
        raise NotImplementedError("package_letter.onnx 后处理待模型类别和输出格式确定后实现")

    def detect_or_expected(self, expected: dict[str, str] | None = None) -> DeliveryTask:
        if expected:
            package = expected["package"]
            return DeliveryTask(
                letter=expected["letter"].upper(),
                package=package,
                ball_color=ball_color_for_package(package),
            )

        if self.session is None:
            raise RuntimeError(f"包裹模型不存在，且未提供 expected task: {self.model_path}")

        raise NotImplementedError("真实包裹识别待模型完成后接入")


def capture_and_vote_expected(
    config: dict,
    expected: dict[str, str] | None,
) -> DeliveryTask:
    detector = PackageDetector(
        config["models"]["package_model"],
        conf=float(config["detection"].get("confidence", 0.45)),
    )
    if expected is not None or not detector.available():
        task = detector.detect_or_expected(expected)
        print(f"[perception] use expected/dry result: {task.summary()}")
        return task

    camera_cfg = config["camera"]
    votes: list[DeliveryTask] = []
    for _ in range(int(config["detection"].get("frames", 3))):
        ok, frame = capture_frame(
            camera_index=int(camera_cfg.get("index", 0)),
            width=int(camera_cfg.get("width", 640)),
            height=int(camera_cfg.get("height", 480)),
            warmup_frames=int(camera_cfg.get("warmup_frames", 5)),
        )
        if not ok:
            continue
        task = detector.detect_frame(frame)
        if task is not None:
            votes.append(task)
    if not votes:
        raise RuntimeError("多帧识别未得到有效包裹任务")
    key = Counter((task.letter, task.package, task.ball_color) for task in votes).most_common(1)[0][0]
    return DeliveryTask(*key)


def find_colored_ball(frame: Any, threshold: list[int]) -> tuple[int, int, int] | None:
    import cv2
    import numpy as np

    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    mask = cv2.inRange(
        lab,
        (threshold[0], threshold[2], threshold[4]),
        (threshold[1], threshold[3], threshold[5]),
    )
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    (x, y), radius = cv2.minEnclosingCircle(contour)
    if radius < 5:
        return None
    return int(x), int(y), int(radius)


def detect_black_line(frame: Any, config: dict | None = None) -> LineDetection | None:
    import cv2
    import numpy as np

    cfg = config or {}
    height, width = frame.shape[:2]
    roi_top_ratio = float(cfg.get("roi_top_ratio", 0.55))
    roi_top = int(height * roi_top_ratio)
    roi = frame[roi_top:, :]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    if cfg.get("adaptive", True):
        block_size = int(cfg.get("adaptive_block_size", 21))
        if block_size % 2 == 0:
            block_size += 1
        block_size = max(3, block_size)
        mask = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            block_size,
            int(cfg.get("adaptive_c", 5)),
        )
    else:
        _, mask = cv2.threshold(
            gray,
            int(cfg.get("threshold", 80)),
            255,
            cv2.THRESH_BINARY_INV,
        )

    kernel_size = int(cfg.get("kernel_size", 5))
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    contour = max(contours, key=cv2.contourArea)
    area = float(cv2.contourArea(contour))
    if area < float(cfg.get("min_area", 120)):
        return None

    moments = cv2.moments(contour)
    if moments["m00"] == 0:
        return None

    x = int(moments["m10"] / moments["m00"])
    y = int(moments["m01"] / moments["m00"]) + roi_top
    return LineDetection(
        x=x,
        y=y,
        width=width,
        height=height,
        roi_top=roi_top,
        area=area,
        normalized_x=2 * x / width - 1,
    )


def detect_colored_ball(frame: Any, color: str, threshold: list[int]) -> BallDetection | None:
    found = find_colored_ball(frame, threshold)
    if found is None:
        return None
    x, y, radius = found
    height, width = frame.shape[:2]
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
    )


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
        cv2.circle(annotated, (detection.x, detection.y), detection.radius, (0, 255, 0), 2)
        cv2.circle(annotated, (detection.x, detection.y), 3, (0, 0, 255), -1)
        cv2.line(annotated, (detection.x, detection.y), (tx, ty), (255, 255, 0), 1)
    cv2.imwrite(str(path), annotated)
    return path
