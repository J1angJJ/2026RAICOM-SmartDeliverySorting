from __future__ import annotations

import unittest

from xgo26.perception import PackageDetector
from xgo26.yolo import YoloDetection, YoloPrediction


class StubYoloDetector:
    def available(self) -> bool:
        return True

    def predict(self, frame: object) -> YoloPrediction:
        return YoloPrediction(
            detections=(
                YoloDetection(0, "clothes", 0.72, (10, 20, 50, 80)),
                YoloDetection(5, "banana", 0.91, (60, 20, 100, 80)),
                YoloDetection(6, "A", 0.88, (20, 90, 50, 120)),
                YoloDetection(8, "C", 0.95, (60, 90, 90, 120)),
            ),
            inference_ms=25.0,
        )


class PackageDetectorTest(unittest.TestCase):
    def test_selects_highest_confidence_package_and_letter(self) -> None:
        detector = PackageDetector("unused.pt", detector=StubYoloDetector())
        task = detector.detect_frame(object())
        self.assertIsNotNone(task)
        assert task is not None
        self.assertEqual(task.package, "banana")
        self.assertEqual(task.letter, "C")
        self.assertEqual(task.ball_color, "blue")
        self.assertAlmostEqual(task.confidence, 0.91)


if __name__ == "__main__":
    unittest.main()
