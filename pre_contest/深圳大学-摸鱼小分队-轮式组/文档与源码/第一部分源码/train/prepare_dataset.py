from __future__ import annotations

import argparse
import random
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common.raicom_goods import CLASS_NAMES, CLASS_NAME_TO_ID, yolo_names_yaml


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def find_label(image_path: Path, raw_dir: Path, class_name: str) -> Path | None:
    candidates = [
        image_path.with_suffix(".txt"),
        raw_dir / "labels" / class_name / f"{image_path.stem}.txt",
        raw_dir / "labels" / f"{image_path.stem}.txt",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def collect_images(raw_dir: Path) -> list[tuple[str, Path, Path | None]]:
    samples: list[tuple[str, Path, Path | None]] = []
    for class_name in CLASS_NAMES:
        class_dir = raw_dir / class_name
        if not class_dir.exists():
            continue
        for image_path in sorted(class_dir.rglob("*")):
            if image_path.suffix.lower() not in IMAGE_EXTS:
                continue
            samples.append((class_name, image_path, find_label(image_path, raw_dir, class_name)))
    return samples


def rewrite_label(source: Path, target: Path, class_name: str) -> None:
    expected_id = CLASS_NAME_TO_ID[class_name]
    rewritten = []
    for raw_line in source.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid YOLO label line in {source}: {raw_line!r}")
        parts[0] = str(expected_id)
        rewritten.append(" ".join(parts))
    target.write_text("\n".join(rewritten) + ("\n" if rewritten else ""), encoding="utf-8")


def write_full_box_label(target: Path, class_name: str) -> None:
    expected_id = CLASS_NAME_TO_ID[class_name]
    target.write_text(f"{expected_id} 0.5 0.5 1.0 1.0\n", encoding="utf-8")


def write_dataset_yaml(dataset_dir: Path) -> None:
    data = {
        "path": str(dataset_dir.resolve()).replace("\\", "/"),
        "train": "images/train",
        "val": "images/val",
        "nc": len(CLASS_NAMES),
        "names": CLASS_NAMES,
    }
    (dataset_dir / "data.yaml").write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (dataset_dir / "classes.txt").write_text("\n".join(CLASS_NAMES) + "\n", encoding="utf-8")
    (dataset_dir / "names.yaml").write_text(yolo_names_yaml(), encoding="utf-8")


def prepare_dataset(args: argparse.Namespace) -> None:
    raw_dir = args.raw_dir.resolve()
    output_dir = args.output_dir.resolve()
    samples = collect_images(raw_dir)
    if not samples:
        raise SystemExit(f"No images found under class folders in {raw_dir}")

    missing = [(class_name, image_path) for class_name, image_path, label in samples if label is None]
    if missing and not args.allow_empty_labels and not args.auto_full_box_labels:
        preview = "\n".join(f"- {class_name}: {image_path}" for class_name, image_path in missing[:10])
        raise SystemExit(
            "Missing YOLO txt labels. Label images first, or pass --allow-empty-labels for negative samples.\n"
            + preview
        )

    if output_dir.exists() and args.clean:
        shutil.rmtree(output_dir)

    for split in ("train", "val"):
        (output_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)
    by_class: dict[str, list[tuple[str, Path, Path | None]]] = {name: [] for name in CLASS_NAMES}
    for sample in samples:
        by_class[sample[0]].append(sample)

    copied = {"train": 0, "val": 0}
    for class_name, class_samples in by_class.items():
        rng.shuffle(class_samples)
        val_count = max(1, round(len(class_samples) * args.val_ratio)) if len(class_samples) > 1 else 0
        val_items = set(id(sample) for sample in class_samples[:val_count])
        for sample in class_samples:
            _, image_path, label_path = sample
            split = "val" if id(sample) in val_items else "train"
            stem = f"{class_name}_{image_path.stem}"
            target_image = output_dir / "images" / split / f"{stem}{image_path.suffix.lower()}"
            target_label = output_dir / "labels" / split / f"{stem}.txt"
            shutil.copy2(image_path, target_image)
            if label_path is None:
                if args.auto_full_box_labels:
                    write_full_box_label(target_label, class_name)
                else:
                    target_label.write_text("", encoding="utf-8")
            else:
                rewrite_label(label_path, target_label, class_name)
            copied[split] += 1

    write_dataset_yaml(output_dir)
    print(f"Dataset ready: {output_dir}")
    print(f"train images: {copied['train']}, val images: {copied['val']}")
    print(f"data yaml: {output_dir / 'data.yaml'}")
    if missing and args.auto_full_box_labels:
        print(f"auto full-box labels: {len(missing)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare RAICOM goods YOLO dataset on Windows.")
    parser.add_argument("--raw-dir", type=Path, required=True, help="Raw captured data with class subfolders.")
    parser.add_argument("--output-dir", type=Path, default=Path("data/raicom_goods"), help="YOLO dataset output.")
    parser.add_argument("--val-ratio", type=float, default=0.2, help="Validation split ratio per class.")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--clean", action="store_true", help="Remove output directory before writing.")
    parser.add_argument("--allow-empty-labels", action="store_true", help="Allow images without txt labels.")
    parser.add_argument(
        "--auto-full-box-labels",
        action="store_true",
        help="Generate full-image YOLO boxes for missing labels. Use only when each image contains one centered object.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    prepare_dataset(parse_args())
