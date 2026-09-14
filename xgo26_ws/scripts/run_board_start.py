#!/usr/bin/env python3
from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from xgo26.board_start import default_workspace, run_board_start


def main() -> None:
    parser = argparse.ArgumentParser(description="Confirm an XGO26 mission with a second B-button press")
    parser.add_argument("--workspace", type=Path, default=default_workspace(), help="xgo26_ws 路径")
    parser.add_argument("--confirm-window", type=float, help="覆盖配置中的第二次 B 键等待秒数")
    parser.add_argument("--countdown", type=int, help="覆盖配置中的确认后倒计时秒数")
    args = parser.parse_args()
    raise SystemExit(run_board_start(args.workspace.resolve(), args.confirm_window, args.countdown))


if __name__ == "__main__":
    main()
