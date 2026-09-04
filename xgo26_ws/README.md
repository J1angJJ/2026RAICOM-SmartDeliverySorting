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

## 快速运行

在普通电脑上验证任务流程：

```bash
cd xgo26_ws
python3 scripts/check_environment.py
python3 scripts/run_mission.py --dry-run --use-expected
```

在机器狗 CM5 上运行时，建议使用官方环境：

```bash
cd ~/2026-raicom-smart-delivery-sorting/xgo26_ws
source /home/pi/RaspberryPi-CM5/xgovenv/bin/activate
python scripts/check_environment.py --strict
python scripts/run_mission.py --use-expected
```

当前 `config.json` 里的路线全部是占位路线，正式运行前必须先在空旷环境逐段标定。包裹识别模型尚未接入，`--use-expected` 会使用配置中的示例识别结果跑通任务编排。
