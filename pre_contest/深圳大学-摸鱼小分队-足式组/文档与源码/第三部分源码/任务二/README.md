# 第三部分任务二：ROS 工作空间覆盖

官方要求创建工作空间 A，并在其中自建名为 `usb_cam` 的功能包；创建工作空间 B，在其中下载 `usb_cam` 源码；同时在 `/opt` 安装 `usb_cam`，最终使 `roscd usb_cam` 进入 `/opt` 下的包目录。

## 目录结构

```text
任务二/
├── ws_a/
│   └── src/usb_cam/       # 自建同名功能包
└── ws_b/
    └── src/               # 在虚拟机中下载 usb_cam
```

仓库跟踪 `ws_a` 和 `ws_b` 的工作空间结构。`ws_b/src/usb_cam` 按比赛流程在虚拟机中下载，不进入 Git。

## 准备工作空间 B

```bash
cd ~/2026-raicom-smart-delivery-sorting/pre_contest/深圳大学-摸鱼小分队-足式组/文档与源码/第三部分源码/任务二/ws_b/src
git clone https://github.com/ros-drivers/usb_cam.git
```

如比赛环境要求指定分支，应以现场可编译的 ROS Noetic 版本为准。

## 安装系统版本

```bash
sudo apt update
sudo apt install -y ros-noetic-usb-cam
```

检查安装结果：

```bash
ls /opt/ros/noetic/share/usb_cam
```

## 视频演示

进入任务目录并展示两个工作空间：

```bash
cd ~/2026-raicom-smart-delivery-sorting/pre_contest/深圳大学-摸鱼小分队-足式组/文档与源码/第三部分源码/任务二
pwd
ls ws_a/src
ls ws_b/src
```

分别查看两个 `usb_cam`：

```bash
cd ws_a/src/usb_cam
pwd
ls
cd ../../../ws_b/src/usb_cam
pwd
ls
```

最后清除可能残留的工作空间环境，只加载系统 ROS，展示包搜索路径并定位 `usb_cam`：

```bash
unset ROS_PACKAGE_PATH CMAKE_PREFIX_PATH
source /opt/ros/noetic/setup.bash
echo "$ROS_PACKAGE_PATH" | tr ':' '\n'
rospack profile
rospack find usb_cam
roscd usb_cam
pwd
```

`ROS_PACKAGE_PATH` 应包含 `/opt/ros/noetic/share`，最后的 `pwd` 必须输出：

```text
/opt/ros/noetic/share/usb_cam
```

## 提交前检查

- `ws_a/src/usb_cam` 是自建功能包。
- `ws_b/src/usb_cam` 是在虚拟机下载的源码包。
- `/opt/ros/noetic/share/usb_cam` 已安装。
- 视频中能看到两个工作空间及其中的功能包。
- `roscd usb_cam` 最终进入 `/opt/ros/noetic/share/usb_cam`。
- 视频不超过 5 分钟且不加速。
