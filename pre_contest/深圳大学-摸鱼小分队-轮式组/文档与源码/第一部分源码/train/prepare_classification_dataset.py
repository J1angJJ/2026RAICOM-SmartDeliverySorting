from __future__ import annotations

import argparse
import random
import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common.raicom_goods import CLASS_NAMES, yolo_names_yaml


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def collect_images(raw_dir: Path) -> dict[str, list[Path]]:
    by_class: dict[str, list[Path]] = {name: [] for name in CLASS_NAMES}
    for class_name in CLASS_NAMES:
        class_dir = raw_dir / class_name
        if not class_dir.exists():
            continue
        by_class[class_name] = [
            path
            for path in sorted(class_dir.rglob("*"))
            if path.is_file() and path.suffix.lower() in IMAGE_EXTS
        ]
    return by_class


def center_crop_image(source: Path, target: Path, crop_ratio: float) -> None:
    if crop_ratio >= 0.999:
        shutil.copy2(source, target)
        return

    with Image.open(source) as image:
        image = image.convert("RGB")
        width, height = image.size
        crop_ratio = max(0.2, min(1.0, crop_ratio))
        crop_w = int(width * crop_ratio)
        crop_h = int(height * crop_ratio)
        left = (width - crop_w) // 2
        top = (height - crop_h) // 2
        cropped = image.crop((left, top, left + crop_w, top + crop_h))
        cropped.save(target, quality=95)


def prepare_dataset(args: argparse.Namespace) -> None:
    raw_dir = args.raw_dir.resolve()
    output_dir = args.output_dir.resolve()
    by_class = collect_images(raw_dir)
    missing_classes = [name for name, images in by_class.items() if not images]
    if missing_classes:
        raise SystemExit(f"Missing images for classes: {', '.join(missing_classes)}")

    if output_dir.exists() and args.clean:
        shutil.rmtree(output_dir)

    rng = random.Random(args.seed)
    copied = {"train": 0, "val": 0}

    for class_name, images in by_class.items():
        images = list(images)
        rng.shuffle(images)
        val_count = max(1, round(len(images) * args.val_ratio)) if len(images) > 1 else 0
        val_ids = set(id(path) for path in images[:val_count])

        for image_path in images:
            split = "val" if id(image_path) in val_ids else "train"
            target_dir = output_dir / split / class_name
            target_dir.mkdir(parents=True, exist_ok=True)
            target_name = f"{class_name}_{image_path.stem}{image_path.suffix.lower()}"
            center_crop_image(image_path, target_dir / target_name, args.center_crop_ratio)
            copied[split] += 1

    (output_dir / "classes.txt").write_text("\n".join(CLASS_NAMES) + "\n", encoding="utf-8")
    (output_dir / "names.yaml").write_text(yolo_names_yaml(), encoding="utf-8")
    print(f"Classification dataset ready: {output_dir}")
    print(f"train images: {copied['train']}, val images: {copied['val']}")
    print(f"center crop ratio: {args.center_crop_ratio}")
    print("Use this path as Ultralytics classification data root.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare RAICOM goods classification dataset.")
    parser.add_argument("--raw-dir", type=Path, required=True, help="Raw captured data with class subfolders.")
    parser.add_argument("--output-dir", type=Path, default=Path("training_workspace/raicom_goods_cls"))
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--clean", action="store_true")
    parser.add_argument(
        "--center-crop-ratio",
        type=float,
        default=1.0,
        help="Center crop ratio before writing images. Use 0.70-0.85 to reduce background.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    prepare_dataset(parse_args())
