from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter

import cv2
from ultralytics import YOLO


# Edit these values in PyCharm, then click Run. No command-line arguments needed.
CAMERA_ID = 0
CONFIDENCE = 0.35
IMAGE_SIZE = 640
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30
WINDOW_NAME = "YOLO real-time detection"

PROJECT_ROOT = Path(__file__).resolve().parent
MODEL_PATH = PROJECT_ROOT / "runs" / "detect" / "runs" / "raicom_goods" / "weights" / "best.pt"

ITEM_INFO = {
    "toothbrush": ("牙刷", "日用品"),
    "paper": ("卫生纸", "日用品"),
    "clothes": ("衣服", "日用品"),
    "banana": ("香蕉", "水果"),
    "apple": ("苹果", "水果"),
    "orange": ("橘子", "水果"),
    "tv": ("电视机", "家电"),
    "fridge": ("冰箱", "家电"),
    "air_conditioner": ("空调", "家电"),
}


def open_camera() -> cv2.VideoCapture:
    backend = cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_V4L2
    cap = cv2.VideoCapture(CAMERA_ID, backend)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
    return cap


def draw_boxes(frame, result) -> list[tuple[str, float]]:
    detected_items = []
    if result.boxes is None:
        return detected_items

    for box in result.boxes:
        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
        class_id = int(box.cls[0])
        conf = float(box.conf[0])
        name = result.names[class_id]
        label = f"{name} {conf:.2f}"
        detected_items.append((name, conf))

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 0), 2)
        cv2.putText(
            frame,
            label,
            (x1, max(y1 - 8, 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 220, 0),
            2,
            cv2.LINE_AA,
        )

    return detected_items


def print_best_result(detected_items: list[tuple[str, float]], last_output: str) -> str:
    if not detected_items:
        return last_output

    best_name, _best_conf = max(detected_items, key=lambda item: item[1])
    item_name, package_type = ITEM_INFO.get(best_name, (best_name, "未知类别"))
    output = f"图中包裹是{item_name}，类别为{package_type}。"
    if output != last_output:
        print(output)
    return output


def draw_fps(frame, fps: float) -> None:
    cv2.putText(
        frame,
        f"FPS: {fps:.1f}",
        (12, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )


def main() -> None:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model file not found: {MODEL_PATH}")

    model = YOLO(str(MODEL_PATH))
    cap = open_camera()
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open camera. Check CAMERA_ID={CAMERA_ID}.")

    print("Real-time detection started. Press q or Esc to exit.")
    print(f"Model: {MODEL_PATH}")

    last_time = perf_counter()
    last_output = ""
    while True:
        ok, frame = cap.read()
        if not ok:
            print("Failed to read frame from camera.")
            break

        result = model.predict(frame, imgsz=IMAGE_SIZE, conf=CONFIDENCE, verbose=False)[0]
        detected_items = draw_boxes(frame, result)
        last_output = print_best_result(detected_items, last_output)

        now = perf_counter()
        fps = 1.0 / max(now - last_time, 1e-6)
        last_time = now
        draw_fps(frame, fps)

        cv2.imshow(WINDOW_NAME, frame)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
