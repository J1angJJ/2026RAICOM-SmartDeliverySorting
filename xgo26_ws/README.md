# xgo26_ws

2026 睿抗国赛智能配送与分拣足式组正式工作区。

当前主线暂定为纯 Python 方案，不预设 ROS：

- 树莓派 CM5 官方镜像。
- 板端优先使用 `/home/pi/RaspberryPi-CM5/xgovenv`。
- 通过 `xgolib` 控制机器狗运动、机械臂和夹爪。
- 通过 OpenCV/Picamera2/ONNX Runtime 完成视觉识别。
- 通过固定路线、yaw 闭环和视觉微调完成导航、抓取、投递。

比赛移动动作集中在 `xgo26/competition_drive.py`：前进、后退和循迹航向微调只驱动四个轮子，原地角度转向仍使用机器狗正常步态。横移目前也保留厂家步态，后续按沙盘实测在这个文件内替换即可。

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
FOLLOW_TO_INSPECTION_1
DETECT_PACKAGE_1
RETURN_TO_LINE_1
FOLLOW_TO_INSPECTION_2
DETECT_PACKAGE_2
RETURN_TO_LINE_2
FOLLOW_TO_PICK_BRANCH
ENTER_PICK_AREA
PICK_BALL
DELIVER_BALL
RETURN_TO_PICK_AREA
PICK_BALL
DELIVER_BALL
FINISH
```

从出发区到两个识别点、再到包裹抓取区入口的路线已按地面循迹线编排。离开循迹线后的包裹抓取、A/B/C/D 投放和返回抓取区先按短时标定动作编排，后续由视觉微调和现场参数补强。

核心路线名：

```text
start_to_recognition_1
recognition_1_to_line
recognition_1_to_recognition_2
recognition_2_to_line
recognition_2_to_pick_area
enter_pick_area
drop_A / drop_B / drop_C / drop_D
drop_A_to_pick_area / drop_B_to_pick_area / drop_C_to_pick_area / drop_D_to_pick_area
```

调参主要改 `config.json` 中：

- `robot.drive.forward_input_max`、`turn_input_max`、`wheel_speed_max` 和模式切换等待时间。
- `line_follow.seconds`、`speed`、`turn_gain`、`max_turn`、`line.roi_top_ratio`、`line.min_area`。
- `turn_to.yaw` 和 `timeout`。
- `yaw_hold_move.seconds`、`speed`、`yaw`、`turn_gain`。

当前没有里程计，所有 `seconds`、横移方向和角度都只是按图 4-3 搭出的初始占位值，正式运行前必须逐段标定。

### 运行单项脚本

先单独测试纯轮前进和正常步态转向：

```bash
python tools/test_drive_actions.py forward --speed 8 --seconds 1
python tools/test_drive_actions.py backward --speed 8 --seconds 1
python tools/test_drive_actions.py turn-left --angle 30
python tools/test_drive_actions.py turn-right --angle 30
```

前两条会启用四轮独立控制，四条腿不执行行走步态；后两条会先退出轮控，再使用 IMU 闭环的正常转向。测试结束会停车并恢复到步态模式。

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

当前纯轮模式没有里程计，`distance_scale=0.5` 暂时沿用原来的距离时间经验值。若仍偏大或偏小，可以直接改缩放：

```bash
python tools/test_square_motion.py --distance-scale 0.45
python tools/test_square_motion.py --distance-scale 0.6
```

也可以直接指定每条边的轮式前进时间：

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
