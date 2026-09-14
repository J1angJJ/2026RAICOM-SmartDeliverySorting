from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .camera import camera_reader_from_config
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
        min_width_ratio: float,
        require_bottom: bool = True,
    ) -> bool:
        return (
            abs(self.box_center_x_normalized - target_x) <= tolerance_x
            and abs(self.box_top_ratio - target_top_ratio) <= tolerance_top_ratio
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
    key = Counter((task.letter, task.package, task.ball_color) for task in votes).most_common(1)[0][0]
    return DeliveryTask(*key)


def find_colored_ball(frame: Any, threshold: list[int]) -> tuple[int, int, int] | None:
    found = _find_colored_ball_contour(frame, threshold)
    return found[1] if found is not None else None


def _find_colored_ball_contour(
    frame: Any, threshold: list[int]
) -> tuple[Any, tuple[int, int, int]] | None:
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
    return contour, (int(x), int(y), int(radius))


def detect_colored_ball(frame: Any, color: str, threshold: list[int]) -> BallDetection | None:
    import cv2

    found = _find_colored_ball_contour(frame, threshold)
    if found is None:
        return None
    contour, (x, y, radius) = found
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
