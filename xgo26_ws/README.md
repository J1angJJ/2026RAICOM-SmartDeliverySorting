# xgo26_ws

2026 睿抗国赛智能配送与分拣足式组正式工作区。

当前主线暂定为纯 Python 方案，不预设 ROS：

- 树莓派 CM5 官方镜像。
- 板端优先使用 `/home/pi/RaspberryPi-CM5/xgovenv`。
- 通过 `xgolib` 控制机器狗运动、机械臂和夹爪。
- 通过 OpenCV/Picamera2/ONNX Runtime 完成视觉识别。
- 通过固定路线、yaw 闭环和视觉微调完成导航、抓取、投递。

比赛移动动作集中在 `xgo26/competition_drive.py`：前进、后退和循迹航向微调只驱动四个轮子，原地角度转向仍使用机器狗正常步态。横移目前也保留厂家步态，后续按沙盘实测在这个文件内替换即可。

视觉由 `xgo26-camera.service` 独占 Picamera2 并向浏览器、YOLO 和传统视觉分发同一时刻的最新帧，设计和接口见 `vision_pipeline.md`。

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

检查共享相机服务：

```bash
curl http://127.0.0.1:8090/health
python tools/test_camera.py --stream lores
python tools/test_camera.py --stream main
```

浏览器预览：

```text
http://192.168.31.70:8090/
```

需要前台调试相机服务时，先确认厂商相机服务已经停止，再运行：

```bash
python scripts/run_camera_service.py
```

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

### 采集 YOLO 图片

采集器只读取 `xgo26-camera.service` 的共享主码流，不会直接占用摄像头。默认保存完整的 `1296x972` 原图，以及曝光时间、模拟增益、亮度、过曝/欠曝比例和清晰度等元数据。输出位于已忽略的 `datasets/raw/`，不会进入 Git。

手动采集：

```bash
python tools/capture_yolo_images.py --session recognition_letters_01
```

终端中按空格保存，按 `A` 开关自动采集，按 `Q` 退出。启动后按固定间隔自动采集：

```bash
python tools/capture_yolo_images.py --session placement_letters_motion_01 --auto --interval 0.4
```

需要过滤几乎没有变化的连续画面时，可以增加最低灰度变化阈值：

```bash
python tools/capture_yolo_images.py --session placement_letters_motion_02 --auto --interval 0.4 --min-change 2
```

每个批次包含 `images/`、`frames.jsonl` 和 `session.json`。不要直接在这个原始目录中裁图或覆盖图片；后续从原图生成训练集，并按采集批次划分训练集和验证集。

相机默认使用自动曝光和自动白平衡。运动采集时注意终端输出中的 `exposure`，曝光时间超过约 `10000 us` 时容易产生运动模糊。完成现场测光后，可以在 `config.json` 的 `camera.controls` 中关闭自动控制并填写 `exposure_time_us`、`analogue_gain` 和 `colour_gains`，然后重启 `xgo26-camera.service`。锁定参数前必须分别检查场地明暗区域，不能仅凭一张画面决定。

### SSH 键盘遥控

确认机器狗周围安全，并保证 `oumax-manual.service`、任务监听服务和其他控制程序没有占用串口：

```bash
python tools/teleop_keyboard.py
```

按键采用自动停车保护，必须按住并依靠键盘重复发送才能持续运动：

```text
W / S    纯四轮前进 / 后退
A / D    正常步态原地左转 / 右转
Q / E    纯四轮向前左微调 / 右微调
1 / 2 / 3  抬头 / 中立 / 低头四轮姿态
+ / -    调整四轮前后速度
空格     立即停车
X        停车、恢复中立步态并退出
```

停止收到运动按键约 `0.65 s` 后会自动停车，`Ctrl+C`、SSH 挂断和终止信号也会执行停车清理。可用参数调整初始速度和保护时间：

```bash
python tools/teleop_keyboard.py --speed 6 --turn-speed 16 --deadman 0.45
```

采集器与遥控器可以在两个 SSH 终端同时运行：采集器只读共享相机，遥控器独占控制串口。仓库内新启动的第二个控制程序会因 `/tmp/xgo26-serial-ttyAMA0.lock` 被拒绝，但厂家程序不识别这个锁，因此仍需人工确认 `oumax-manual.service` 已停止。

推荐的运动数据采集顺序：

```text
终端一：启动 capture_yolo_images.py 并开启自动采集
终端二：启动 teleop_keyboard.py，低速按住方向键移动
终端二：先按空格停车，再按 X 退出
终端一：按 A 停止自动采集，按 Q 退出
```

### 运行单项脚本

先单独测试纯轮前进和正常步态转向：

```bash
python tools/test_drive_actions.py forward --speed 8 --seconds 1
python tools/test_drive_actions.py backward --speed 8 --seconds 1
python tools/test_drive_actions.py turn-left --angle 30
python tools/test_drive_actions.py turn-right --angle 30
```

前两条会启用四轮独立控制，四条腿不执行行走步态；后两条会先退出轮控，再使用 IMU 闭环的正常转向。测试结束会停车并恢复到步态模式。

测试低头四轮姿态；该命令不让轮子转动，保持指定秒数后恢复中立步态：

```bash
python tools/test_wheel_posture.py --pitch 15 --seconds 5
```

`view_down` 保持正常机身高度 `95 mm`，使用厂商循迹例程采用的最大前倾角
`+15°`。三段循迹默认保持该姿态并使用纯四轮前进；切换到步态转弯时自动恢复中立姿态。普通 `move`、`move_by` 和纵向 `yaw_hold_move` 使用中立四轮姿态。参数位于 `robot.drive.wheel_postures`，首次实测时应扶稳机器狗并确认四轮均正常承重。

打印 `config.json` 里的示例任务：

```bash
python tools/print_expected_tasks.py
```

测试摄像头；`--direct` 仅用于相机服务停止后的底层排查：

```bash
python tools/test_camera.py
python tools/test_camera.py --stream main
python tools/test_camera.py --direct
```

只检查循迹视觉，不初始化机器狗或发送运动指令：

```bash
python tools/test_line_vision.py
python tools/test_line_vision.py --input debug/example.jpg --output debug/line_debug.jpg
```

输出图左侧为扫描点和目标中心，右侧为黑线掩码。循迹参数集中在
`config.json` 的 `line_following`，路线步骤只保留速度、时长和转向幅度等运动参数。

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

### 运行前处理厂商占用服务

比赛相机服务启用后会替代 `oumax-camera`，不要同时启动两者。如果串口被手动控制服务占用，再单独停止 `oumax-manual`：

```bash
sudo systemctl stop oumax-manual
```

相机服务的安装和回滚命令见 `vision_pipeline.md`。恢复厂商手动控制服务：

```bash
sudo systemctl start oumax-manual
```

查看服务状态：

```bash
systemctl status xgo26-camera oumax-manual --no-pager
```

### 板载 B 键一键启动

厂家开机入口是 `/etc/rc.local` 启动的 `RaspberryPi-CM5/common/main.py`。它负责屏幕主菜单、ABCD 按键和厂家子程序调度；选择子程序后会阻塞等待子程序结束。主界面的 B 键原本没有功能，因此比赛模式将它挂接为：

```text
第一次按 B -> 1.2 秒内再按一次 B -> 屏幕倒计时 3 秒 -> 启动正式任务
```

第二次按键超时会取消。任务正在运行时有文件锁防止重复启动；`oumax-manual.service` 仍在占用串口、共享相机健康检查失败时都会拒绝启动并在屏幕提示。启动器不导入厂家 `uiutils`，避免为显示和按键再次打开机器狗串口。

仓库默认设置 `config.json` 中的 `board_start.armed` 为 `false`。此时可以安装挂接并测试双击 B，屏幕只会显示 `MISSION NOT ARMED`，绝不会运行任务。完成分段运动测试后才将它改为 `true`；双击窗口和倒计时也在同一配置段调整。

部署前先确认仓库位于默认板端路径，并检查厂家文件是否与已知版本匹配：

```bash
cd ~/2026-raicom-smart-delivery-sorting/xgo26_ws
python deploy/install_board_button.py check
```

进入比赛模式前只需配置一次服务。以下操作可逆，但必须在机器狗静止并确认没有其他队员运行控制程序时执行：

```bash
sudo systemctl disable --now oumax-manual.service
sudo systemctl disable --now oumax-camera.service
sudo install -m 644 deploy/systemd/xgo26-camera.service /etc/systemd/system/xgo26-camera.service
sudo systemctl daemon-reload
sudo systemctl enable --now xgo26-camera.service
sudo /home/pi/RaspberryPi-CM5/xgovenv/bin/python deploy/install_board_button.py install
sudo systemctl restart --no-block rc-local.service
```

安装工具会先保留 `common/main.py.before-xgo26`，校验修改后的 Python 语法，再原子替换厂家文件。它只替换原本无功能的 B 键分支，不改下位机固件、串口协议或其他菜单项。

检查挂接和运行日志：

```bash
python deploy/install_board_button.py check
tail -f /home/pi/app.log
```

恢复厂家主界面及原服务：

```bash
sudo /home/pi/RaspberryPi-CM5/xgovenv/bin/python deploy/install_board_button.py restore
sudo systemctl disable --now xgo26-camera.service
sudo systemctl enable --now oumax-camera.service oumax-manual.service
sudo systemctl restart --no-block rc-local.service
```

恢复操作会保留备份文件以便核对，不自动删除任何厂家源码或备份。下次上机应先完成 `check` 和服务状态检查，再在机器狗架空或有人扶稳的情况下测试双击确认；当前路线尚未完成场地标定，不得直接放地运行完整任务。

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
