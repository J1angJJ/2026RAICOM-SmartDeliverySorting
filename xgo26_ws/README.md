# xgo26_ws

2026 睿抗国赛智能配送与分拣足式组正式工作区。

当前主线暂定为纯 Python 方案，不预设 ROS：

- 树莓派 CM5 官方镜像。
- 板端优先使用 `/home/pi/RaspberryPi-CM5/xgovenv`。
- 通过 `xgolib` 控制机器狗运动、机械臂和夹爪。
- 通过 OpenCV/Picamera2/Ultralytics YOLO 完成视觉识别，必要时使用 ONNX Runtime。
- 通过固定路线、yaw 闭环和视觉微调完成导航、抓取、投递。

场地先验地图位于 `maps/field_map.json`。它以喷绘布左下角为原点，使用米和右手
坐标系，记录 TIFF 母版对应的循迹线、A-D 投放圆、抓取长方形、识别区以及两个
`30x30x30cm` 识别箱体。外围围挡位置未知，不写入静态占据物。

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

队员提供 `models/package_letter.pt` 后，可在板端只读相机测试推理，不会执行运动：

```bash
python tools/test_yolo.py --frames 10
```

该入口从共享服务读取完整 `main` BGR 原图，Ultralytics 在内存中完成 YOLO26 的
letterbox、推理和 NMS，不经过 JPEG，也不会再次占用 Picamera2。

相机默认使用自动曝光和自动白平衡。运动采集时注意终端输出中的 `exposure`，曝光时间超过约 `10000 us` 时容易产生运动模糊。完成现场测光后，可以在 `config.json` 的 `camera.controls` 中关闭自动控制并填写 `exposure_time_us`、`analogue_gain` 和 `colour_gains`，然后重启 `xgo26-camera.service`。锁定参数前必须分别检查场地明暗区域，不能仅凭一张画面决定。

### SSH 键盘遥控

确认机器狗周围安全，并保证 `oumax-manual.service`、任务监听服务和其他控制程序没有占用串口：

```bash
python tools/teleop_keyboard.py
```

按键采用自动停车保护，必须按住并依靠键盘重复发送才能持续运动：

```text
W / S    纯四轮前进 / 后退
A / D    保持当前姿态，步态向前左弧 / 右弧
Q / E    保持当前姿态，步态原地左微调 / 右微调
J / L    正常步态左转 / 右转，会先恢复中立姿态
1 / 2 / 3  抬头 / 中立 / 低头四轮姿态
+ / -    调整四轮前后速度
空格     立即停车
X        停车、恢复中立步态并退出
```

停止收到运动按键约 `0.65 s` 后会自动停车，`Ctrl+C`、SSH 挂断和终止信号也会执行停车清理。可用参数调整初始速度和保护时间：

```bash
python tools/teleop_keyboard.py --speed 20 --gait-forward 8 --gait-arc-turn 12 --gait-turn 20
```

需要逐步观察相机反馈时，使用带 `0.5 s` 硬上限的低头步态测试脚本。以下命令只执行一次约 `0.18 s` 的转向，随后立即停车：

```bash
python tools/test_gait_adjust.py left --turn-speed 20 --seconds 0.35
python tools/test_gait_adjust.py right --turn-speed 20 --seconds 0.35
python tools/test_gait_adjust.py shift-left --lateral-speed 8 --seconds 0.35
python tools/test_gait_adjust.py shift-right --lateral-speed 8 --seconds 0.35
```

实机慢速步态测试中，原地转向量 `8` 和 `12` 没有产生可测航向变化；转向量 `20`、持续 `0.40 s` 时约转过 `5°`。前进弧线可使用较小的转向量，具体位移仍需结合画面逐步标定。

直角弯采用两阶段逻辑：循迹阶段只有角点进入图像近场触发区后才停车；随后暂停视觉循迹，由 IMU 闭环执行保持低头的相对转向。单独测试入口如下，运行后会连续完成目标角度，必须先确认周围安全：

```bash
python tools/test_drive_actions.py corner-left --angle 90
python tools/test_drive_actions.py corner-right --angle 90
```

三段循迹线和两个连续右直角弯使用一个完整测试入口：

```bash
bash tools/run_three_segment_route.sh
```

包装脚本会临时停用厂家相机、手动控制和主菜单，启动比赛相机后运行路线；成功、报错或按 `Ctrl+C` 时都会停车并恢复厂家服务。如果控制串口仍被其他程序占用则拒绝启动。直线阶段使用四轮前进，视觉偏差超过阈值时停车并执行一次低头步态微调，然后恢复轮行。程序会在识别到右角点并观察到角点从相机下方消失后，执行配置中的短距离补偿，再通过 IMU 完成低头右转90度；这个过程重复两次，最后沿第三段运行并停车。现场参数集中在 `config.json` 的 `three_segment_route`，当前补偿为轮速28、`0.12 s`。

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
python tools/test_wheel_posture.py --pitch 20 --seconds 5
```

`view_down` 保持正常机身高度 `95 mm`，默认前倾 `+20°`。板端 XGOMINI
版 `xgolib` 的俯仰限幅为 `±22°`，比赛动作层也按该值做最终保护；资料中个别
`30°/35°` 示例实际会被库裁剪，不作为有效目标。三段循迹默认保持低头姿态并使用
纯四轮前进；切换到步态转弯时自动恢复中立姿态，再进入轮行时重新应用所选姿态。
普通 `move`、`move_by` 和纵向 `yaw_hold_move` 使用中立四轮姿态。

只读检查下位机 IMU 和 15 路舵机编码器反馈：

```bash
python tools/inspect_robot_feedback.py --samples 5 --interval 0.2
```

运行前仍需停止其他串口控制程序。该工具不初始化控制模式、不改变姿态，但创建
`xgolib.XGO` 对象时厂商库会发送一次零转速命令。输出中的舵机编号依次为
`11..43` 四腿 12 个关节和 `51..53` 机械臂 3 个关节。当前协议没有四个轮子的
编码器或里程反馈接口，不能把舵机角度误当作轮式里程计。

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
python tools/test_ball_grasp.py wheel-view --color red --save-image
python tools/test_ball_grasp.py align-approach --color red
python tools/test_ball_grasp.py staged
python tools/test_ball_grasp.py body-grasp --color red
python tools/test_ball_grasp.py grasp-once
python tools/test_ball_grasp.py catch --color red
```

`staged` 在同一个串口会话内依次等待回车并执行：

```text
body-down -> arm-down -> claw-close -> arm-up -> body-up -> arm-stow
```

等待回车期间机器人保持当前状态，可观察画面和机构位置；输入 `v` 会抓取一帧并输出
小球轮廓及 `grasp_ready` 判定，输入 `q` 会关闭程序但不复位机器人。若机械臂或本体
还在下探状态，通常应继续完成 `arm-up`、`body-up` 后再退出。

抓取视觉参数以比赛相机服务的 4:3 `lores` 码流标定。抓球模块只在画面下部 ROI
选择候选色块，避免上方人物、设备或场地外物体抢占最大轮廓；厂家 16:9 调试流仅作
浏览器兼容，不用于生成正式纵向位置参数。

以下入口用于孤立检查单个阶段：

```bash
python tools/test_ball_grasp.py body-down
python tools/test_ball_grasp.py arm-down
python tools/test_ball_grasp.py claw-close
python tools/test_ball_grasp.py arm-up
python tools/test_ball_grasp.py body-up
python tools/test_ball_grasp.py arm-stow
```

厂家 `xgolib` 每次创建控制对象都会复位机器人，因此不能在多个进程中依次运行上述
单阶段命令来拼接动作。需要保持上一阶段状态时必须使用 `staged`。不要跳过
`arm-up` 就执行 `body-up`，避免携球机械臂在本体抬起时碰撞头部。
`grasp-once` 暂时保留已经实机验证的交错下探顺序。

`body-grasp` 使用一个连续控制会话：先执行 `body-down`，随后读取比赛相机画面；
仅当目标球满足 `grasp_ready` 时才继续抓取，否则恢复本体并退出。

`wheel-view` 只进入低头轮态 `view_down` 姿态并读取一帧，不驱动车轮；取帧后自动
退出轮控并恢复中立姿态，用于单独标定低头行进阶段的小球视野。它输出独立的
`approach_ready`，表示可以停止轮式接近并切换到 `body-down`；该判定不与最终闭爪前
使用的 `grasp_ready` 混用。

`align-approach` 在低头轮态下进行离散闭环：横向偏差较大时停车，并通过 IMU 闭环
完成一次 `1°～3°` 的低头小角度转向；方向到位后再用四轮短步前后调整距离。每一步
都会停车重拍，丢失目标或达到步数上限会立即退出，不会直接执行抓取。

### 雷达局部定位

YDLIDAR T-mini Plus 暂时只把两个 `30x30x30cm` 识别箱体作为局部地标，不依赖位置
未确定的场地围挡，不承担全场建图，也不替代地面字母和图案视觉。`xgo26/lidar.py`
直接使用厂家 YDLidar SDK，将原始扫描转换为与 SDK 解耦的数据结构；点云先按空间
连续性分簇，再用 30cm 正面宽度先验拒绝长围挡和短小杂物。任务层只应消费
`CubeEstimate`，不要依赖 SDK 的 `LaserScan`。

首次上机前保持 `config.json` 中 `lidar.enabled=false`。确认雷达牢固安装、USB 串口
及供电正常后，先设置为 `true`，只运行静态读取：

```bash
python tools/test_lidar.py --scans 20
python tools/test_lidar.py --scans 20 --json
```

默认按厂家例程使用 `230400` 波特率、4K 采样率、10Hz 扫描频率、三角测距类型和
强度数据。板端优先从厂商已有的
`RaspberryPi-CM5/robots/Dog_LM/demos/YDLidar-SDK/build/python` 加载 SDK，不复制或
修改参考目录源码。

当前 `angle_offset_deg`、`clockwise_angles`、`sensor_forward_offset_m` 和
`sensor_left_offset_m` 都是未标定值。首次测试应在雷达正前方放置一块平整纸板，确认
纸板落在 `front_center_deg=0` 附近，再标定角度方向和雷达到机器人中心的安装偏移；
还必须确认雷达扫描平面低于 30cm 箱顶并能稳定打到箱体正面。
这些参数确认前，雷达结果不得触发移动。局部平面估计稳定后，再把
`robot_distance_m/yaw_deg/confidence` 接入识别区停车微调。

雷达自身不能判断当前看到的是识别区 1 还是识别区 2。状态机先沿循迹拓扑进入对应
识别区，视觉确认识别素材所在箱体后，才允许使用同一时段的 `CubeEstimate` 修正距离
和偏航；没有视觉确认时，尺寸相近的其他物体也不得触发控制。

算法内部坐标约定为机器人前方 `+x`、左侧 `+y`；`yaw_deg>0` 表示检测平面的左侧
距离更远。该符号只有在 `angle_offset_deg` 和 `clockwise_angles` 实机标定后才可信。

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
