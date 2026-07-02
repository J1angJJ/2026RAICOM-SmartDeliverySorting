# 第三部分任务一：乌龟轨迹录制与回放

本任务使用 `rosbag` 录制 `/turtle1/cmd_vel` 和 `/turtle1/pose`，生成 `run.bag`，再在第二个 turtlesim 窗口中回放。录制窗口保留最终轨迹，便于与回放窗口并排比较。

## 任务目录

```bash
cd ~/2026-raicom-smart-delivery-sorting/pre_contest/深圳大学-摸鱼小分队-足式组/文档与源码/第三部分源码/任务一
```

## 录制：4 个终端

终端 1，启动 ROS Master：

```bash
source /opt/ros/noetic/setup.bash
roscore
```

终端 2，启动左侧原始轨迹窗口：

```bash
source /opt/ros/noetic/setup.bash
rosrun turtlesim turtlesim_node __name:=turtlesim_record
```

终端 3，进入任务目录并开始录制：

```bash
cd ~/2026-raicom-smart-delivery-sorting/pre_contest/深圳大学-摸鱼小分队-足式组/文档与源码/第三部分源码/任务一
source /opt/ros/noetic/setup.bash
[ ! -f run.bag ] || mv run.bag "run_$(date +%Y%m%d-%H%M%S).bag"
rosbag record -O run.bag /turtle1/cmd_vel /turtle1/pose
```

必须等待终端显示 `Recording to run.bag` 后再操作，避免漏掉第一段运动。

终端 4，启动键盘遥控：

```bash
source /opt/ros/noetic/setup.bash
rosrun turtlesim turtle_teleop_key
```

保持终端 4 获得键盘焦点，用方向键画出包含明显转弯的轨迹。完成后先停止遥控，再停止录制，但不要关闭左侧轨迹窗口。

## 检查录制文件

在终端 3 执行：

```bash
ls -lh run.bag
rosbag info run.bag
```

输出中必须包含 `/turtle1/cmd_vel` 和 `/turtle1/pose`。

## 双窗口回放

在终端 4 启动右侧回放窗口：

```bash
source /opt/ros/noetic/setup.bash
ROS_NAMESPACE=/replay rosrun turtlesim turtlesim_node __name:=turtlesim_replay
```

确认右侧窗口出现后，在仍位于任务目录的终端 3 执行：

```bash
rosbag play run.bag /turtle1/cmd_vel:=/replay/turtle1/cmd_vel /turtle1/pose:=/recorded/turtle1/pose
```

左侧窗口保留录制轨迹，右侧窗口绘制回放轨迹。视频应清楚展示录制、`run.bag` 信息、播放过程及两条一致轨迹。

## 提交前检查

- 文件名为 `run.bag`，并保留在本任务目录。
- bag 中包含 `/turtle1/cmd_vel` 和 `/turtle1/pose`。
- 回放窗口能够复现原轨迹。
- 视频左下角显示“深圳大学 摸鱼小分队 足式组”。
- 视频不超过 5 分钟且不加速。
