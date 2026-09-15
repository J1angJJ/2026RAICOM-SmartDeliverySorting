from __future__ import annotations

import argparse
import importlib.util
import platform
from pathlib import Path
import sys

from .config import ROOT, load_config, resolve_path
from .field_map import load_field_map


def main() -> None:
    parser = argparse.ArgumentParser(description="Check xgo26 runtime environment")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--strict", action="store_true", help="模型缺失也视为失败")
    args = parser.parse_args()

    config = load_config(args.config)
    failures = 0

    def record(ok: bool, name: str, detail: str = "", warn_only: bool = False) -> None:
        nonlocal failures
        mark = "OK" if ok else ("WARN" if warn_only else "FAIL")
        print(f"[{mark}] {name}" + (f": {detail}" if detail else ""))
        if not ok and not warn_only:
            failures += 1

    print("xgo26 环境自检")
    print(f"root={ROOT}")
    print(f"python={platform.python_version()} {platform.platform()}")

    for rel in [
        "config.json",
        "maps/field_map.json",
        "scripts/run_mission.py",
        "xgo26/mission.py",
    ]:
        path = ROOT / rel
        record(path.exists(), rel, str(path))

    map_path = config.get("field_map", {}).get("path", "maps/field_map.json")
    try:
        field_map = load_field_map(map_path)
        record(
            field_map.width == 3.0 and field_map.height == 2.5,
            "field map",
            f"{field_map.width:.1f}m x {field_map.height:.1f}m",
        )
    except (OSError, KeyError, TypeError, ValueError) as error:
        record(False, "field map", str(error))

    for module in [
        "cv2",
        "numpy",
        "onnxruntime",
        "ultralytics",
        "torch",
        "xgolib",
        "xgoedu",
        "picamera2",
    ]:
        spec = importlib.util.find_spec(module)
        record(
            spec is not None,
            f"import {module}",
            "missing" if spec is None else "found",
            warn_only=not args.strict,
        )

    for key, value in config["models"].items():
        path = resolve_path(value)
        exists = path.exists()
        record(
            exists,
            f"model {key}",
            str(path) if exists else f"missing: {path}",
            warn_only=not args.strict,
        )

    serial = Path(config["robot"].get("serial_port", "/dev/ttyAMA0"))
    if platform.system().lower() == "linux":
        record(serial.exists(), "serial", str(serial), warn_only=not args.strict)
    else:
        record(True, "serial", "非 Linux 环境跳过")

    lidar = config.get("lidar", {})
    if lidar.get("enabled", False):
        sdk_path = str(lidar.get("sdk_python_path", "")).strip()
        if sdk_path and sdk_path not in sys.path:
            sys.path.insert(0, sdk_path)
        record(
            importlib.util.find_spec("ydlidar") is not None,
            "import ydlidar",
            sdk_path or "使用当前 Python 环境",
        )
        configured_value = str(lidar.get("port", "")).strip()
        configured_port = Path(configured_value) if configured_value else None
        fallback_port = Path(str(lidar.get("fallback_port", "/dev/ttyUSB0")))
        lidar_port = (
            configured_port
            if configured_port is not None and configured_port.exists()
            else fallback_port
        )
        record(lidar_port.exists(), "lidar serial", str(lidar_port))

    if failures:
        raise SystemExit(1)
    print("自检完成")
