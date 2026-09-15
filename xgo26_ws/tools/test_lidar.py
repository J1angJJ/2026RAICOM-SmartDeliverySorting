#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from xgo26.config import load_config
from xgo26.lidar import FrontWallEstimator, YDLidarDevice


def main() -> None:
    parser = argparse.ArgumentParser(description="读取 T-mini Plus 并估计前方平面")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--scans", type=int, default=10)
    parser.add_argument("--interval", type=float, default=0.05)
    parser.add_argument("--json", action="store_true", help="逐圈输出 JSON")
    args = parser.parse_args()

    config = load_config(args.config)
    lidar_config = config.get("lidar", {})
    if not lidar_config.get("enabled", False):
        raise SystemExit("雷达尚未启用；确认接线和安装方向后设置 lidar.enabled=true")

    estimator = FrontWallEstimator(lidar_config)
    valid_count = 0
    with YDLidarDevice(lidar_config) as lidar:
        print(f"[lidar-test] connected port={lidar.port}")
        for index in range(1, max(1, args.scans) + 1):
            scan = lidar.read_scan()
            if scan is None:
                print(f"[lidar-test] scan={index} unavailable")
                time.sleep(max(0.0, args.interval))
                continue
            estimate = estimator.estimate(scan)
            valid_count += int(estimate.valid)
            if args.json:
                output = {
                    "scan": index,
                    "raw_points": len(scan.points),
                    "scan_frequency_hz": scan.scan_frequency_hz,
                    **estimate.as_dict(),
                }
                print(json.dumps(output, ensure_ascii=False))
            else:
                print(
                    f"[lidar-test] scan={index} raw_points={len(scan.points)} "
                    f"frequency={scan.scan_frequency_hz:.2f}Hz {estimate.summary()}"
                )
            time.sleep(max(0.0, args.interval))

    if valid_count == 0:
        raise SystemExit("没有得到有效前方平面；请检查端口、安装方向和定位参数")


if __name__ == "__main__":
    main()
