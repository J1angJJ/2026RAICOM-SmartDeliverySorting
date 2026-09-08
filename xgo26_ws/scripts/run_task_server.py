#!/usr/bin/env python3
from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from xgo26.config import load_config
from xgo26.runtime_server import serve


def main() -> None:
    parser = argparse.ArgumentParser(description="Run XGO26 task runtime HTTP server")
    parser.add_argument("--config", default="config.json", help="配置文件路径")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=8767, help="监听端口")
    parser.add_argument("--dry-run", action="store_true", help="只打印动作，不连接硬件")
    args = parser.parse_args()

    config = load_config(args.config)
    serve(config, host=args.host, port=args.port, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
