from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO


def train(args: argparse.Namespace) -> None:
    data_dir = args.data.resolve()
    if not (data_dir / "train").exists() or not (data_dir / "val").exists():
        raise SystemExit(f"Classification dataset must contain train/ and val/: {data_dir}")
    project_dir = args.project.resolve()

    model = YOLO(args.model)
    result = model.train(
        data=str(data_dir),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=str(project_dir),
        name=args.name,
        workers=args.workers,
        patience=args.patience,
        exist_ok=args.exist_ok,
    )
    print("Classification training finished.")
    print(result)
    print(f"Save dir: {result.save_dir}")
    print(f"Expected best weight: {project_dir / args.name / 'weights' / 'best.pt'}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train RAICOM goods YOLO classification model on Windows.")
    parser.add_argument("--data", type=Path, default=Path("training_workspace/raicom_goods_cls"))
    parser.add_argument("--model", default="yolo11n-cls.pt", help="Base classification model, e.g. yolo11n-cls.pt.")
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--imgsz", type=int, default=224)
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--device", default="0")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--project", type=Path, default=Path("training_workspace/train_runs"))
    parser.add_argument("--name", default="raicom_goods_yolo11n_cls")
    parser.add_argument("--exist-ok", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    train(parse_args())
