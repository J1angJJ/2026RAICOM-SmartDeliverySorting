from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config.json"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path) if path else DEFAULT_CONFIG
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    with config_path.open("r", encoding="utf-8") as fp:
        config = json.load(fp)
    config["_config_path"] = str(config_path)
    config["_root"] = str(ROOT)
    return config


def resolve_path(value: str | Path, base: str | Path | None = None) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return Path(base or ROOT) / path

