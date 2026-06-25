from __future__ import annotations

import argparse
import sys
import time
from collections import Counter, deque
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None
    ImageDraw = None
    ImageFont = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common.raicom_goods import CLASS_INFO, format_detection
from camera_utils import open_vm_camera, read_frame_with_retry


FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
]


def load_font(size: int = 22):
    if ImageFont is None:
        return None
    for font_path in FONT_CANDIDATES:
        if Path(font_path).exists():
            try:
                return ImageFont.truetype(font_path, size)
            except OSError:
                continue
    return None


def draw_chinese_text(frame, text: str, x: int, y: int, font, color=(80, 255, 120)):
    if Image is None or ImageDraw is None or font is None:
        cv2.putText(
            frame,
            text.encode("ascii", "ignore").decode("ascii"),
            (x, y + 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2,
        )
        return frame
    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(image)
    bbox = draw.textbbox((x, y), text, font=font)
    draw.rectangle((bbox[0] - 6, bbox[1] - 4, bbox[2] + 6, bbox[3] + 4), fill=(0, 0, 0))
    draw.text((x, y), text, font=font, fill=color)
    return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)


def best_class_from_result(result, min_conf: float) -> tuple[str | None, float]:
    if result.probs is None:
        return None, 0.0
    cls_id = int(result.probs.top1)
    conf = float(result.probs.top1conf)
    class_name = result.names[cls_id]
    if conf < min_conf:
        return None, conf
    return class_name, conf


def run_classification(args: argparse.Namespace) -> None:
    model_path = args.model.resolve()
    if not model_path.exists():
        raise SystemExit(f"模型文件不存在: {model_path}")

    print("正在加载 YOLO 分类模型...")
    model = YOLO(str(model_path))
    print(f"模型加载成功: {model_path}")

    cap = open_vm_camera(args.camera, args.width, args.height, args.fps)
    if cap is None:
        return

    ok, _ = read_frame_with_retry(cap)
    if not ok:
        cap.release()
        raise SystemExit("无法读取摄像头画面。请先检查 USB 直通和 v4l2-ctl。")

    font = load_font(args.font_size)
    history: deque[str] = deque(maxlen=args.window_size)
    stable_class: str | None = None
    stable_conf = 0.0
    last_print = 0.0

    print("摄像头读取正常，按 q 退出。")
    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                print("警告：无法读取摄像头画面。")
                break

            result = model.predict(frame, imgsz=args.imgsz, device=args.device, verbose=False)[0]
            current_class, current_conf = best_class_from_result(result, args.conf)
            if current_class in CLASS_INFO:
                history.append(current_class)
                common_class, count = Counter(history).most_common(1)[0]
                if count >= args.confirm_count:
                    stable_class = common_class
                    stable_conf = current_conf

            annotated = frame.copy()
            if stable_class:
                status_text = f"{format_detection(stable_class)} 置信度 {stable_conf:.2f}"
            else:
                status_text = "等待稳定分类结果"

            annotated = draw_chinese_text(annotated, status_text, 10, 10, font)
            if args.overlay:
                h = annotated.shape[0]
                annotated = draw_chinese_text(
                    annotated, args.overlay, 10, max(10, h - 36), font, color=(255, 255, 255)
                )

            now = time.time()
            if now - last_print >= args.print_interval:
                print(status_text)
                last_print = now

            cv2.imshow("RAICOM package classification", annotated)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RAICOM goods classification in Ubuntu VM.")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--model", type=Path, default=Path("models/best-cls.pt"))
    parser.add_argument("--conf", type=float, default=0.45)
    parser.add_argument("--imgsz", type=int, default=224)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--height", type=int, default=240)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--window-size", type=int, default=5)
    parser.add_argument("--confirm-count", type=int, default=3)
    parser.add_argument("--print-interval", type=float, default=0.5)
    parser.add_argument("--overlay", default="深圳大学 摸鱼小分队 轮式组")
    parser.add_argument("--font-size", type=int, default=22)
    return parser.parse_args()


if __name__ == "__main__":
    run_classification(parse_args())
