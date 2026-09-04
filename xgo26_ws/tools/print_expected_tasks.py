#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from xgo26.config import load_config
from xgo26.perception import PackageDetector


def main() -> None:
    config = load_config()
    detector = PackageDetector(config["models"]["package_model"])
    for item in config["mission"].get("expected_tasks", []):
        task = detector.detect_or_expected(item)
        print(task.summary())


if __name__ == "__main__":
    main()
