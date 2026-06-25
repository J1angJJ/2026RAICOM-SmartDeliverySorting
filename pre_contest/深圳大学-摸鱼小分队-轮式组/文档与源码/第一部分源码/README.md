# 第一部分：包裹识别

本部分采用“虚拟机采集与推理、本机 Windows 训练”的工作流。原因是 USB 摄像头在虚拟机中已经验证可用，但显卡直通训练不稳定；本机 Windows 的 `cv-train` 环境可以使用 RTX 4060 Laptop GPU 训练。

## 目录结构

```text
第一部分源码/
├── common/
│   └── raicom_goods.py          # 9 类物品顺序和中文输出映射
├── detect/                      # Ubuntu 虚拟机使用
│   ├── capture_dataset.py       # USB 相机采集图片
│   ├── detect_camera.py         # 摄像头实时推理
│   ├── camera_utils.py
│   ├── environment.yml
│   └── models/
│       └── best.pt              # 训练后手动放入，不进 git
└── train/                       # Windows 本机使用
    ├── prepare_dataset.py       # 整理 YOLO 数据集
    ├── train_yolo.py            # 训练 YOLO
    ├── export_for_vm.py         # 复制 best.pt 到 detect/models
    ├── data_template.yaml
    └── environment.yml
```

数据集、采集图片、训练输出和模型权重不进入 git。

## 类别定义

类别顺序固定如下，采集、标注、训练和推理都必须保持一致：

```text
0 tv              电视机    家电
1 air_conditioner 空调      家电
2 fridge          冰箱      家电
3 paper           卫生纸    日用品
4 clothes         衣服      日用品
5 toothbrush      牙刷      日用品
6 banana          香蕉      水果
7 orange          橘子      水果
8 apple           苹果      水果
```

终端输出格式：

```text
图中包裹是卫生纸，类别为日用品。
```

## 1. 虚拟机采集图片

虚拟机沿用四足赛预选赛中已经验证过的 YOLO/USB 相机环境。摄像头按 V4L2 打开，使用 YUYV、320x240、30FPS。

```bash
cd ~/2026-raicom-smart-delivery-sorting/pre_contest/深圳大学-摸鱼小分队-轮式组/文档与源码/第一部分源码/detect
source /home/noetic/yolo_detect/venv/bin/activate
python capture_dataset.py paper --camera 0 --interval 0.5
```

采集窗口中：

```text
空格 开始/暂停自动拍照
s 手动保存当前帧
q 退出
```

每类建议采集多张，目录示例：

```text
detect/capture/
├── paper/
│   └── 20260624_153000/
├── banana/
└── tv/
```

采集完成后，将 `detect/capture/` 传到 Windows 本机。可以直接复制到：

```text
第一部分源码/train/raw_capture/
```

也可以先在虚拟机中打包：

```bash
cd ~/2026-raicom-smart-delivery-sorting/pre_contest/深圳大学-摸鱼小分队-轮式组/文档与源码/第一部分源码/detect
bash pack_capture.sh
```

默认生成：

```text
detect/packages/raicom_capture_时间戳.tar.gz
```

将该压缩包传到 Windows 后解压，再把其中的 `capture/` 内容整理到 `train/raw_capture/`。

## 2. 本机标注与整理数据集

在 Windows 本机使用任意 YOLO 标注工具生成 `.txt` 标签。推荐保持以下结构：

```text
train/raw_capture/
├── paper/
│   ├── paper_001.jpg
│   └── paper_001.txt
├── banana/
└── tv/
```

标签格式为 YOLO detection 格式：

```text
class_id x_center y_center width height
```

`prepare_dataset.py` 会按文件夹名重写 `class_id`，避免手工标错类别编号。

```powershell
cd R:\2026RAICOM-SmartDeliverySorting\pre_contest\深圳大学-摸鱼小分队-轮式组\文档与源码\第一部分源码\train
C:\Users\JJ406\.conda\envs\cv-train\python.exe prepare_dataset.py --raw-dir raw_capture --output-dir data\raicom_goods --clean
```

生成：

```text
train/data/raicom_goods/
├── data.yaml
├── classes.txt
├── images/train
├── images/val
├── labels/train
└── labels/val
```

## 3. 本机训练

本机训练环境参考 `R:\ai-context` 中的 `cv-train`：Python 3.11、PyTorch CUDA、Ultralytics YOLO。

```powershell
cd R:\2026RAICOM-SmartDeliverySorting\pre_contest\深圳大学-摸鱼小分队-轮式组\文档与源码\第一部分源码\train
C:\Users\JJ406\.conda\envs\cv-train\python.exe train_yolo.py --data data\raicom_goods\data.yaml --model yolov8n.pt --epochs 100 --imgsz 640 --batch 8 --device 0
```

训练完成后权重位于：

```text
train/outputs/train_runs/raicom_goods/weights/best.pt
```

复制到虚拟机推理目录：

```powershell
C:\Users\JJ406\.conda\envs\cv-train\python.exe export_for_vm.py --best outputs\train_runs\raicom_goods\weights\best.pt
```

然后将 `detect/models/best.pt` 同步到虚拟机对应目录。

## 4. 虚拟机实时推理

```bash
cd ~/2026-raicom-smart-delivery-sorting/pre_contest/深圳大学-摸鱼小分队-轮式组/文档与源码/第一部分源码/detect
source /home/noetic/yolo_detect/venv/bin/activate
python detect_camera.py --camera 0 --model models/best.pt --conf 0.45 --device cpu
```

如果摄像头编号不是 `/dev/video0`，先查看：

```bash
ls /dev/video*
v4l2-ctl --list-devices
```

必要时先做底层相机测试：

```bash
v4l2-ctl -d /dev/video0 --set-fmt-video=width=320,height=240,pixelformat=YUYV --stream-mmap --stream-count=30
```

## 5. 录屏要点

- 相机距离按更严格口径保持 20cm 以上。
- 视频中展示 USB 相机、识别距离、识别窗口、终端中文输出。
- 至少识别 3 个包裹类别，每类 2 张，共 6 次识别。
- 画面左下角显示：`深圳大学 摸鱼小分队 轮式组`。
- 单个视频不超过 5 分钟，不加速。

## 6. 提交检查

- `detect/models/best.pt` 已放入虚拟机推理目录。
- `detect_camera.py` 能打开 USB 摄像头。
- 图像中有检测框和类别标记。
- 终端输出中文结果。
- `common/raicom_goods.py` 中类别顺序与训练数据 `data.yaml` 一致。
