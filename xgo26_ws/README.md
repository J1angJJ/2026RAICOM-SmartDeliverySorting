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

## 常用命令

### 连接机器狗

```bash
ssh pi@192.168.31.70
```

### 进入国赛目录并激活环境

```bash
cd ~/2026-raicom-smart-delivery-sorting/xgo26_ws
source /home/pi/RaspberryPi-CM5/xgovenv/bin/activate
```

确认当前 Python 来自官方环境：

```bash
which python
python --version
```

### 更新仓库代码

```bash
cd ~/2026-raicom-smart-delivery-sorting
git pull
cd xgo26_ws
source /home/pi/RaspberryPi-CM5/xgovenv/bin/activate
```

### 环境自检

普通检查：

```bash
python scripts/check_environment.py
```

上板严格检查：

```bash
python scripts/check_environment.py --strict
```

### 运行任务

不连接硬件，只验证完整任务流程：

```bash
python scripts/run_mission.py --dry-run --use-expected
```

连接硬件，但暂时使用 `config.json` 中的示例识别结果：

```bash
python scripts/run_mission.py --use-expected
```

后续模型接入后，正式运行：

```bash
python scripts/run_mission.py
```

启动常驻任务监听服务：

```bash
python scripts/run_task_server.py
```

监听服务默认端口为 `8767`。启动时会先初始化控制模式，然后等待 HTTP 请求：

```bash
curl http://127.0.0.1:8767/health
curl -X POST http://127.0.0.1:8767/square -H 'Content-Type: application/json' -d '{"side_cm":50}'
curl -X POST http://127.0.0.1:8767/mission -H 'Content-Type: application/json' -d '{"use_expected":true}'
curl -X POST http://127.0.0.1:8767/stop
```

当前主状态机：

```text
BOOT_CHECK
FOLLOW_TO_RECOGNITION_1
DETECT_PACKAGE_1
FOLLOW_TO_RECOGNITION_2
DETECT_PACKAGE_2
GO_TO_PICK_AREA
PICK_AND_DELIVER
RETURN_TO_PICK_AREA
PICK_AND_DELIVER
FINISH
```

从出发区到两个识别点的路线已按地面循迹线编排。调参主要改 `config.json` 中 `line_follow` 步骤的 `seconds`、`speed`、`turn_gain`、`max_turn`、`line.roi_top_ratio` 和 `line.min_area`；到点后转身识别的角度改对应 `turn_to.yaw`。

### 运行单项脚本

打印 `config.json` 里的示例任务：

```bash
python tools/print_expected_tasks.py
```

测试摄像头：

```bash
python tools/test_camera.py
```

测试 50cm 正方形运动：

```bash
python tools/test_square_motion.py
```

如果感觉厂家 `move_x_by` 距离估算不对，可以改用定时前进模式对比：

```bash
python tools/test_square_motion.py --timed --forward-seconds 2.3
```

分段测试小球抓取：

```bash
python tools/test_ball_grasp.py detect --color red --save-image
python tools/test_ball_grasp.py align --color red
python tools/test_ball_grasp.py grasp-once
python tools/test_ball_grasp.py catch --color red
```

### 运行前停止厂商占用服务

如果摄像头或串口被厂商服务占用，先停掉：

```bash
sudo systemctl stop oumax-camera oumax-manual
```

恢复厂商服务：

```bash
sudo systemctl start oumax-camera oumax-manual
```

查看服务状态：

```bash
systemctl status oumax-camera oumax-manual --no-pager
```

### 停止任务

终端中按：

```text
Ctrl+C
```

然后让机器狗停止并复位，后续会补专门脚本；当前可重新运行 dry-run 或手动重启程序确认状态。

### 退出环境和 SSH

退出 Python 虚拟环境：

```bash
deactivate
```

退出 SSH：

```bash
exit
```

### 安全关机

在机器狗 SSH 里面执行：

```bash
sync
sudo systemctl poweroff
```

从本机一条命令远程关机：

```bash
ssh pi@192.168.31.70 'sync; sudo systemctl poweroff'
```

关机后等待屏幕、风扇或指示灯进入关机状态，再断电或拔卡。

## 本机快速运行

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
