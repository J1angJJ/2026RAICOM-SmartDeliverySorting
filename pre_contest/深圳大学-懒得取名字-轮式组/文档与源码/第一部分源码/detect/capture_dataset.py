from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common.raicom_goods import CLASS_NAMES
from camera_utils import open_vm_camera, read_frame_with_retry


def create_output_dir(base_dir: Path, class_name: str, session: str | None) -> Path:
    session_name = session or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = base_dir / class_name / session_name
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def capture(args: argparse.Namespace) -> None:
    if args.class_name not in CLASS_NAMES:
        raise SystemExit(f"Unknown class: {args.class_name}. Choose one of: {', '.join(CLASS_NAMES)}")

    output_dir = create_output_dir(args.output_dir, args.class_name, args.session)

    cap = open_vm_camera(args.camera, args.width, args.height, args.fps)
    if cap is None:
        return

    ok, _ = read_frame_with_retry(cap)
    if not ok:
        cap.release()
        raise SystemExit("无法读取摄像头画面。请先用 v4l2-ctl 检查 USB 相机。")

    print("摄像头读取正常")
    print(f"保存目录: {output_dir}")
    print("\n操作说明:")
    print("按 空格 开始/暂停自动拍照")
    print("按 s 手动保存当前帧")
    print("按 q 退出程序\n")

    saved = 0
    capturing = args.auto_start
    last_capture_time = 0.0

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                print("警告：读取帧失败")
                break

            now = time.time()
            if capturing and now - last_capture_time >= args.interval:
                saved += 1
                filename = f"{args.class_name}_{saved:05d}.jpg"
                image_path = output_dir / filename
                if cv2.imwrite(str(image_path), frame):
                    print(f"已保存: {image_path}")
                else:
                    print(f"保存失败: {image_path}")
                last_capture_time = now

            display = frame.copy()
            if capturing:
                status = f"CAPTURING | {args.class_name} | Count: {saved} | {args.interval:.2f}s"
            else:
                status = f"PAUSED | {args.class_name} | Count: {saved}"
            cv2.putText(display, status, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)
            cv2.putText(display, "SPACE: start/pause | S: save once | Q: quit", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 255, 0), 1)
            cv2.imshow("RAICOM capture", display)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                print("\n用户主动退出")
                break
            if key == 32:
                capturing = not capturing
                if capturing:
                    print("\n开始自动拍照")
                    last_capture_time = 0.0
                else:
                    print("\n暂停自动拍照")
            if key == ord("s"):
                saved += 1
                filename = f"{args.class_name}_{saved:05d}.jpg"
                image_path = output_dir / filename
                if cv2.imwrite(str(image_path), frame):
                    print(f"手动保存: {image_path}")
                else:
                    print(f"保存失败: {image_path}")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("\n采集结束")
        print(f"共保存图片数量: {saved}")
        print(f"保存目录: {output_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture RAICOM goods images in Ubuntu VM.")
    parser.add_argument("class_name", help=f"One of: {', '.join(CLASS_NAMES)}")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--output-dir", type=Path, default=Path("capture"))
    parser.add_argument("--interval", type=float, default=0.5, help="Automatic capture interval in seconds.")
    parser.add_argument("--session", default=None, help="Optional session folder name. Defaults to timestamp.")
    parser.add_argument("--auto-start", action="store_true", help="Start automatic capture immediately.")
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--height", type=int, default=240)
    parser.add_argument("--fps", type=int, default=30)
    return parser.parse_args()


if __name__ == "__main__":
    capture(parse_args())
