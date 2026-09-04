# 国赛赛题研究与工程初稿

## 资料来源

- `private/2026睿抗国赛规则-物流配送挑战赛-足式4.2.pdf`
- `private/资料/产品概述.md`
- `private/资料/CM镜像说明.md`
- `private/资料/基于Python的开发使用/Python库.md`
- `private/资料/基于串口协议的开发使用.md`
- `private/资料/比赛示例/基础示例*.md`
- `reference/DOG1/`
- `docs/robot_offline_snapshot_2026-09-04/`

## 任务理解

国赛线下任务是单台足式机器狗在固定场地内完成物流配送与分拣。比赛开始后，机器狗从左上角出发区自主出发，前往右侧两个包裹识别区，分别识别 KT 箱上的包裹图片信息和目标字母信息；随后前往左下角抓取区，根据识别结果抓取对应颜色的小球，并运输到下方包裹放置区的对应 A/B/C/D 字母区域。

每轮任务最多涉及两个包裹：

- 每个识别区有一个包裹图片和一个目标字母。
- 衣服、卫生纸、牙刷对应红色小球。
- 苹果、橘子、香蕉对应蓝色小球。
- 需要把识别到的包裹和字母通过语音播报出来。
- 示例流程为：识别到 `A 牙刷` 和 `C 香蕉` 后，抓红球投到 A，再抓蓝球投到 C。

比赛时间约束为 4 分钟测试、8 分钟正赛，最多两轮，取最好成绩。正赛中不暂停，救援最多 2 次且扣分。

## 评分重点

比赛总分由任务得分和技术文档组成：

- 比赛任务占 70%。
- 技术文档占 30%。

任务项满分 100 分：

- 识别包裹图片和字母：20 分，两次识别各 10 分。
- 语音播报：10 分，两次播报各 5 分。
- 抓取小球：30 分，两次抓取各 15 分，抓起后 3 秒不掉落视为成功。
- 运输包裹：20 分，两次运输各 10 分。
- 投递包裹：20 分，两次投递各 10 分。

扣分项：

- 与识别区箱子或场地围挡碰撞，每次扣 2 分；连续失控碰撞本轮结束。
- 每次救援扣 5 分，最多 2 次。
- 运输中小球掉落，每次扣 2 分；掉落后可继续抓取。

技术报告评分重点：

- 技术方案完整、架构合理、切实可行。
- 算法有一定深度或优化，有实测数据支撑。
- 文档图文并茂，关键代码解释清晰。
- 工程代码完整，风格良好，注释清晰。

## 硬件与运行环境

当前机器狗为树莓派 CM5 版本：

- 硬件型号：Raspberry Pi Compute Module 5 Lite Rev 1.0。
- 系统：Debian GNU/Linux 12 bookworm。
- 架构：aarch64。
- CPU：4 核 Cortex-A76，最高 2.4GHz。
- 内存：约 4GiB。
- Python：3.11.2。
- SSH：`pi@192.168.31.70`。
- 根分区已扩容到约 117G。

板端推荐运行环境：

- 优先使用 `/home/pi/RaspberryPi-CM5/xgovenv`。
- 该环境确认具备 `xgolib`、`xgoedu`、`cv2`、`picamera2`、`onnxruntime`、`ultralytics`、`torch`。
- 控制串口优先使用 `/dev/ttyAMA0`。
- 相机服务端口 `8090`，手动控制服务端口 `8765`。

厂商系统结构：

- 上位机为树莓派 CM5 或地平线 RDK-X3，负责 AI、视觉、任务决策。
- 下位机为 ESP32，负责电源管理、舵机驱动、步态算法。
- 上下位机通过 TTL 串口协议通信，默认 115200 8N1。
- Python 方案可以优先调用 `xgolib`，必要时再查串口协议做底层补充。

## 是否需要 ROS

当前国赛任务不强制要求 ROS。结合现有板端环境和参考例程，第一版正式方案建议不使用 ROS，采用纯 Python 工程：

- 路径导航主要依赖固定场地、固定路线、IMU yaw 闭环和视觉微调。
- 识别、抓取、投递可以直接用 `xgolib`、OpenCV、ONNX Runtime、Picamera2。
- ROS 会引入工作空间、依赖、启动和调试复杂度，而当前 CM5 官方镜像已为 Python 方案准备好常用库。

后续只有在确认需要激光雷达建图/导航，或比赛临时要求 ROS 内容时，再单独建立 ROS 子工作区。

## 可复用资产

`reference/DOG1` 可作为功能骨架参考，但不能直接当国赛方案。

可复用部分：

- `lib/Motion.py`：基于 `read_yaw()` 的偏航角 PID，对固定路线转向和直行纠偏有价值。
- `lib/camera.py`：Picamera2 优先、OpenCV 兜底的单帧采集方式可复用。
- `lib/catch_ball.py`：红/蓝球颜色阈值、视觉对准、机械臂抓取流程可复用和重调。
- `lib/place_abcd.py`：A/B/C/D 字母 ONNX 检测、对准字母区域、放球流程可复用。
- `check_environment.py`：可改造成 `xgo26_ws` 的环境自检脚本。

需要重写或大改部分：

- `dog1_main.py` 和 `dog2_main.py` 是双机器狗协作流程，国赛应改成单机两次任务的状态机。
- `lib/detect.py` 当前识别的是仪表 `High/Normal/Low` 加字母，不符合国赛“包裹图片 + 字母”的语义。
- TCP 通信模块在单狗方案中不再是主路径，可暂时不用。
- 路线时间参数需要基于国赛场地图重新标定，不能照搬 DOG1。

已发现的参考例程风险：

- `dog2_main.py` 中只判断了 `if anomalies:`，但后续直接访问 `anomalies[1]`，当只收到一个异常字母时会越界。
- 参考代码中有多处硬编码路径 `/home/pi/Desktop/DOG1`，正式工程应统一配置。
- `debug=True` 时使用 `cv2.imshow()`，远程无显示环境可能失败；正式运行应改为保存调试图或终端日志。

## 第一版系统架构

建议 `xgo26_ws` 采用纯 Python 分层结构：

```text
xgo26_ws/
  task_study.md
  README.md
  configs/
    field.yaml
    runtime.yaml
  scripts/
    run_mission.py
    check_environment.py
  xgo26/
    __init__.py
    config.py
    camera.py
    robot.py
    motion.py
    perception/
      package_detector.py
      letter_detector.py
      ball_detector.py
    manipulation/
      grasp.py
      place.py
    mission/
      types.py
      planner.py
      runner.py
    audio.py
    logging_utils.py
  tools/
    capture_dataset.py
    tune_color_threshold.py
    test_detector_image.py
    test_camera.py
    test_motion.py
    test_grasp.py
    test_place.py
  models/
    README.md
```

核心思想：

- `robot.py` 只封装 `xgolib.XGO("/dev/ttyAMA0")` 和基础安全动作。
- `motion.py` 负责 yaw 闭环、定时移动、路线动作，不直接做识别。
- `perception/` 负责包裹、字母、色球识别。
- `manipulation/` 负责抓球和放球动作。
- `mission/runner.py` 负责编排完整比赛流程。
- `configs/field.yaml` 保存可反复调参的路线时间、目标 yaw、抓取参数、投递区域偏移。

## 比赛流程状态机

第一版正式任务可以按以下状态机实现：

1. `BOOT_CHECK`
   - 检查电量、串口、摄像头、模型文件。
   - 复位姿态，关闭表演模式，爪子打开。

2. `GO_TO_RECOGNITION_1`
   - 按固定路线到第一个识别区。
   - 用 yaw 闭环控制转向，尽量避免碰箱和围挡。

3. `DETECT_PACKAGE_1`
   - 采集多帧图像。
   - 输出 `{letter, package, ball_color, confidence}`。
   - 终端打印并语音播报。

4. `GO_TO_RECOGNITION_2`
   - 移动到第二个识别区。

5. `DETECT_PACKAGE_2`
   - 同上，得到第二个配送任务。

6. `GO_TO_PICK_AREA`
   - 移动到抓取区。

7. `PICK_AND_DELIVER_TASK_1`
   - 根据第一个任务选择红/蓝球。
   - 视觉对准并抓取。
   - 运输到目标字母区域。
   - 视觉对准目标字母或按固定位置投递。

8. `RETURN_TO_PICK_AREA`
   - 回到抓取区。

9. `PICK_AND_DELIVER_TASK_2`
   - 完成第二个任务。

10. `FINISH`
    - 停止、复位到安全姿态、输出结果摘要。

## 感知方案

### 包裹图片与字母识别

国赛识别目标包括 6 类包裹图片和 4 类字母：

- 包裹类：衣服、卫生纸、牙刷、苹果、橘子、香蕉。
- 字母类：A、B、C、D。

建议训练一个联合检测模型，类别可以设计为：

```text
clothes, paper, toothbrush, apple, orange, banana, A, B, C, D
```

识别后需要把同一张 A4 贴图中的包裹和字母配对。参考 DOG1 的思路，可以按 bbox 中心距离或水平/垂直布局匹配；因为每个识别区通常只有一个包裹和一个字母，第一版可以取最高置信度包裹和最高置信度字母。

颜色映射：

```python
RED_PACKAGES = {"clothes", "paper", "toothbrush"}
BLUE_PACKAGES = {"apple", "orange", "banana"}
```

为了拿识别分和播报分，输出必须稳定包含：

- 终端文字输出。
- 语音播报。
- 置信度和原始检测结果日志。

### 色球识别与抓取

抓取区只有红色和蓝色海绵球，优先使用 OpenCV 颜色阈值方案：

- LAB 对光照相对稳，参考 `catch_ball.py` 已有阈值。
- 红色可同时保留 HSV 双区间作为备选。
- 每次抓取前根据目标颜色只寻找对应颜色中最大的圆形区域。

抓取策略：

- 先低速搜索目标颜色球。
- 对准图像中心和目标纵向位置。
- 到达容差后执行固定机械臂抓取序列。
- 抓取后等待 3 秒确认不掉落，满足评分规则。

### 投递区定位

投递区分 A/B/C/D 四块。第一版建议采用固定路线 + 字母视觉微调：

- 固定路线负责接近放置区。
- 使用 `ABCD.onnx` 或新训练字母模型检测目标字母。
- 对准目标字母后执行放置动作。

如果现场字母贴图清晰，视觉微调能减少固定路线误差；如果场地反光或遮挡严重，要保留纯固定位置投递的兜底路径。

## 路线与运动方案

在没有实物场地标定前，不应过早相信时间参数。第一阶段只保留路线动作接口和配置项，拿到场地后再标定。

建议路线分段：

- `start_to_recognition_1`
- `recognition_1_to_recognition_2`
- `recognition_2_to_pick_area`
- `pick_area_to_drop_A`
- `pick_area_to_drop_B`
- `pick_area_to_drop_C`
- `pick_area_to_drop_D`
- `drop_area_to_pick_area`

每段配置包含：

- 目标 yaw。
- 前进/横移速度。
- 运行时间。
- 是否启用 yaw 纠偏。
- 进入该段前后的安全停顿。

技术文档需要实测数据，因此后续应记录每段路线的成功率、平均耗时、碰撞风险、识别置信度和抓取成功率。

## 近期开发优先级

第一阶段：工程骨架和单项自检。

- 建立 `xgo26_ws` Python 包结构。
- 从 DOG1 迁移并整理相机、运动、抓球、放球模块。
- 写 `check_environment.py`，检查 `xgovenv`、模型、串口、摄像头、磁盘、网络。
- 写 `run_mission.py --dry-run`，无实物动作时也能跑完整状态机。

第二阶段：识别模型。

- 明确训练类别和标签格式。
- 采集或生成包裹 A4 贴图样本。
- 训练/导出 ONNX。
- 在 CM5 的 `xgovenv` 中测试 ONNX Runtime 推理速度。

第三阶段：实物调参。

- 标定色球阈值。
- 标定抓取动作序列。
- 标定 A/B/C/D 投递点。
- 标定固定路线和 yaw 纠偏参数。

第四阶段：比赛策略优化。

- 做失败重试：识别多帧投票、抓取二次搜索、投递目标丢失兜底。
- 做日志和截图留档，支撑技术报告。
- 减少碰撞风险，宁可慢一点也先拿稳识别、抓取和投递分。

## 当前判断

最稳的主线是“纯 Python + 固定路线/yaw 闭环 + 视觉微调 + ONNX 检测 + OpenCV 色球抓取”。ROS 暂时不进入主路径。当前优先目标不是马上跑完整比赛，而是把工程拆成可独立测试的模块，先让每个评分项都有单项测试入口。
