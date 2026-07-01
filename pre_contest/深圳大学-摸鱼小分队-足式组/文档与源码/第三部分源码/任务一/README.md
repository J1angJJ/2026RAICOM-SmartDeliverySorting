# 第三部分任务一：乌龟轨迹 rosbag 录制与播放复现步骤

本文档用于在 Ubuntu + ROS 环境中复现第三部分任务一。任务要求使用 `turtlesim` 控制小乌龟运动，并使用 `rosbag` 录制一个名为 `run.bag` 的轨迹文件，最后播放该 bag 文件验证轨迹可以复现。

## 1. 任务目标

完成以下内容：

```text
1. 启动 turtlesim 仿真窗口。
2. 控制小乌龟运动，形成一段可观察轨迹。
3. 使用 rosbag 录制小乌龟运动相关话题。
4. 将录制文件命名为 run.bag。
5. 使用 rosbag play 播放 run.bag。
6. 播放时小乌龟轨迹与录制时一致。
7. 提交 run.bag 和演示视频。
```

## 2. 创建任务目录

```bash
mkdir -p ~/raicom_submit/学校名称_队伍名称_足式组/文档与源码/第三部分源码/任务一
mkdir -p ~/raicom_submit/学校名称_队伍名称_足式组/第三部分/任务一/视频
cd ~/raicom_submit/学校名称_队伍名称_足式组/第三部分/任务一
```

`run.bag` 最终建议放在：

```text
~/raicom_submit/学校名称_队伍名称_足式组/第三部分/任务一/run.bag
```

README 放在：

```text
~/raicom_submit/学校名称_队伍名称_足式组/文档与源码/第三部分源码/任务一/README.md
```

## 3. 检查 ROS 环境

```bash
source /opt/ros/noetic/setup.bash
rosversion -d
```

正常情况下输出：

```text
noetic
```

如果系统使用的是其他 ROS 1 版本，例如 Melodic，也可以继续完成该任务，但命令中的 ROS 路径需要对应调整。

## 4. 启动 roscore

打开第一个终端：

```bash
source /opt/ros/noetic/setup.bash
roscore
```

保持该终端运行。

## 5. 启动 turtlesim

打开第二个终端：

```bash
source /opt/ros/noetic/setup.bash
rosrun turtlesim turtlesim_node
```

正常情况下会出现蓝色背景的 turtlesim 仿真窗口。

## 6. 启动键盘控制节点

打开第三个终端：

```bash
source /opt/ros/noetic/setup.bash
rosrun turtlesim turtle_teleop_key
```

使用方向键控制小乌龟移动。

注意：需要让第三个终端保持当前焦点，方向键才会生效。

## 7. 查看话题

打开第四个终端：

```bash
source /opt/ros/noetic/setup.bash
rostopic list
```

应能看到类似话题：

```text
/rosout
/turtle1/cmd_vel
/turtle1/color_sensor
/turtle1/pose
```

本任务建议录制以下话题：

```text
/turtle1/cmd_vel
/turtle1/pose
```

其中：

```text
/turtle1/cmd_vel：控制小乌龟运动的速度指令
/turtle1/pose：小乌龟当前位姿
```

## 8. 开始录制 run.bag

进入任务一提交目录：

```bash
cd ~/raicom_submit/学校名称_队伍名称_足式组/第三部分/任务一
```

开始录制：

```bash
rosbag record -O run.bag /turtle1/cmd_vel /turtle1/pose
```

终端出现类似内容说明录制开始：

```text
[ INFO] Subscribing to /turtle1/cmd_vel
[ INFO] Subscribing to /turtle1/pose
[ INFO] Recording to run.bag.
```

## 9. 控制小乌龟运动

回到运行 `turtle_teleop_key` 的终端，使用方向键控制小乌龟运动。

建议控制小乌龟画出明显轨迹，例如：

```text
1. 向前移动一段。
2. 左转或右转。
3. 再向前移动一段。
4. 多次转向形成折线、方形或曲线轨迹。
```

录制时间建议控制在 20 到 40 秒，轨迹清晰即可。

完成后回到录制终端，按：

```text
Ctrl + C
```

停止录制。

确认生成文件：

```bash
ls -lh run.bag
```

## 10. 检查 bag 文件信息

```bash
rosbag info run.bag
```

正常应看到：

```text
path:        run.bag
duration:    ...
topics:      /turtle1/cmd_vel
             /turtle1/pose
```

如果 `topics` 中包含 `/turtle1/cmd_vel` 和 `/turtle1/pose`，说明录制内容正确。

## 11. 播放前重置 turtlesim

为了让播放轨迹更清晰，建议先关闭当前 turtlesim 窗口和键盘控制节点。

然后重新打开 turtlesim：

```bash
rosrun turtlesim turtlesim_node
```

如果需要清空轨迹，可以调用：

```bash
rosservice call /clear
```

## 12. 播放 run.bag

在任务一目录中执行：

```bash
cd ~/raicom_submit/学校名称_队伍名称_足式组/第三部分/任务一
rosbag play run.bag
```

播放时应能看到小乌龟根据录制的速度指令重新运动，轨迹与录制时一致或基本一致。

如果希望播放时完整复现速度，可以使用：

```bash
rosbag play --clock run.bag
```

## 13. 录屏建议

录屏建议按以下顺序展示：

```text
1. 打开终端，进入第三部分任务一目录。
2. 启动 roscore。
3. 启动 turtlesim_node。
4. 启动 turtle_teleop_key。
5. 执行 rostopic list，展示 /turtle1/cmd_vel 和 /turtle1/pose。
6. 执行 rosbag record -O run.bag /turtle1/cmd_vel /turtle1/pose。
7. 控制小乌龟运动，画出清晰轨迹。
8. 停止录制，执行 ls -lh run.bag。
9. 执行 rosbag info run.bag，展示 bag 文件话题信息。
10. 重新打开或清空 turtlesim。
11. 执行 rosbag play run.bag。
12. 展示小乌龟轨迹被播放复现。
```

视频中重点需要出现：

```text
1. rosbag record 正在录制。
2. 小乌龟运动轨迹清晰。
3. run.bag 文件已经生成。
4. rosbag info 能看到录制话题。
5. rosbag play 后轨迹可以复现。
6. 视频左下角显示：学校名称 + 队伍名称 + 足式组。
7. 录屏不超过 5 分钟，不加速。
```

## 14. 提交文件位置

第三部分任务一最终提交结构建议如下：

```text
学校名称_队伍名称_足式组/
├── 第三部分/
│   └── 任务一/
│       ├── 视频/
│       │   └── 03_任务一_乌龟轨迹录制与播放.mp4
│       └── run.bag
└── 文档与源码/
    └── 第三部分源码/
        └── 任务一/
            └── README.md
```

## 15. 常见问题

`turtlesim_node` 无法启动：

```bash
sudo apt install -y ros-noetic-turtlesim
```

`rosbag` 命令不存在：

```bash
sudo apt install -y ros-noetic-rosbag
```

找不到 `/turtle1/cmd_vel`：

```text
请确认 turtlesim_node 已经启动。
```

方向键不能控制小乌龟：

```text
请确认 turtle_teleop_key 所在终端处于当前焦点。
```

播放 bag 时小乌龟不动：

```text
请确认 run.bag 中录制了 /turtle1/cmd_vel。
可以通过 rosbag info run.bag 检查 topics。
```

## 16. 提交前检查

- `run.bag` 已生成。
- `run.bag` 位于 `第三部分/任务一/` 下。
- `rosbag info run.bag` 能看到 `/turtle1/cmd_vel`。
- `rosbag play run.bag` 能复现小乌龟运动轨迹。
- 视频中展示录制过程和播放过程。
- 视频左下角包含学校名称、队伍名称和足式组。
- 录屏不超过 5 分钟。
- 录屏没有加速。
