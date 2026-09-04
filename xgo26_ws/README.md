# xgo26_ws

2026 睿抗国赛智能配送与分拣足式组正式工作区。

当前主线暂定为纯 Python 方案，不预设 ROS：

- 树莓派 CM5 官方镜像。
- 板端优先使用 `/home/pi/RaspberryPi-CM5/xgovenv`。
- 通过 `xgolib` 控制机器狗运动、机械臂和夹爪。
- 通过 OpenCV/Picamera2/ONNX Runtime 完成视觉识别。
- 通过固定路线、yaw 闭环和视觉微调完成导航、抓取、投递。

当前阶段先做赛题研究和工程拆解，结论见：

- `task_study.md`
