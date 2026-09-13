#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from xgo26.camera_service import serve_camera
from xgo26.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the shared XGO26 camera service")
    parser.add_argument("--config", default="config.json", help="配置文件路径")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, help="覆盖配置中的监听端口")
    args = parser.parse_args()

    config = load_config(args.config)["camera"]
    port = int(args.port if args.port is not None else config.get("port", 8090))
    serve_camera(config, host=args.host, port=port)


if __name__ == "__main__":
    main()
