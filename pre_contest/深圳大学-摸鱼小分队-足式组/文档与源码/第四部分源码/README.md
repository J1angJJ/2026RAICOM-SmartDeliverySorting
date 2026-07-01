# 第四部分：ROS 建图与导航复现步骤

本文档用于在 Ubuntu + ROS Noetic 环境中复现第四部分“ROS 建图与导航”任务。第四部分包含三个任务：

```text
任务一：四面墙 Gazebo 环境建图并保存地图。
任务二：添加三个圆柱物体，使用 launch 文件自动保存地图，并提交截图。
任务三：使用任务一地图进行定点导航，使小车轨迹写出“足”字。
```

## 1. 环境准备

安装 TurtleBot3、Gazebo、SLAM、导航和地图保存相关依赖：

```bash
sudo apt update
sudo apt install -y \
  ros-noetic-turtlebot3 \
  ros-noetic-turtlebot3-simulations \
  ros-noetic-turtlebot3-slam \
  ros-noetic-turtlebot3-navigation \
  ros-noetic-gmapping \
  ros-noetic-map-server \
  ros-noetic-navigation \
  ros-noetic-teleop-twist-keyboard \
  ros-noetic-xacro
```

设置 TurtleBot3 模型：

```bash
echo "export TURTLEBOT3_MODEL=burger" >> ~/.bashrc
source ~/.bashrc
```

## 2. 创建工作目录

为避免中文路径影响 ROS 查找包，实际运行目录使用英文路径：

```bash
mkdir -p /home/noetic/raicom_nav_work/raicom_nav_ws/src/raicom_nav/{launch,scripts,maps,screenshots}
cd /home/noetic/raicom_nav_work/raicom_nav_ws/src/raicom_nav
```

创建 `package.xml`：

```bash
gedit package.xml
```

写入：

```xml
<?xml version="1.0"?>
<package format="2">
  <name>raicom_nav</name>
  <version>0.0.1</version>
  <description>RAICOM mapping and navigation</description>
  <maintainer email="noetic@example.com">noetic</maintainer>
  <license>MIT</license>

  <exec_depend>rospy</exec_depend>
  <exec_depend>gazebo_ros</exec_depend>
  <exec_depend>gazebo_msgs</exec_depend>
  <exec_depend>geometry_msgs</exec_depend>
  <exec_depend>nav_msgs</exec_depend>
  <exec_depend>move_base_msgs</exec_depend>
  <exec_depend>actionlib</exec_depend>
</package>
```

加入 ROS 包搜索路径：

```bash
cd /home/noetic/raicom_nav_work/raicom_nav_ws
catkin_make
source devel/setup.bash
echo "source /home/noetic/raicom_nav_work/raicom_nav_ws/devel/setup.bash" >> ~/.bashrc
rospack profile
rospack find raicom_nav
```

正常应输出：

```text
/home/noetic/raicom_nav_work/raicom_nav_ws/src/raicom_nav
```

## 3. 创建场地生成脚本

创建脚本：

```bash
gedit /home/noetic/raicom_nav_work/raicom_nav_ws/src/raicom_nav/scripts/spawn_arena.py
```

该脚本用于在 Gazebo 中生成：

```text
1. 3m x 4m 四面墙环境。
2. 任务二需要的三个圆柱障碍物。
```

写入：

```python
#!/usr/bin/env python3
import argparse

import rospy
from gazebo_msgs.srv import SpawnModel, DeleteModel
from geometry_msgs.msg import Pose


def pose(x, y, z):
    p = Pose()
    p.position.x = x
    p.position.y = y
    p.position.z = z
    p.orientation.w = 1.0
    return p


def box_sdf(name, sx, sy, sz):
    return f"""
<sdf version="1.6">
  <model name="{name}">
    <static>true</static>
    <link name="link">
      <collision name="collision">
        <geometry><box><size>{sx} {sy} {sz}</size></box></geometry>
      </collision>
      <visual name="visual">
        <geometry><box><size>{sx} {sy} {sz}</size></box></geometry>
      </visual>
    </link>
  </model>
</sdf>
"""


def cylinder_sdf(name, radius, length):
    return f"""
<sdf version="1.6">
  <model name="{name}">
    <static>true</static>
    <link name="link">
      <collision name="collision">
        <geometry><cylinder><radius>{radius}</radius><length>{length}</length></cylinder></geometry>
      </collision>
      <visual name="visual">
        <geometry><cylinder><radius>{radius}</radius><length>{length}</length></cylinder></geometry>
      </visual>
    </link>
  </model>
</sdf>
"""


def spawn(spawner, name, sdf, x, y, z):
    spawner(name, sdf, "", pose(x, y, z), "world")
    rospy.loginfo("spawned %s", name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["walls", "cylinders"], default="walls")
    args, _ = parser.parse_known_args()

    rospy.init_node("spawn_raicom_arena")
    rospy.wait_for_service("/gazebo/spawn_sdf_model")
    rospy.wait_for_service("/gazebo/delete_model")

    spawner = rospy.ServiceProxy("/gazebo/spawn_sdf_model", SpawnModel)
    deleter = rospy.ServiceProxy("/gazebo/delete_model", DeleteModel)

    for name in [
        "north_wall", "south_wall", "east_wall", "west_wall",
        "cylinder_1", "cylinder_2", "cylinder_3"
    ]:
        try:
            deleter(name)
        except Exception:
            pass

    spawn(spawner, "north_wall", box_sdf("north_wall", 3.0, 0.08, 1.0), 0.0, 2.0, 0.5)
    spawn(spawner, "south_wall", box_sdf("south_wall", 3.0, 0.08, 1.0), 0.0, -2.0, 0.5)
    spawn(spawner, "east_wall", box_sdf("east_wall", 0.08, 4.0, 1.0), 1.5, 0.0, 0.5)
    spawn(spawner, "west_wall", box_sdf("west_wall", 0.08, 4.0, 1.0), -1.5, 0.0, 0.5)

    if args.mode == "cylinders":
        spawn(spawner, "cylinder_1", cylinder_sdf("cylinder_1", 0.18, 0.8), -0.6, 0.8, 0.4)
        spawn(spawner, "cylinder_2", cylinder_sdf("cylinder_2", 0.18, 0.8), 0.55, 0.1, 0.4)
        spawn(spawner, "cylinder_3", cylinder_sdf("cylinder_3", 0.18, 0.8), -0.15, -0.9, 0.4)


if __name__ == "__main__":
    main()
```

赋予执行权限：

```bash
chmod +x /home/noetic/raicom_nav_work/raicom_nav_ws/src/raicom_nav/scripts/spawn_arena.py
```

## 4. 任务一：四面墙环境建图

创建 launch 文件：

```bash
gedit /home/noetic/raicom_nav_work/raicom_nav_ws/src/raicom_nav/launch/task1_mapping.launch
```

写入：

```xml
<launch>
  <arg name="model" default="$(env TURTLEBOT3_MODEL)"/>
  <arg name="gui" default="true"/>

  <include file="$(find gazebo_ros)/launch/empty_world.launch">
    <arg name="paused" value="false"/>
    <arg name="use_sim_time" value="true"/>
    <arg name="gui" value="$(arg gui)"/>
  </include>

  <param name="robot_description"
         command="$(find xacro)/xacro $(find turtlebot3_description)/urdf/turtlebot3_$(arg model).urdf.xacro"/>

  <node pkg="gazebo_ros" type="spawn_model" name="spawn_turtlebot3"
        args="-urdf -model turtlebot3_$(arg model) -x 0 -y 0 -z 0 -param robot_description"/>

  <node pkg="raicom_nav" type="spawn_arena.py" name="spawn_arena_walls"
        args="--mode walls" output="screen"/>

  <include file="$(find turtlebot3_slam)/launch/turtlebot3_slam.launch">
    <arg name="slam_methods" value="gmapping"/>
  </include>
</launch>
```

运行建图环境：

```bash
killall gzserver gzclient
source /opt/ros/noetic/setup.bash
export TURTLEBOT3_MODEL=burger
cd /home/noetic/raicom_nav_work/raicom_nav_ws
catkin_make
source devel/setup.bash
rospack profile
roslaunch raicom_nav task1_mapping.launch gui:=true
```

另开终端启动键盘控制：

```bash
source /opt/ros/noetic/setup.bash
export TURTLEBOT3_MODEL=burger
roslaunch turtlebot3_teleop turtlebot3_teleop_key.launch
```

控制小车沿四面墙环境走一圈，使 gmapping 生成完整地图。

保存任务一地图：

```bash
rosrun map_server map_saver -f /home/noetic/raicom_nav_work/raicom_nav_ws/src/raicom_nav/maps/task1_map
```

检查生成文件：

```bash
ls /home/noetic/raicom_nav_work/raicom_nav_ws/src/raicom_nav/maps/task1_map.*
```

应看到：

```text
task1_map.pgm
task1_map.yaml
```

任务一提交文件：

```text
第四部分/任务一/
├── task1_map.yaml
└── task1_map.pgm
```

## 5. 任务二：添加圆柱并自动保存地图

创建 launch 文件：

```bash
gedit /home/noetic/raicom_nav_work/raicom_nav_ws/src/raicom_nav/launch/task2_mapping_save.launch
```

写入：

```xml
<launch>
  <arg name="model" default="$(env TURTLEBOT3_MODEL)"/>
  <arg name="gui" default="true"/>
  <arg name="save_delay" default="60"/>
  <arg name="map_name" default="$(find raicom_nav)/maps/task2_cylinder_map"/>

  <include file="$(find gazebo_ros)/launch/empty_world.launch">
    <arg name="paused" value="false"/>
    <arg name="use_sim_time" value="true"/>
    <arg name="gui" value="$(arg gui)"/>
  </include>

  <param name="robot_description"
         command="$(find xacro)/xacro $(find turtlebot3_description)/urdf/turtlebot3_$(arg model).urdf.xacro"/>

  <node pkg="gazebo_ros" type="spawn_model" name="spawn_turtlebot3"
        args="-urdf -model turtlebot3_$(arg model) -x 0 -y 0 -z 0 -param robot_description"/>

  <node pkg="raicom_nav" type="spawn_arena.py" name="spawn_arena_cylinders"
        args="--mode cylinders" output="screen"/>

  <include file="$(find turtlebot3_slam)/launch/turtlebot3_slam.launch">
    <arg name="slam_methods" value="gmapping"/>
  </include>

  <node pkg="map_server" type="map_saver" name="task2_map_saver"
        args="-f $(arg map_name)"
        output="screen"
        launch-prefix="bash -c 'sleep $(arg save_delay); exec $0 $@'"/>
</launch>
```

运行：

```bash
killall gzserver gzclient
source /opt/ros/noetic/setup.bash
export TURTLEBOT3_MODEL=burger
cd /home/noetic/raicom_nav_work/raicom_nav_ws
catkin_make
source devel/setup.bash
rospack profile
roslaunch raicom_nav task2_mapping_save.launch gui:=true save_delay:=60
```

另开终端遥控小车绕场地走一圈：

```bash
source /opt/ros/noetic/setup.bash
export TURTLEBOT3_MODEL=burger
roslaunch turtlebot3_teleop turtlebot3_teleop_key.launch
```

等待 `save_delay` 时间后，launch 中的 `map_saver` 会自动保存地图。

检查地图：

```bash
ls /home/noetic/raicom_nav_work/raicom_nav_ws/src/raicom_nav/maps/task2_cylinder_map.*
```

应看到：

```text
task2_cylinder_map.pgm
task2_cylinder_map.yaml
```

截图保存：

```text
在 Gazebo 中显示三个圆柱物体后截图，保存为 task2_cylinders.jpg。
```

任务二提交文件：

```text
第四部分/任务二/
├── task2_cylinders.jpg
├── task2_mapping_save.launch
├── task2_cylinder_map.yaml
└── task2_cylinder_map.pgm
```

## 6. 任务三：导航写“足”字

任务三使用任务一保存的地图 `task1_map.yaml`，通过 `move_base` 发送多个导航目标点，使小车运动轨迹近似形成“足”字。

### 6.1 创建导航 launch

```bash
gedit /home/noetic/raicom_nav_work/raicom_nav_ws/src/raicom_nav/launch/task3_navigation.launch
```

写入：

```xml
<launch>
  <arg name="model" default="$(env TURTLEBOT3_MODEL)"/>
  <arg name="gui" default="true"/>
  <arg name="map_file" default="/home/noetic/raicom_nav_work/raicom_nav_ws/src/raicom_nav/maps/task1_map.yaml"/>

  <include file="$(find gazebo_ros)/launch/empty_world.launch">
    <arg name="paused" value="false"/>
    <arg name="use_sim_time" value="true"/>
    <arg name="gui" value="$(arg gui)"/>
  </include>

  <param name="robot_description"
         command="$(find xacro)/xacro $(find turtlebot3_description)/urdf/turtlebot3_$(arg model).urdf.xacro"/>

  <node pkg="gazebo_ros"
        type="spawn_model"
        name="spawn_turtlebot3"
        args="-urdf -model turtlebot3_$(arg model) -x 0 -y 0 -z 0 -param robot_description"/>

  <node pkg="raicom_nav"
        type="spawn_arena.py"
        name="spawn_arena_walls"
        args="--mode walls"
        output="screen"/>

  <include file="$(find turtlebot3_navigation)/launch/turtlebot3_navigation.launch">
    <arg name="map_file" value="$(arg map_file)"/>
  </include>
</launch>
```

启动导航环境：

```bash
killall gzserver gzclient
source /opt/ros/noetic/setup.bash
export TURTLEBOT3_MODEL=burger
cd /home/noetic/raicom_nav_work/raicom_nav_ws
catkin_make
source devel/setup.bash
rospack profile
roslaunch raicom_nav task3_navigation.launch gui:=true
```

在 RViz 中使用 `2D Pose Estimate` 设置小车初始位姿。

### 6.2 创建写“足”字脚本

```bash
gedit /home/noetic/raicom_nav_work/raicom_nav_ws/src/raicom_nav/scripts/write_zu_nav.py
```

写入：

```python
#!/usr/bin/env python3
import math

import actionlib
import rospy
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from geometry_msgs.msg import Quaternion
from tf.transformations import quaternion_from_euler


POINTS = [
    (-0.65,  1.15, 0.0),
    ( 0.65,  1.15, 0.0),
    ( 0.65,  0.60, -3.14),
    (-0.65,  0.60, -3.14),
    (-0.65,  1.15, 1.57),
    ( 0.00,  1.15, -1.57),
    ( 0.00,  0.00, -1.57),
    (-0.60, -1.10, -2.4),
    ( 0.00,  0.00, 0.0),
    ( 0.70, -1.10, -0.6),
]


def make_goal(x, y, yaw):
    goal = MoveBaseGoal()
    goal.target_pose.header.frame_id = "map"
    goal.target_pose.header.stamp = rospy.Time.now()
    goal.target_pose.pose.position.x = x
    goal.target_pose.pose.position.y = y
    goal.target_pose.pose.position.z = 0.0

    q = quaternion_from_euler(0.0, 0.0, yaw)
    goal.target_pose.pose.orientation = Quaternion(*q)
    return goal


def main():
    rospy.init_node("write_zu_nav")
    client = actionlib.SimpleActionClient("move_base", MoveBaseAction)

    rospy.loginfo("等待 move_base action server...")
    client.wait_for_server()
    rospy.loginfo("move_base 已连接，开始发送“足”字导航点。")

    for index, (x, y, yaw) in enumerate(POINTS, start=1):
        goal = make_goal(x, y, yaw)
        rospy.loginfo("发送第 %d 个目标点：x=%.2f y=%.2f yaw=%.2f", index, x, y, yaw)
        client.send_goal(goal)
        client.wait_for_result()
        rospy.sleep(0.5)

    rospy.loginfo("“足”字导航点执行完成。")


if __name__ == "__main__":
    main()
```

赋权：

```bash
chmod +x /home/noetic/raicom_nav_work/raicom_nav_ws/src/raicom_nav/scripts/write_zu_nav.py
```

运行写字脚本：

```bash
source /opt/ros/noetic/setup.bash
export TURTLEBOT3_MODEL=burger
cd /home/noetic/raicom_nav_work/raicom_nav_ws
catkin_make
source devel/setup.bash
rosrun raicom_nav write_zu_nav.py
```

录屏时需要在 RViz 中看到小车轨迹，轨迹整体呈现“足”字。

## 7. 录屏建议

第四部分三个任务建议分别录屏，单个视频不超过 5 分钟。

任务一视频展示：

```text
1. 启动四面墙 Gazebo 环境。
2. 启动 gmapping。
3. 遥控小车建图。
4. 使用 map_saver 保存地图。
5. 展示 task1_map.yaml 和 task1_map.pgm。
```

任务二视频展示：

```text
1. 启动 task2_mapping_save.launch。
2. Gazebo 中出现四面墙和三个圆柱。
3. 遥控小车建图。
4. launch 自动保存地图。
5. 展示截图、launch 文件、yaml 和 pgm。
```

任务三视频展示：

```text
1. 启动 task3_navigation.launch。
2. RViz 中加载任务一地图。
3. 设置 2D Pose Estimate。
4. 运行 write_zu_nav.py。
5. 小车按导航点运动。
6. RViz 中能看到“足”字轨迹。
```

所有视频左下角需要显示：

```text
学校名称 + 队伍名称 + 足式组
```

## 8. 复制到提交目录

创建提交目录：

```bash
mkdir -p ~/raicom_submit/学校名称_队伍名称_足式组/第四部分/任务一
mkdir -p ~/raicom_submit/学校名称_队伍名称_足式组/第四部分/任务二
mkdir -p ~/raicom_submit/学校名称_队伍名称_足式组/第四部分/任务三/视频
mkdir -p ~/raicom_submit/学校名称_队伍名称_足式组/文档与源码/第四部分源码/raicom_nav_ws/src
```

复制任务一地图：

```bash
cp /home/noetic/raicom_nav_work/raicom_nav_ws/src/raicom_nav/maps/task1_map.yaml \
  ~/raicom_submit/学校名称_队伍名称_足式组/第四部分/任务一/

cp /home/noetic/raicom_nav_work/raicom_nav_ws/src/raicom_nav/maps/task1_map.pgm \
  ~/raicom_submit/学校名称_队伍名称_足式组/第四部分/任务一/
```

复制任务二文件：

```bash
cp /home/noetic/raicom_nav_work/raicom_nav_ws/src/raicom_nav/launch/task2_mapping_save.launch \
  ~/raicom_submit/学校名称_队伍名称_足式组/第四部分/任务二/

cp /home/noetic/raicom_nav_work/raicom_nav_ws/src/raicom_nav/maps/task2_cylinder_map.yaml \
  ~/raicom_submit/学校名称_队伍名称_足式组/第四部分/任务二/

cp /home/noetic/raicom_nav_work/raicom_nav_ws/src/raicom_nav/maps/task2_cylinder_map.pgm \
  ~/raicom_submit/学校名称_队伍名称_足式组/第四部分/任务二/

cp /home/noetic/raicom_nav_work/raicom_nav_ws/src/raicom_nav/screenshots/task2_cylinders.jpg \
  ~/raicom_submit/学校名称_队伍名称_足式组/第四部分/任务二/
```

复制源码：

```bash
cp -a /home/noetic/raicom_nav_work/raicom_nav_ws/src/raicom_nav \
  ~/raicom_submit/学校名称_队伍名称_足式组/文档与源码/第四部分源码/raicom_nav_ws/src/
```

## 9. 最终提交结构

```text
学校名称_队伍名称_足式组/
├── 第四部分/
│   ├── 任务一/
│   │   ├── task1_map.yaml
│   │   └── task1_map.pgm
│   ├── 任务二/
│   │   ├── task2_cylinders.jpg
│   │   ├── task2_mapping_save.launch
│   │   ├── task2_cylinder_map.yaml
│   │   └── task2_cylinder_map.pgm
│   └── 任务三/
│       └── 视频/
│           └── 04_任务三_足字导航.mp4
└── 文档与源码/
    └── 第四部分源码/
        ├── README.md
        └── 源码/
            └── raicom_nav/
                    ├── package.xml
                    ├── launch/
                    ├── scripts/
                    ├── maps/
                    └── screenshots/
```

## 10. 提交前检查

- 任务一已生成 `task1_map.yaml` 和 `task1_map.pgm`。
- 任务二已生成 `task2_cylinder_map.yaml` 和 `task2_cylinder_map.pgm`。
- 任务二已提交 `task2_mapping_save.launch`。
- 任务二已提交三个圆柱的 Gazebo 截图。
- 任务三源码 `write_zu_nav.py` 可运行。
- RViz 中小车轨迹能形成“足”字。
- 视频左下角包含学校名称、队伍名称和足式组。
- 单个视频不超过 5 分钟。
- 视频没有加速。
```



