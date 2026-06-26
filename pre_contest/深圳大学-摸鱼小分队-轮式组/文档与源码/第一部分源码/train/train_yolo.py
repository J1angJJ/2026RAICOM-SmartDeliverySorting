from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO


def train(args: argparse.Namespace) -> None:
    data_yaml = args.data.resolve()
    if not data_yaml.exists():
        raise SystemExit(f"Dataset yaml not found: {data_yaml}")
    project_dir = args.project.resolve()

    model = YOLO(args.model)
    result = model.train(
        data=str(data_yaml),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=str(project_dir),
        name=args.name,
        workers=args.workers,
        patience=args.patience,
        optimizer=args.optimizer,
        close_mosaic=args.close_mosaic,
        rect=args.rect,
        multi_scale=args.multi_scale,
        exist_ok=args.exist_ok,
    )
    print("Training finished.")
    print(result)
    print(f"Save dir: {result.save_dir}")
    print(f"Expected best weight: {project_dir / args.name / 'weights' / 'best.pt'}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train RAICOM goods YOLO model on Windows.")
    parser.add_argument("--data", type=Path, default=Path("data/raicom_goods/data.yaml"))
    parser.add_argument("--model", default="yolov8n.pt", help="Base YOLO model, e.g. yolo11n.pt or yolo26n.pt.")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", default="0", help="Use 0 for RTX GPU, or cpu.")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--patience", type=int, default=30)
    parser.add_argument("--optimizer", default="auto")
    parser.add_argument("--close-mosaic", type=int, default=10)
    parser.add_argument("--rect", action="store_true", help="Use rectangular batches. Usually leave off for small custom datasets.")
    parser.add_argument("--multi-scale", action="store_true", help="Enable multi-scale training augmentation.")
    parser.add_argument("--project", type=Path, default=Path("outputs/train_runs"))
    parser.add_argument("--name", default="raicom_goods")
    parser.add_argument("--exist-ok", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    train(parse_args())
