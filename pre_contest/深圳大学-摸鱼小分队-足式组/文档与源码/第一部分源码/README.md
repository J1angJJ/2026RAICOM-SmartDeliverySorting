# 第一部分：包裹识别

本部分采用“虚拟机采集与推理、本机 Windows 训练”的工作流。USB 摄像头在 Ubuntu/ROS 虚拟机中已验证可用，本机 Windows 的 `cv-train` 环境用于 GPU 训练。

当前主线为 **YOLO26 检测模型**。早期分类模型代码仍保留作为备份，但正式演示优先使用检测模型，因为比赛距离下目标较小，且物品不一定在画面中心。

## 目录结构

```text
第一部分源码/
├── common/
│   └── raicom_goods.py              # 9 类物品顺序和中文输出映射
├── detect/                          # Ubuntu 虚拟机使用
│   ├── capture_dataset.py           # USB 摄像头采集图片
│   ├── detect_camera.py             # 检测模型实时推理
│   ├── classify_camera.py           # 分类模型推理，备份
│   ├── camera_utils.py
│   ├── pack_capture.sh              # 打包采集数据
│   ├── environment.yml
│   └── models/
│       └── best.pt                  # 检测权重，手动放入，不进 git
└── train/                           # Windows 本机使用
    ├── annotate_boxes.html          # 本地浏览器检测框标注工具
    ├── prepare_dataset.py           # 整理 YOLO26 检测数据集
    ├── check_detection_dataset.py   # 检查漏标、空标、越界框
    ├── train_yolo.py                # 训练 YOLO26 检测模型
    ├── export_for_vm.py             # 复制权重到 detect/models
    ├── data_template.yaml
    └── environment.yml
```

数据集、采集图片、训练输出和模型权重不进入 git。

## 类别顺序

训练、标注、推理必须保持以下顺序：

```text
0 tv              电视机   家电
1 air_conditioner 空调     家电
2 fridge          冰箱     家电
3 paper           卫生纸   日用品
4 clothes         衣服     日用品
5 toothbrush      牙刷     日用品
6 banana          香蕉     水果
7 orange          橘子     水果
8 apple           苹果     水果
```

## 1. 虚拟机采集图片

```bash
cd ~/2026-raicom-smart-delivery-sorting/pre_contest/深圳大学-摸鱼小分队-足式组/文档与源码/第一部分源码/detect
source /home/noetic/yolo_detect/venv/bin/activate
python capture_dataset.py paper --camera 0 --interval 0.5
```

采集窗口按键：

```text
空格  开始/暂停自动拍照
s     手动保存当前帧
q     退出
```

采集完成后可打包：

```bash
bash pack_capture.sh
```

将压缩包传回 Windows 后，整理到：

```text
第一部分源码/train/raw_capture/
├── tv/
├── air_conditioner/
├── fridge/
├── paper/
├── clothes/
├── toothbrush/
├── banana/
├── orange/
└── apple/
```

## 2. 本机标注检测框

用 Chrome 或 Edge 打开：

```text
train/annotate_boxes.html
```

点击 `打开 raw_capture`，选择：

```text
第一部分源码/train/raw_capture
```

操作方式：

```text
鼠标左键拖拽  画框
S             保存当前框
A / D         上一张 / 下一张
Delete        清空当前图标签
```

标注器只需要画框，不需要选择类别。类别由父目录名自动推断，并写入每张图片旁边的同名 `.txt` 标签。

## 3. 整理 YOLO26 数据集

在 Windows `cmd` 中执行：

```cmd
cd /d "R:\2026RAICOM-SmartDeliverySorting\pre_contest\深圳大学-摸鱼小分队-足式组\文档与源码\第一部分源码\train"

C:\Users\JJ406\.conda\envs\cv-train\python.exe prepare_dataset.py --raw-dir raw_capture --output-dir training_workspace\raicom_goods_yolo26 --clean
```

生成结构与之前 `final-demo` 的 YOLO26 数据集一致：

```text
training_workspace/raicom_goods_yolo26/
├── data.yaml
├── train/
│   ├── images/
│   └── labels/
└── valid/
    ├── images/
    └── labels/
```

训练前检查：

```cmd
C:\Users\JJ406\.conda\envs\cv-train\python.exe check_detection_dataset.py --data training_workspace\raicom_goods_yolo26\data.yaml
```

正确结果应包含：

```text
dataset ok
```

## 4. 训练 YOLO26

```cmd
C:\Users\JJ406\.conda\envs\cv-train\python.exe train_yolo.py --model yolo26n.pt --data "training_workspace\raicom_goods_yolo26\data.yaml" --project "training_workspace\train_runs" --name "raicom_goods_yolo26n_img800" --epochs 150 --imgsz 800 --batch 8 --device 0 --workers 4 --patience 40 --exist-ok
```

训练完成后最佳权重位于：

```text
training_workspace/train_runs/raicom_goods_yolo26n_img800/weights/best.pt
```

如果显存不足，可改为：

```text
--imgsz 640 --batch 16
```

## 5. 导出并同步到虚拟机

```cmd
C:\Users\JJ406\.conda\envs\cv-train\python.exe export_for_vm.py --best "training_workspace\train_runs\raicom_goods_yolo26n_img800\weights\best.pt" --target "..\detect\models\best.pt"
```

传到虚拟机：

```cmd
scp "R:\2026RAICOM-SmartDeliverySorting\pre_contest\深圳大学-摸鱼小分队-足式组\文档与源码\第一部分源码\detect\models\best.pt" noetic@192.168.31.11:"/home/noetic/2026-raicom-smart-delivery-sorting/pre_contest/深圳大学-摸鱼小分队-足式组/文档与源码/第一部分源码/detect/models/best.pt"
```

## 6. 虚拟机实时推理

```bash
cd ~/2026-raicom-smart-delivery-sorting/pre_contest/深圳大学-摸鱼小分队-足式组/文档与源码/第一部分源码/detect
source /home/noetic/yolo_detect/venv/bin/activate
python detect_camera.py --camera 0 --model models/best.pt --conf 0.35 --device cpu --imgsz 800
```

检测框默认显示中文物品名和置信度。需要恢复 Ultralytics 原始英文标签时，追加：

```bash
--box-label-mode original
```

也可使用 `--box-label-mode none` 隐藏框标签。

如果 CPU 推理卡顿，可降低输入尺寸：

```bash
python detect_camera.py --camera 0 --model models/best.pt --conf 0.35 --device cpu --imgsz 640
```

## 7. 录屏要点

- 摄像头距离按规则保持在要求范围。
- 画面中展示 USB 摄像头、识别窗口、终端输出。
- 至少覆盖规则要求的物品类别和次数。
- 视频左下角显示：`深圳大学 摸鱼小分队 足式组`。
- 单个视频不超过 5 分钟，不加速。

## 8. 提交前检查

- `detect/models/best.pt` 已放入虚拟机推理目录。
- `detect_camera.py` 能打开 USB 摄像头。
- 画面中有检测框、类别和置信度。
- 终端输出能对应物品类别。
- `common/raicom_goods.py`、`data.yaml` 和模型类别顺序一致。
