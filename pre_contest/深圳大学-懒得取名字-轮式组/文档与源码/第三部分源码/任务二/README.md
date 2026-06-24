# 第三部分任务二：ROS 工作空间覆盖复现步骤

本文档用于复现第三部分任务二。任务要求创建两个 ROS 工作空间，并验证 `roscd usb_cam` 最终进入 `/opt/ros/noetic/share/usb_cam` 路径。

## 1. 任务目标

完成以下内容：

```text
1. 创建工作空间 A，里面有一个名为 usb_cam 的功能包。
2. 创建工作空间 B，里面下载源码功能包 usb_cam。
3. 在 /opt 下安装 usb_cam。
4. 配置环境，使 roscd usb_cam 后进入 /opt 路径。
5. 录屏展示工作空间 A、工作空间 B 和 roscd usb_cam 的结果。
```

## 2. 创建提交目录

本仓库预置了工作空间 A 的自建 `usb_cam` 功能包，可直接同步到虚拟机：

```text
文档与源码/第三部分源码/任务二/
└── ws_a/
    └── src/usb_cam/
```

`ws_b` 按赛题要求应在虚拟机中现场创建，并通过 `git clone` 下载官方源码包；因此仓库中不预置 `ws_b` 内容。

```bash
mkdir -p ~/raicom_submit/学校名称_队伍名称_轮式组/第三部分/任务二/ws_a/src
mkdir -p ~/raicom_submit/学校名称_队伍名称_轮式组/第三部分/任务二/ws_b/src
mkdir -p ~/raicom_submit/学校名称_队伍名称_轮式组/第三部分/任务二/视频
mkdir -p ~/raicom_submit/学校名称_队伍名称_轮式组/文档与源码/第三部分源码/任务二
```

## 3. 创建工作空间 A

```bash
source /opt/ros/noetic/setup.bash
cd ~/raicom_submit/学校名称_队伍名称_轮式组/第三部分/任务二/ws_a/src
catkin_init_workspace
# 如果没有使用仓库预置的 ws_a，则执行：
# catkin_create_pkg usb_cam rospy std_msgs
```

编译工作空间 A：

```bash
cd ~/raicom_submit/学校名称_队伍名称_轮式组/第三部分/任务二/ws_a
catkin_make
```

检查：

```bash
ls ~/raicom_submit/学校名称_队伍名称_轮式组/第三部分/任务二/ws_a/src
```

应看到：

```text
usb_cam
```

这一步证明工作空间 A 中已经创建了名为 `usb_cam` 的功能包。

## 4. 创建工作空间 B 并下载 usb_cam 源码

```bash
source /opt/ros/noetic/setup.bash
mkdir -p ~/raicom_submit/学校名称_队伍名称_轮式组/第三部分/任务二/ws_b/src
cd ~/raicom_submit/学校名称_队伍名称_轮式组/第三部分/任务二/ws_b/src
catkin_init_workspace
git clone -b develop https://github.com/ros-drivers/usb_cam.git
```

检查：

```bash
ls ~/raicom_submit/学校名称_队伍名称_轮式组/第三部分/任务二/ws_b/src
ls ~/raicom_submit/学校名称_队伍名称_轮式组/第三部分/任务二/ws_b/src/usb_cam
```

应看到：

```text
CMakeLists.txt
package.xml
```

## 5. 安装编译依赖

```bash
sudo apt update
sudo apt install -y libv4l-0 libv4l-dev v4l-utils
```

## 6. 编译工作空间 B

```bash
cd ~/raicom_submit/学校名称_队伍名称_轮式组/第三部分/任务二/ws_b
source /opt/ros/noetic/setup.bash
catkin_make
```

加载工作空间 B 环境：

```bash
source ~/raicom_submit/学校名称_队伍名称_轮式组/第三部分/任务二/ws_b/devel/setup.bash
```

验证工作空间 B 的 `usb_cam`：

```bash
rospack find usb_cam
```

此时应输出类似：

```text
/home/用户名/raicom_submit/学校名称_队伍名称_轮式组/第三部分/任务二/ws_b/src/usb_cam
```

这一步证明工作空间 B 中下载的源码包可以被 ROS 找到。

## 7. 在 /opt 下安装 usb_cam

```bash
sudo apt update
sudo apt install -y ros-noetic-usb-cam
```

安装后检查：

```bash
ls /opt/ros/noetic/share/usb_cam
```

应能看到：

```text
package.xml
launch
```

## 8. 配置环境并验证 roscd usb_cam

关键点：最终验证时不要 source `ws_a` 或 `ws_b`，只加载官方 ROS 环境。

建议新开一个终端，执行：

```bash
source /opt/ros/noetic/setup.bash
rospack profile
rospack find usb_cam
roscd usb_cam
pwd
```

正确结果应为：

```text
/opt/ros/noetic/share/usb_cam
```

这是本题最关键的得分画面。

## 9. 如果 roscd 进入了工作空间

如果输出类似：

```text
/home/用户名/raicom_submit/学校名称_队伍名称_轮式组/第三部分/任务二/ws_b/src/usb_cam
```

说明当前终端加载了工作空间 B。

解决方法：

```bash
source /opt/ros/noetic/setup.bash
rospack profile
roscd usb_cam
pwd
```

或者重新打开一个终端，只执行：

```bash
source /opt/ros/noetic/setup.bash
roscd usb_cam
pwd
```

## 10. 录屏演示顺序

建议按以下顺序录屏：

```bash
cd ~/raicom_submit/学校名称_队伍名称_轮式组/第三部分/任务二
ls
```

展示两个工作空间：

```bash
ls ws_a/src
ls ws_b/src
```

展示工作空间 A 中创建的 `usb_cam`：

```bash
cd ~/raicom_submit/学校名称_队伍名称_轮式组/第三部分/任务二/ws_a/src/usb_cam
pwd
ls
```

展示工作空间 B 中下载的 `usb_cam`：

```bash
cd ~/raicom_submit/学校名称_队伍名称_轮式组/第三部分/任务二/ws_b/src/usb_cam
pwd
ls
```

展示 `/opt` 下安装的 `usb_cam`：

```bash
ls /opt/ros/noetic/share/usb_cam
```

最终重点演示：

```bash
source /opt/ros/noetic/setup.bash
rospack find usb_cam
roscd usb_cam
pwd
```

最后必须显示：

```text
/opt/ros/noetic/share/usb_cam
```

## 11. 提交结构

```text
学校名称_队伍名称_轮式组/
├── 第三部分/
│   └── 任务二/
│       ├── ws_a/
│       ├── ws_b/
│       └── 视频/
└── 文档与源码/
    └── 第三部分源码/
        └── 任务二/
            └── README.md
```

## 12. 提交前检查

- `ws_a/src/usb_cam` 存在。
- `ws_b/src/usb_cam` 存在。
- `/opt/ros/noetic/share/usb_cam` 存在。
- `rospack find usb_cam` 最终指向 `/opt/ros/noetic/share/usb_cam`。
- `roscd usb_cam` 后执行 `pwd` 显示 `/opt/ros/noetic/share/usb_cam`。
- 视频中展示两个工作空间、`/opt` 安装结果和最终 `roscd usb_cam`。
- 录屏不超过 5 分钟，且没有加速。
