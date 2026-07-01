from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy trained model weight to the VM detect model folder.")
    parser.add_argument(
        "--best",
        type=Path,
        default=Path("training_workspace/train_runs/raicom_goods_yolo11n_cls/weights/best.pt"),
        help="Trained best.pt from Ultralytics output.",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=Path("../detect/models/best-cls.pt"),
        help="Target model path for Ubuntu VM inference.",
    )
    args = parser.parse_args()

    best = args.best.resolve()
    target = args.target.resolve()
    if not best.exists():
        raise SystemExit(f"best.pt not found: {best}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best, target)
    print(f"Copied {best} -> {target}")
    print("The .pt file is ignored by git; transfer it to the VM with the detect folder.")


if __name__ == "__main__":
    main()
