# 第四部分：ROS 建图与导航

本部分使用 ROS Noetic、Gazebo、TurtleBot3、gmapping 与 move_base 完成四面墙建图、三个圆柱建图和自动导航写“足”字。正式工作空间位于仓库内，不需要复制到额外英文目录。

## 工作空间

```bash
cd ~/2026-raicom-smart-delivery-sorting/pre_contest/深圳大学-摸鱼小分队-足式组/文档与源码/第四部分源码/raicom_nav_ws
```

源码结构：

```text
raicom_nav_ws/src/raicom_nav/
├── launch/
│   ├── task1_mapping.launch
│   ├── task2_mapping_save.launch
│   └── task3_navigation.launch
├── maps/
│   ├── task1_map.yaml
│   ├── task1_map.pgm
│   ├── task2_map.yaml
│   └── task2_map.pgm
├── rviz/task3_zu_nav.rviz
└── scripts/
    ├── spawn_arena.py
    └── write_zu_nav.py
```

## 统一准备

```bash
cd ~/2026-raicom-smart-delivery-sorting/pre_contest/深圳大学-摸鱼小分队-足式组/文档与源码/第四部分源码/raicom_nav_ws
source /opt/ros/noetic/setup.bash
chmod +x src/raicom_nav/scripts/*.py
catkin_make
source devel/setup.bash
rospack find raicom_nav
```

每次切换任务前可清理残留 Gazebo 进程：

```bash
killall gzserver gzclient 2>/dev/null || true
```

## 任务一：四面墙建图

终端 1：

```bash
cd ~/2026-raicom-smart-delivery-sorting/pre_contest/深圳大学-摸鱼小分队-足式组/文档与源码/第四部分源码/raicom_nav_ws
source devel/setup.bash
export TURTLEBOT3_MODEL=burger
roslaunch raicom_nav task1_mapping.launch gui:=true
```

终端 2：

```bash
source /opt/ros/noetic/setup.bash
export TURTLEBOT3_MODEL=burger
roslaunch turtlebot3_teleop turtlebot3_teleop_key.launch
```

遥控小车沿四面墙运动，使 RViz 地图轮廓完整闭合。终端 3 保存地图：

```bash
cd ~/2026-raicom-smart-delivery-sorting/pre_contest/深圳大学-摸鱼小分队-足式组/文档与源码/第四部分源码/raicom_nav_ws
source devel/setup.bash
rosrun map_server map_saver -f src/raicom_nav/maps/task1_map
ls -lh src/raicom_nav/maps/task1_map.{yaml,pgm}
```

## 任务二：三个圆柱与自动保存地图

终端 1：

```bash
cd ~/2026-raicom-smart-delivery-sorting/pre_contest/深圳大学-摸鱼小分队-足式组/文档与源码/第四部分源码/raicom_nav_ws
source devel/setup.bash
export TURTLEBOT3_MODEL=burger
roslaunch raicom_nav task2_mapping_save.launch gui:=true save_delay:=120
```

终端 2 使用与任务一相同的遥控命令，让地图清楚显示三个圆柱。自动保存完成后在终端 3 检查：

```bash
cd ~/2026-raicom-smart-delivery-sorting/pre_contest/深圳大学-摸鱼小分队-足式组/文档与源码/第四部分源码/raicom_nav_ws
ls -lh src/raicom_nav/maps/task2_map.{yaml,pgm}
```

视频应展示 Gazebo 中的三个圆柱、RViz 地图、launch 自动保存信息和地图文件，并另存三个圆柱清晰可见的截图。

## 任务三：自动导航写“足”字

任务三 launch 会启动 Gazebo、任务一地图、move_base、专用 RViz 配置与写字脚本，并自动发布初始位姿。

```bash
cd ~/2026-raicom-smart-delivery-sorting/pre_contest/深圳大学-摸鱼小分队-足式组/文档与源码/第四部分源码/raicom_nav_ws
source devel/setup.bash
export TURTLEBOT3_MODEL=burger
roslaunch raicom_nav task3_navigation.launch gui:=true rviz:=true auto_start:=true start_delay:=20
```

RViz 中 `ActualPath` 订阅 `/zu_actual_path`。等待轨迹执行完成并形成“足”字，最终画面停留至少 5 秒。

若虚拟机中的 RViz 因 OpenGL 退出，重启任务前执行：

```bash
export LIBGL_ALWAYS_SOFTWARE=1
```

## 提交前检查

- 任务一生成 `task1_map.yaml` 和 `task1_map.pgm`。
- 任务二生成 `task2_map.yaml` 和 `task2_map.pgm`，并保留三个圆柱截图及自动保存 launch。
- 任务三能够自动运行，RViz 实际轨迹形成“足”字。
- 三个任务的视频左下角均显示“深圳大学 摸鱼小分队 足式组”。
- 每个视频不超过 5 分钟且不加速。
