# 第一部分：包裹识别 YOLO 复现步骤

本文档用于在 Ubuntu 环境中复现“包裹识别”任务。项目基于 YOLO 实现摄像头实时识别，在图像窗口中绘制检测框，并在终端输出中文包裹类别。

## 1. 任务目标

识别 3 种不同包裹类别，每种类别展示 2 张图片，共 6 次识别。

要求：

- 图像中有正确识别框和类别标记。
- 终端输出中文识别结果。
- 视频左下角显示：学校名称 + 队伍名称 + 轮式组。
- 录屏不超过 5 分钟，不加速。
- 相机距离图片建议至少 20cm。

终端输出示例：

```text
图中包裹是卫生纸，类别为日用品。
```

## 2. 包裹类别

| 包裹类别 | 物品 |
| --- | --- |
| 日用品 | 牙刷、卫生纸、衣服 |
| 水果 | 香蕉、苹果、橘子 |
| 家电 | 电视机、冰箱、空调 |

模型英文类别与中文输出映射如下：

```python
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
```

## 3. 项目目录

```bash
mkdir -p ~/raicom_submit/学校名称_队伍名称_轮式组/文档与源码/第一部分源码/源码/part1_yolo
cd ~/raicom_submit/学校名称_队伍名称_轮式组/文档与源码/第一部分源码/源码/part1_yolo

mkdir -p capture/{toothbrush,paper,clothes,banana,apple,orange,tv,fridge,air_conditioner}
mkdir -p datasets/raicom_goods/images/{train,val}
mkdir -p datasets/raicom_goods/labels/{train,val}
mkdir -p runs/detect/runs/raicom_goods/weights
```

最终目录结构：

```text
part1_yolo/
├── detect_camera.py
├── yolov8n.pt
├── capture/
├── datasets/
│   └── raicom_goods/
│       ├── images/train/
│       ├── images/val/
│       ├── labels/train/
│       ├── labels/val/
│       ├── classes.txt
│       └── data.yaml
└── runs/detect/runs/raicom_goods/weights/
    └── best.pt
```

## 4. 安装环境

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv python3-opencv fonts-noto-cjk v4l-utils
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip setuptools wheel
pip install ultralytics opencv-python pillow numpy pyyaml
```

检查环境：

```bash
python3 -c "import cv2; from ultralytics import YOLO; from PIL import Image; print('YOLO环境正常')"
```

检查摄像头：

```bash
ls /dev/video*
v4l2-ctl --list-devices
```

若摄像头为 `/dev/video0`，程序中设置 `CAMERA_ID = 0`；若为 `/dev/video1`，设置 `CAMERA_ID = 1`。

## 5. 数据集配置

创建 `datasets/raicom_goods/classes.txt`：

```text
tv
air_conditioner
fridge
paper
clothes
toothbrush
banana
orange
apple
```

创建 `datasets/raicom_goods/data.yaml`：

```yaml
path: datasets/raicom_goods
train: images/train
val: images/val

names:
  0: tv
  1: air_conditioner
  2: fridge
  3: paper
  4: clothes
  5: toothbrush
  6: banana
  7: orange
  8: apple
```

训练图片放入 `images/train`、`images/val`，YOLO 标签放入 `labels/train`、`labels/val`。

YOLO 标签格式：

```text
class_id x_center y_center width height
```




### 6. 识别程序设计

识别程序文件为：

```text
detect_camera.py
```

本程序基于 `Ultralytics YOLO + OpenCV` 实现摄像头实时识别。程序运行后加载训练好的 `best.pt` 模型，打开摄像头，对每一帧画面进行 YOLO 检测，在识别窗口中绘制检测框，并在终端输出中文包裹类别。

### 6.1 程序整体流程

```text
1. 设置摄像头编号、置信度阈值、图像尺寸和模型路径。
2. 检查 YOLO 模型权重 best.pt 是否存在。
3. 加载 YOLO 模型。
4. 根据系统平台选择摄像头后端。
   - Windows 使用 cv2.CAP_DSHOW。
   - Ubuntu/Linux 使用 cv2.CAP_V4L2。
5. 打开摄像头并设置分辨率、帧率和 MJPG 编码。
6. 循环读取摄像头画面。
7. 对每一帧图像执行 YOLO 推理。
8. 获取检测框坐标、类别名称和置信度。
9. 在图像中绘制绿色检测框和英文类别标签。
10. 选择置信度最高的检测结果。
11. 将英文类别映射为中文物品名和包裹类别。
12. 在终端输出中文识别结果。
13. 在窗口左上角显示实时 FPS。
14. 按 q 或 Esc 退出程序。
15. 释放摄像头并关闭窗口。
```

### 6.2 主要参数设计

程序顶部定义运行参数：

```python
CAMERA_ID = 0
CONFIDENCE = 0.35
IMAGE_SIZE = 640
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30
WINDOW_NAME = "YOLO real-time detection"
```

参数含义：

```text
CAMERA_ID：摄像头编号，通常 /dev/video0 对应 0。
CONFIDENCE：YOLO 检测置信度阈值。
IMAGE_SIZE：YOLO 推理输入尺寸。
CAMERA_WIDTH：摄像头画面宽度。
CAMERA_HEIGHT：摄像头画面高度。
CAMERA_FPS：摄像头帧率。
WINDOW_NAME：OpenCV 显示窗口名称。
```

### 6.3 模型路径设计

程序使用相对项目目录的固定路径加载模型：

```python
PROJECT_ROOT = Path(__file__).resolve().parent
MODEL_PATH = PROJECT_ROOT / "runs" / "detect" / "runs" / "raicom_goods" / "weights" / "best.pt"
```

因此训练好的模型必须放在：

```text
part1_yolo/runs/detect/runs/raicom_goods/weights/best.pt
```

如果该文件不存在，程序会直接报错：

```text
Model file not found
```

### 6.4 类别映射设计

YOLO 模型输出英文类别名，比赛要求终端输出中文，因此程序使用 `ITEM_INFO` 字典完成映射：

```python
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
```

映射逻辑：

```text
英文类别名 -> 中文物品名 -> 中文包裹类别
```

示例：

```text
paper -> 卫生纸 -> 日用品
banana -> 香蕉 -> 水果
tv -> 电视机 -> 家电
```

### 6.5 摄像头打开设计

程序通过 `open_camera()` 函数打开摄像头：

```python
def open_camera() -> cv2.VideoCapture:
    backend = cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_V4L2
    cap = cv2.VideoCapture(CAMERA_ID, backend)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
    return cap
```

设计说明：

```text
1. Windows 调试时使用 cv2.CAP_DSHOW。
2. Ubuntu 比赛环境使用 cv2.CAP_V4L2。
3. 设置 MJPG 编码，提高 USB 摄像头兼容性。
4. 设置画面大小为 640x480。
5. 设置目标帧率为 30 FPS。
```

### 6.6 检测框绘制设计

程序通过 `draw_boxes(frame, result)` 处理 YOLO 检测结果：

```python
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
```

该函数完成：

```text
1. 判断当前帧是否检测到目标。
2. 读取检测框坐标。
3. 读取类别编号和置信度。
4. 根据类别编号得到英文类别名。
5. 在画面中绘制绿色检测框。
6. 在检测框上方显示英文类别名和置信度。
7. 返回当前帧检测到的所有目标。
```

注意：当前程序窗口中显示的是英文类别，例如：

```text
paper 0.86
banana 0.91
tv 0.88
```

比赛要求“终端中文输出”，因此窗口标签使用英文是可以接受的；终端必须输出中文。

### 6.7 终端中文输出设计

程序通过 `print_best_result()` 输出中文结果：

```python
def print_best_result(detected_items: list[tuple[str, float]], last_output: str) -> str:
    if not detected_items:
        return last_output

    best_name, _best_conf = max(detected_items, key=lambda item: item[1])
    item_name, package_type = ITEM_INFO.get(best_name, (best_name, "未知类别"))
    output = f"图中包裹是{item_name}，类别为{package_type}。"
    if output != last_output:
        print(output)
    return output
```

设计说明：

```text
1. 如果当前帧没有识别结果，则不输出。
2. 如果当前帧识别到多个目标，选择置信度最高的目标。
3. 根据英文类别名查询中文物品名和包裹类别。
4. 按比赛要求输出中文结果。
5. 为避免终端刷屏，只有当识别结果变化时才打印。
```

输出示例：

```text
图中包裹是卫生纸，类别为日用品。
图中包裹是香蕉，类别为水果。
图中包裹是电视机，类别为家电。
```

录屏时需要注意：由于程序只在识别结果变化时打印，如果连续展示两张同一物品图片，终端可能不会重复打印。建议录屏时更换不同物品，或在展示下一张图片前短暂移开图片，让识别结果发生变化。

### 6.8 FPS 显示设计

程序通过 `draw_fps()` 在窗口左上角显示实时帧率：

```python
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
```

FPS 用于观察程序运行是否流畅，不参与评分，但可以辅助说明程序为实时识别。

### 6.9 主函数设计

主函数 `main()` 是程序入口：

```text
1. 检查 best.pt 是否存在。
2. 加载 YOLO 模型。
3. 打开摄像头。
4. 打印启动信息和模型路径。
5. 循环读取图像帧。
6. 执行 YOLO 推理。
7. 绘制检测框。
8. 输出中文识别结果。
9. 计算并显示 FPS。
10. 显示实时窗口。
11. 按 q 或 Esc 退出。
12. 释放摄像头资源。
```

启动后终端会显示：

```text
Real-time detection started. Press q or Esc to exit.
Model: /home/用户名/.../part1_yolo/runs/detect/runs/raicom_goods/weights/best.pt
```

### 6.10 程序运行效果

运行成功后应看到：

```text
1. OpenCV 弹出实时检测窗口。
2. 摄像头画面正常显示。
3. 被识别物品周围出现绿色检测框。
4. 检测框上方显示英文类别名和置信度。
5. 窗口左上角显示 FPS。
6. 终端输出中文识别结果。
```
```

建议你把原 README 里的第 6 节替换成上面这一版。它完全贴合你提供的 `detect_camera.py`，不会再写 PIL 中文绘制那种你代码里没有实现的内容。

## 7. 训练模型

进入项目目录：

```bash
cd ~/raicom_submit/学校名称_队伍名称_轮式组/文档与源码/第一部分源码/源码/part1_yolo
source .venv/bin/activate
```

CPU 训练：

```bash
yolo detect train model=yolov8n.pt data=datasets/raicom_goods/data.yaml epochs=100 imgsz=640 batch=4 device=cpu project=runs name=raicom_goods
```

GPU 训练：

```bash
yolo detect train model=yolov8n.pt data=datasets/raicom_goods/data.yaml epochs=100 imgsz=640 batch=8 device=0 project=runs name=raicom_goods
```

检查权重：

```bash
ls runs/detect/runs/raicom_goods/weights/best.pt
```

若已有训练好的 `best.pt`，直接放入：

```text
runs/detect/runs/raicom_goods/weights/best.pt
```

## 8. 运行识别

```bash
cd ~/raicom_submit/学校名称_队伍名称_轮式组/文档与源码/第一部分源码/源码/part1_yolo
source .venv/bin/activate
python3 detect_camera.py
```

正常输出示例：

```text
YOLO package detection started
图中包裹是卫生纸，类别为日用品。
图中包裹是香蕉，类别为水果。
图中包裹是空调，类别为家电。
```

## 9. 录屏要求

视频需要展示：

```text
1. 摄像头画面。
2. 识别窗口。
3. 终端中文输出。
4. 识别距离。
5. 左下角显示：学校名称 + 队伍名称 + 轮式组。
```

识别过程：

```text
1. 日用品、水果、家电中各选择至少 1 类。
2. 共展示 3 种类别。
3. 每种类别展示 2 张图片。
4. 共完成 6 次识别。
```

视频命名：

```text
01_包裹识别.mp4
```

视频放入：

```text
学校名称_队伍名称_轮式组/第一部分/任务一/视频/
```

## 10. 提交结构

```text
学校名称_队伍名称_轮式组/
├── 第一部分/
│   └── 任务一/
│       └── 视频/
│           └── 01_包裹识别.mp4
└── 文档与源码/
    └── 第一部分源码/
        ├── README.md
        └── 源码/
            └── part1_yolo/
                ├── detect_camera.py
                ├── datasets/
                └── runs/detect/runs/raicom_goods/weights/best.pt
```

## 11. 提交前检查

- `detect_camera.py` 可以正常运行。
- 摄像头可以正常打开。
- `best.pt` 路径正确。
- 数据集 `data.yaml` 类别顺序与标签一致。
- 能识别至少 3 个包裹类别。
- 每个类别完成 2 次识别。
- 图像中检测框位置正确。
- 终端中文输出正确。
- 视频左下角包含学校名称、队伍名称和轮式组。
- 录屏不超过 5 分钟。
- 录屏没有加速。
```

这版相比原版，主要补上了 `detect_camera.py` 的设计：参数、模型路径、摄像头、YOLO 推理、检测结果处理、中文输出和退出流程。
