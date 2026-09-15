#!/usr/bin/env python3
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from xgo26.camera import CameraServiceClient
from xgo26.config import load_config
from xgo26.yolo import YoloDetector


def main() -> None:
    parser = argparse.ArgumentParser(description="读取共享相机原图并测试 YOLO26 推理")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--model", help="覆盖配置中的模型路径")
    parser.add_argument("--frames", type=int, default=1)
    args = parser.parse_args()

    config = load_config(args.config)
    camera_cfg = config["camera"]
    detection_cfg = config["detection"]
    detector = YoloDetector(
        args.model or config["models"]["package_model"],
        confidence=float(detection_cfg.get("confidence", 0.45)),
        iou=float(detection_cfg.get("iou", 0.45)),
        image_size=int(detection_cfg.get("image_size", 640)),
        device=str(detection_cfg.get("device", "cpu")),
        max_detections=int(detection_cfg.get("max_detections", 20)),
    )
    client = CameraServiceClient(
        str(camera_cfg.get("service_url", "http://127.0.0.1:8090")),
        timeout=float(camera_cfg.get("request_timeout", 2.0)),
    )
    stream = str(detection_cfg.get("camera_stream", "main"))

    for _ in range(max(1, args.frames)):
        frame = client.read(stream)
        prediction = detector.predict(frame)
        info = client.last_frame_info
        print(
            f"frame={info.get('sequence', '?')} {frame.shape[1]}x{frame.shape[0]} "
            f"inference={prediction.inference_ms:.1f}ms objects={len(prediction.detections)}"
        )
        for detection in prediction.detections:
            print(f"  {detection.summary()}")


if __name__ == "__main__":
    main()
