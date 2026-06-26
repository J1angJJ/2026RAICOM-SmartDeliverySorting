from __future__ import annotations

import argparse
from pathlib import Path

import yaml


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def load_data_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def dataset_path(data_yaml: Path, data: dict) -> Path:
    if "path" in data:
        root = Path(data["path"])
        return root if root.is_absolute() else (data_yaml.parent / root).resolve()
    return data_yaml.parent.resolve()


def check_split(root: Path, split_name: str, split_value: str, class_count: int) -> tuple[int, int, list[str]]:
    image_dir = root / split_value
    label_dir = root / split_value.replace("images", "labels", 1)
    images = sorted(path for path in image_dir.rglob("*") if path.suffix.lower() in IMAGE_EXTS)
    errors: list[str] = []
    labeled = 0

    for image_path in images:
        relative = image_path.relative_to(image_dir)
        label_path = label_dir / relative.with_suffix(".txt")
        if not label_path.exists():
            errors.append(f"{split_name}: missing label for {relative}")
            continue

        lines = [line.strip() for line in label_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            errors.append(f"{split_name}: empty label for {relative}")
            continue

        labeled += 1
        for line_no, line in enumerate(lines, start=1):
            parts = line.split()
            if len(parts) != 5:
                errors.append(f"{split_name}: invalid line {label_path}:{line_no}: {line}")
                continue
            try:
                class_id = int(float(parts[0]))
                values = [float(value) for value in parts[1:]]
            except ValueError:
                errors.append(f"{split_name}: non-numeric line {label_path}:{line_no}: {line}")
                continue
            if class_id < 0 or class_id >= class_count:
                errors.append(f"{split_name}: class id out of range {label_path}:{line_no}: {class_id}")
            if any(value < 0.0 or value > 1.0 for value in values):
                errors.append(f"{split_name}: box value out of range {label_path}:{line_no}: {line}")
            if values[2] <= 0.0 or values[3] <= 0.0:
                errors.append(f"{split_name}: non-positive box size {label_path}:{line_no}: {line}")

    return len(images), labeled, errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Check a YOLO detection dataset before training.")
    parser.add_argument("--data", type=Path, default=Path("training_workspace/raicom_goods_det/data.yaml"))
    args = parser.parse_args()

    data_yaml = args.data.resolve()
    data = load_data_yaml(data_yaml)
    root = dataset_path(data_yaml, data)
    names = data["names"]
    class_count = len(names)
    total_images = 0
    total_labeled = 0
    all_errors: list[str] = []

    for split_name in ("train", "val"):
        image_count, labeled_count, errors = check_split(root, split_name, data[split_name], class_count)
        total_images += image_count
        total_labeled += labeled_count
        all_errors.extend(errors)
        print(f"{split_name}: images={image_count}, labeled={labeled_count}, errors={len(errors)}")

    print(f"total: images={total_images}, labeled={total_labeled}, errors={len(all_errors)}")
    if all_errors:
        for error in all_errors[:50]:
            print(error)
        if len(all_errors) > 50:
            print(f"... {len(all_errors) - 50} more errors")
        raise SystemExit(1)
    print("dataset ok")


if __name__ == "__main__":
    main()
