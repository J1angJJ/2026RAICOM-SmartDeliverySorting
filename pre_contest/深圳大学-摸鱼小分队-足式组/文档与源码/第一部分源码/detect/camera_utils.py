from __future__ import annotations

import time

import cv2


def read_frame_with_retry(cap: cv2.VideoCapture, retry_count: int = 20, delay: float = 0.05):
    for _ in range(retry_count):
        success, frame = cap.read()
        if success and frame is not None:
            return True, frame
        time.sleep(delay)
    return False, None


def open_vm_camera(camera_id: int, width: int = 320, height: int = 240, fps: int = 30) -> cv2.VideoCapture | None:
    print(f"\n正在尝试打开摄像头: /dev/video{camera_id}")
    cap = cv2.VideoCapture(camera_id, cv2.CAP_V4L2)
    if not cap.isOpened():
        print(f"错误：无法打开 /dev/video{camera_id}")
        return None

    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"YUYV"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    cap.set(cv2.CAP_PROP_CONVERT_RGB, 1)

    print("\n摄像头参数:")
    print(f"索引: /dev/video{camera_id}")
    print("编码: YUYV")
    print(f"宽度: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}")
    print(f"高度: {int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
    print(f"FPS: {cap.get(cv2.CAP_PROP_FPS)}")
    return cap
