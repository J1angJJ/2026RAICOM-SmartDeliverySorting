from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common.raicom_goods import CLASS_NAMES
from camera_utils import open_vm_camera, read_frame_with_retry


def capture(args: argparse.Namespace) -> None:
    if args.class_name not in CLASS_NAMES:
        raise SystemExit(f"Unknown class: {args.class_name}. Choose one of: {', '.join(CLASS_NAMES)}")

    output_dir = args.output_dir / args.class_name
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = open_vm_camera(args.camera, args.width, args.height, args.fps)
    if cap is None:
        return

    ok, _ = read_frame_with_retry(cap)
    if not ok:
        cap.release()
        raise SystemExit("无法读取摄像头画面。请先用 v4l2-ctl 检查 USB 相机。")

    print("按 s 保存当前帧，按 q 退出。")
    print(f"保存目录: {output_dir}")
    saved = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                print("警告：读取帧失败")
                break

            display = frame.copy()
            cv2.putText(display, args.class_name, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.imshow("RAICOM capture", display)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("s"):
                filename = f"{args.class_name}_{time.strftime('%Y%m%d_%H%M%S')}_{saved:03d}.jpg"
                cv2.imwrite(str(output_dir / filename), frame)
                saved += 1
                print(f"saved: {output_dir / filename}")
    finally:
        cap.release()
        cv2.destroyAllWindows()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture RAICOM goods images in Ubuntu VM.")
    parser.add_argument("class_name", help=f"One of: {', '.join(CLASS_NAMES)}")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--output-dir", type=Path, default=Path("capture"))
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--height", type=int, default=240)
    parser.add_argument("--fps", type=int, default=30)
    return parser.parse_args()


if __name__ == "__main__":
    capture(parse_args())
