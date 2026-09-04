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


def normalize_center(x: int, y: int, width: int, height: int) -> tuple[float, float]:
    return 2 * x / width - 1, 1 - 2 * y / height

