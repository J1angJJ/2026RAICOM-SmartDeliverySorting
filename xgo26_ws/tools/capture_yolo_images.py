#!/usr/bin/env python3
from __future__ import annotations

import argparse
from contextlib import nullcontext
from datetime import datetime
import json
from pathlib import Path
import re
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from xgo26.camera import CameraServiceClient
from xgo26.config import load_config, resolve_path
from xgo26.terminal_keys import TerminalKeys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="从共享相机服务采集 YOLO 原始图片")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--session", help="采集批次名，默认使用日期时间")
    parser.add_argument("--output", default="datasets/raw", help="数据集原始图片根目录")
    parser.add_argument("--stream", choices=["main", "lores"], default="main")
    parser.add_argument("--auto", action="store_true", help="启动后立即自动拍摄")
    parser.add_argument("--interval", type=float, default=0.5, help="自动拍摄间隔，单位秒")
    parser.add_argument("--max-images", type=int, default=0, help="达到数量后退出，0 表示不限")
    parser.add_argument("--duration", type=float, default=0, help="达到时长后退出，0 表示不限")
    parser.add_argument("--jpeg-quality", type=int, default=95)
    parser.add_argument(
        "--min-change",
        type=float,
        default=0.0,
        help="自动拍摄与上一张的最小灰度平均变化，0 表示不去重",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.interval <= 0:
        raise SystemExit("--interval 必须大于 0")
    if not 30 <= args.jpeg_quality <= 100:
        raise SystemExit("--jpeg-quality 必须在 30 到 100 之间")

    config = load_config(args.config)
    camera_cfg = config["camera"]
    session = _session_name(args.session)
    session_dir = resolve_path(args.output) / session
    if session_dir.exists():
        raise SystemExit(f"采集批次已经存在: {session_dir}")

    client = CameraServiceClient(
        str(camera_cfg.get("service_url", "http://127.0.0.1:8090")),
        float(camera_cfg.get("request_timeout", 2.0)),
    )
    stream_cfg = camera_cfg.get(args.stream, {})
    width = int(stream_cfg.get("width", camera_cfg.get("width", 1296)))
    height = int(stream_cfg.get("height", camera_cfg.get("height", 972)))
    interactive = sys.stdin.isatty()
    if not interactive and not args.auto:
        raise SystemExit("非交互运行必须指定 --auto")

    print(f"[capture] connecting to {client.base_url}")
    first_frame = client.read(args.stream, width, height)
    images_dir = session_dir / "images"
    images_dir.mkdir(parents=True)
    metadata_path = session_dir / "frames.jsonl"
    _write_session_file(session_dir, args, camera_cfg)

    print(f"[capture] session={session} stream={args.stream} {width}x{height}")
    print(f"[capture] output={session_dir}")
    if interactive:
        print("[capture] 空格=拍照  a=自动开关  q=退出")

    auto_enabled = bool(args.auto)
    capture_requested = False
    saved = 0
    started = time.monotonic()
    last_auto = started - args.interval
    previous_gray: Any | None = None
    terminal = TerminalKeys() if interactive else nullcontext()

    try:
        with terminal as keys, metadata_path.open("a", encoding="utf-8") as metadata_file:
            while True:
                now = time.monotonic()
                if args.duration > 0 and now - started >= args.duration:
                    break
                if args.max_images > 0 and saved >= args.max_images:
                    break

                if first_frame is not None:
                    frame = first_frame
                    first_frame = None
                else:
                    frame = client.read(args.stream, width, height)
                if interactive:
                    key = keys.read()
                    if key == " ":
                        capture_requested = True
                    elif key and key.lower() == "a":
                        auto_enabled = not auto_enabled
                        print(f"\n[capture] auto={'on' if auto_enabled else 'off'}")
                        last_auto = time.monotonic() - args.interval
                    elif key and key.lower() == "q":
                        break

                now = time.monotonic()
                auto_due = auto_enabled and now - last_auto >= args.interval
                if not capture_requested and not auto_due:
                    continue

                quality, gray = _quality_metrics(frame)
                if (
                    auto_due
                    and args.min_change > 0
                    and previous_gray is not None
                    and _mean_change(gray, previous_gray) < args.min_change
                ):
                    last_auto = time.monotonic()
                    capture_requested = False
                    continue

                saved += 1
                timestamp = datetime.now().astimezone()
                filename = (
                    f"{timestamp:%Y%m%d_%H%M%S}_"
                    f"{timestamp.microsecond // 1000:03d}_{saved:05d}.jpg"
                )
                image_path = images_dir / filename
                _save_jpeg(image_path, frame, args.jpeg_quality)
                record = {
                    "file": f"images/{filename}",
                    "captured_at": timestamp.isoformat(timespec="milliseconds"),
                    "width": int(frame.shape[1]),
                    "height": int(frame.shape[0]),
                    **client.last_frame_info,
                    **quality,
                    "source": "manual" if capture_requested else "auto",
                }
                metadata_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                metadata_file.flush()
                previous_gray = gray
                capture_requested = False
                if auto_due:
                    last_auto = time.monotonic()
                warning = _quality_warning(record)
                print(
                    f"\r[capture] saved={saved} exposure={record.get('exposure_time_us')}us "
                    f"gain={_format_number(record.get('analogue_gain'))} "
                    f"brightness={record['brightness']:.1f} blur={record['sharpness']:.1f}{warning}   ",
                    end="",
                    flush=True,
                )
    except KeyboardInterrupt:
        pass
    finally:
        print(f"\n[capture] finished, saved={saved}, output={session_dir}")


def _session_name(value: str | None) -> str:
    name = value or datetime.now().astimezone().strftime("session_%Y%m%d_%H%M%S")
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("._")
    if not cleaned:
        raise SystemExit("--session 不能是空名称")
    return cleaned


def _write_session_file(
    session_dir: Path, args: argparse.Namespace, camera_cfg: dict
) -> None:
    data = {
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "stream": args.stream,
        "interval_seconds": args.interval,
        "camera_service_url": camera_cfg.get("service_url"),
        "camera_controls": camera_cfg.get("controls", {}),
        "note": "保存原始完整画面；标注或训练前另行裁剪，不覆盖本目录。",
    }
    (session_dir / "session.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _quality_metrics(frame: Any) -> tuple[dict[str, float], Any]:
    import cv2
    import numpy as np

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    sample = cv2.resize(gray, (160, 120), interpolation=cv2.INTER_AREA)
    return {
        "brightness": round(float(np.mean(sample)), 2),
        "underexposed_ratio": round(float(np.mean(sample <= 8)), 4),
        "overexposed_ratio": round(float(np.mean(sample >= 247)), 4),
        "sharpness": round(float(cv2.Laplacian(sample, cv2.CV_64F).var()), 2),
    }, sample


def _mean_change(current: Any, previous: Any) -> float:
    import cv2
    import numpy as np

    return float(np.mean(cv2.absdiff(current, previous)))


def _save_jpeg(path: Path, frame: Any, quality: int) -> None:
    import cv2

    if not cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, quality]):
        raise RuntimeError(f"无法保存图片: {path}")


def _quality_warning(record: dict[str, Any]) -> str:
    warnings = []
    if record["underexposed_ratio"] > 0.2:
        warnings.append("欠曝")
    if record["overexposed_ratio"] > 0.1:
        warnings.append("过曝")
    exposure = record.get("exposure_time_us")
    if isinstance(exposure, int) and exposure > 10000:
        warnings.append("运动模糊风险")
    return f" warning={','.join(warnings)}" if warnings else ""


def _format_number(value: Any) -> str:
    return f"{value:.2f}" if isinstance(value, (int, float)) else "?"


if __name__ == "__main__":
    main()
