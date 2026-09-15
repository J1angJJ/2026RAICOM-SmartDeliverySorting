from __future__ import annotations

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

    def available(self) -> bool:
        return self._model is not None or self.model_path.exists()

    def load(self) -> None:
        if self._model is not None:
            return
        if not self.model_path.exists():
            raise FileNotFoundError(f"YOLO模型不存在: {self.model_path}")
        from ultralytics import YOLO

        self._model = YOLO(str(self.model_path), task="detect")

    def predict(self, bgr_frame: Any) -> YoloPrediction:
        self.load()
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
