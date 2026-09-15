from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
import time
from typing import Any

from .config import resolve_path


@dataclass(frozen=True)
class YoloDetection:
    class_id: int
    class_name: str
    confidence: float
    bbox: tuple[int, int, int, int]

    def summary(self) -> str:
        return (
            f"{self.class_name} conf={self.confidence:.3f} "
            f"bbox={self.bbox}"
        )


@dataclass(frozen=True)
class YoloPrediction:
    detections: tuple[YoloDetection, ...]
    inference_ms: float


class YoloDetector:
    """Thin Ultralytics adapter for YOLO26 PT or exported ONNX models."""

    def __init__(
        self,
        model_path: str | Path,
        *,
        confidence: float = 0.45,
        iou: float = 0.45,
        image_size: int = 640,
        device: str = "cpu",
        max_detections: int = 20,
        model: Any | None = None,
    ):
        self.model_path = resolve_path(model_path)
        self.confidence = float(confidence)
        self.iou = float(iou)
        self.image_size = int(image_size)
        self.device = device
        self.max_detections = int(max_detections)
        self._model = model
        self._backend = "injected" if model is not None else ""
        self._input_name = ""
        self._input_size = (self.image_size, self.image_size)
        self._names: dict[int, str] = {}

    def available(self) -> bool:
        return self._model is not None or self.model_path.exists()

    def load(self) -> None:
        if self._model is not None:
            return
        if not self.model_path.exists():
            raise FileNotFoundError(f"YOLO模型不存在: {self.model_path}")
        if self.model_path.suffix.lower() == ".onnx":
            self._load_onnx()
            return
        from ultralytics import YOLO

        self._model = YOLO(str(self.model_path), task="detect")
        self._backend = "ultralytics"

    def predict(self, bgr_frame: Any) -> YoloPrediction:
        self.load()
        if self._backend == "onnxruntime":
            return self._predict_onnx(bgr_frame)
        started = time.perf_counter()
        results = self._model.predict(
            source=bgr_frame,
            imgsz=self.image_size,
            conf=self.confidence,
            iou=self.iou,
            device=self.device,
            max_det=self.max_detections,
            verbose=False,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        result = results[0]
        names = result.names
        detections = []
        if result.boxes is not None:
            boxes = result.boxes.xyxy.cpu().tolist()
            classes = result.boxes.cls.cpu().tolist()
            confidences = result.boxes.conf.cpu().tolist()
            for box, class_id_value, confidence in zip(boxes, classes, confidences):
                class_id = int(class_id_value)
                name = names[class_id] if isinstance(names, dict) else names[class_id]
                detections.append(
                    YoloDetection(
                        class_id=class_id,
                        class_name=str(name),
                        confidence=float(confidence),
                        bbox=tuple(int(round(value)) for value in box),
                    )
                )
        return YoloPrediction(tuple(detections), elapsed_ms)

    def _load_onnx(self) -> None:
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        self._model = ort.InferenceSession(
            str(self.model_path),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        model_input = self._model.get_inputs()[0]
        self._input_name = model_input.name
        height, width = model_input.shape[-2:]
        if isinstance(height, int) and isinstance(width, int):
            self._input_size = (width, height)
        metadata = self._model.get_modelmeta().custom_metadata_map
        raw_names = metadata.get("names", "")
        if raw_names:
            parsed = ast.literal_eval(raw_names)
            if isinstance(parsed, dict):
                self._names = {int(key): str(value) for key, value in parsed.items()}
            elif isinstance(parsed, (list, tuple)):
                self._names = {index: str(value) for index, value in enumerate(parsed)}
        self._backend = "onnxruntime"

    def _predict_onnx(self, bgr_frame: Any) -> YoloPrediction:
        import numpy as np

        tensor, scale, pad_x, pad_y = _letterbox_tensor(bgr_frame, self._input_size)
        started = time.perf_counter()
        output = self._model.run(None, {self._input_name: tensor})[0]
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        rows, end_to_end = _prediction_rows(output, len(self._names))
        detections = []
        for row in rows:
            if end_to_end:
                x1, y1, x2, y2, confidence, class_id_value = row[:6]
                class_id = int(class_id_value)
            else:
                class_scores = row[4:]
                class_id = int(np.argmax(class_scores))
                confidence = float(class_scores[class_id])
                if confidence < self.confidence:
                    continue
                center_x, center_y, width, height = row[:4]
                x1 = center_x - width / 2
                y1 = center_y - height / 2
                x2 = center_x + width / 2
                y2 = center_y + height / 2
            if float(confidence) < self.confidence:
                continue
            box = _restore_box(
                (float(x1), float(y1), float(x2), float(y2)),
                scale,
                pad_x,
                pad_y,
                bgr_frame.shape[1],
                bgr_frame.shape[0],
            )
            detections.append(
                YoloDetection(
                    class_id=class_id,
                    class_name=self._names.get(class_id, str(class_id)),
                    confidence=float(confidence),
                    bbox=box,
                )
            )
        kept = _class_aware_nms(detections, self.iou, self.max_detections)
        return YoloPrediction(tuple(kept), elapsed_ms)


def _letterbox_tensor(
    bgr_frame: Any, target_size: tuple[int, int]
) -> tuple[Any, float, int, int]:
    import cv2
    import numpy as np

    target_width, target_height = target_size
    source_height, source_width = bgr_frame.shape[:2]
    scale = min(target_width / source_width, target_height / source_height)
    resized_width = max(1, int(round(source_width * scale)))
    resized_height = max(1, int(round(source_height * scale)))
    resized = cv2.resize(
        bgr_frame, (resized_width, resized_height), interpolation=cv2.INTER_LINEAR
    )
    pad_x = (target_width - resized_width) // 2
    pad_y = (target_height - resized_height) // 2
    canvas = np.full((target_height, target_width, 3), 114, dtype=np.uint8)
    canvas[pad_y : pad_y + resized_height, pad_x : pad_x + resized_width] = resized
    rgb_chw = canvas[:, :, ::-1].transpose(2, 0, 1)
    tensor = np.ascontiguousarray(rgb_chw, dtype=np.float32)[None] / 255.0
    return tensor, scale, pad_x, pad_y


def _prediction_rows(output: Any, class_count: int) -> tuple[Any, bool]:
    import numpy as np

    prediction = np.asarray(output)
    if prediction.ndim == 3:
        prediction = prediction[0]
    if prediction.ndim != 2:
        raise RuntimeError(f"不支持的YOLO输出形状: {output.shape}")
    if prediction.shape[1] == 6:
        return prediction, True
    if prediction.shape[0] == 6:
        return prediction.T, True
    expected_columns = 4 + class_count if class_count else 0
    if expected_columns and prediction.shape[0] == expected_columns:
        prediction = prediction.T
    elif prediction.shape[0] < prediction.shape[1]:
        prediction = prediction.T
    if prediction.shape[1] < 5:
        raise RuntimeError(f"不支持的YOLO输出形状: {output.shape}")
    return prediction, False


def _restore_box(
    box: tuple[float, float, float, float],
    scale: float,
    pad_x: int,
    pad_y: int,
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = box
    return (
        max(0, min(width - 1, int(round((x1 - pad_x) / scale)))),
        max(0, min(height - 1, int(round((y1 - pad_y) / scale)))),
        max(0, min(width - 1, int(round((x2 - pad_x) / scale)))),
        max(0, min(height - 1, int(round((y2 - pad_y) / scale)))),
    )


def _class_aware_nms(
    detections: list[YoloDetection], iou: float, limit: int
) -> list[YoloDetection]:
    kept = []
    for candidate in sorted(detections, key=lambda item: item.confidence, reverse=True):
        if all(
            candidate.class_id != selected.class_id
            or _box_iou(candidate.bbox, selected.bbox) <= iou
            for selected in kept
        ):
            kept.append(candidate)
            if len(kept) >= limit:
                break
    return kept


def _box_iou(
    first: tuple[int, int, int, int], second: tuple[int, int, int, int]
) -> float:
    intersection_width = max(0, min(first[2], second[2]) - max(first[0], second[0]))
    intersection_height = max(0, min(first[3], second[3]) - max(first[1], second[1]))
    intersection = intersection_width * intersection_height
    first_area = max(0, first[2] - first[0]) * max(0, first[3] - first[1])
    second_area = max(0, second[2] - second[0]) * max(0, second[3] - second[1])
    union = first_area + second_area - intersection
    return intersection / union if union else 0.0
