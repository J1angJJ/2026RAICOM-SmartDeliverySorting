# 第二部分：ROS Service 包裹类别查询复现步骤

本文档用于在 Ubuntu + ROS 环境中复现第二部分“ROS 程序题”。本任务使用 ROS Service 实现服务端与客户端通信：客户端发送物品名称，服务端返回对应包裹类别。

## 1. 任务目标

第二部分共 15 分：

| 任务 | 内容 | 分值 |
| --- | --- | --- |
| 任务一 | 编写服务端，使用 `rosservice call` 能看到正确输出 | 5 分 |
| 任务二 | 编写客户端，传入参数并输出服务返回结果 | 10 分 |

## 2. 工作空间路径

本项目第二部分工作空间为：

```bash
~/raicom_submit/学校名称_队伍名称_轮式组/文档与源码/第二部分源码/package_query_ws
```

## 3. 创建工作空间和功能包

```bash
source /opt/ros/noetic/setup.bash
mkdir -p ~/raicom_submit/学校名称_队伍名称_轮式组/文档与源码/第二部分源码/package_query_ws/src
cd ~/raicom_submit/学校名称_队伍名称_轮式组/文档与源码/第二部分源码/package_query_ws/src
catkin_create_pkg package_query rospy std_msgs message_generation
```

进入功能包：

```bash
cd ~/raicom_submit/学校名称_队伍名称_轮式组/文档与源码/第二部分源码/package_query_ws/src/package_query
mkdir -p srv scripts
```

## 4. 创建自定义 Service 文件

新建：

```bash
gedit srv/QueryPackage.srv
```

写入：

```srv
string item
---
string category
string message
bool success
```

字段含义：

```text
item：客户端发送的物品名称
category：服务端返回的包裹类别
message：中文提示信息
success：是否查询成功
```

## 5. 修改 package.xml

打开：

```bash
gedit package.xml
```

确认包含以下依赖，没有就补上：

```xml
<build_depend>message_generation</build_depend>
<build_depend>std_msgs</build_depend>
<build_depend>rospy</build_depend>

<exec_depend>message_runtime</exec_depend>
<exec_depend>std_msgs</exec_depend>
<exec_depend>rospy</exec_depend>
```

## 6. 修改 CMakeLists.txt

打开：

```bash
gedit CMakeLists.txt
```

找到 `find_package`，修改为：

```cmake
find_package(catkin REQUIRED COMPONENTS
  rospy
  std_msgs
  message_generation
)
```

添加 Service 文件：

```cmake
add_service_files(
  FILES
  QueryPackage.srv
)
```

添加消息生成：

```cmake
generate_messages(
  DEPENDENCIES
  std_msgs
)
```

修改 `catkin_package`：

```cmake
catkin_package(
  CATKIN_DEPENDS rospy std_msgs message_runtime
)
```

注意：`add_service_files` 和 `generate_messages` 要放在 `catkin_package` 前面。

## 7. 编写服务端节点

新建：

```bash
gedit scripts/package_server.py
```

写入：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rospy
from package_query.srv import QueryPackage, QueryPackageResponse

PACKAGE_DATABASE = {
    "衣服": "日用品",
    "牙刷": "日用品",
    "卫生纸": "日用品",
    "香蕉": "水果",
    "苹果": "水果",
    "橘子": "水果",
    "电视机": "家电",
    "冰箱": "家电",
    "空调": "家电",
}

def handle_query(req):
    item = req.item.strip()

    if item in PACKAGE_DATABASE:
        category = PACKAGE_DATABASE[item]
        message = "物品：{}，包裹类别：{}".format(item, category)
        rospy.loginfo(message)
        return QueryPackageResponse(category, message, True)

    message = "未查询到物品：{}".format(item)
    rospy.logwarn(message)
    return QueryPackageResponse("未知", message, False)

def main():
    rospy.init_node("package_query_server")
    rospy.Service("query_package", QueryPackage, handle_query)
    rospy.loginfo("包裹类别查询服务已启动，服务名：/query_package")
    rospy.spin()

if __name__ == "__main__":
    main()
```

赋予执行权限：

```bash
chmod +x scripts/package_server.py
```

## 8. 编写客户端节点

新建：

```bash
gedit scripts/package_client.py
```

写入：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import rospy
from package_query.srv import QueryPackage

def main():
    rospy.init_node("package_query_client")

    if len(sys.argv) < 2:
        print("用法：rosrun package_query package_client.py 物品名称")
        print("示例：rosrun package_query package_client.py 卫生纸")
        return

    item = sys.argv[1]
    rospy.wait_for_service("query_package")

    try:
        query_package = rospy.ServiceProxy("query_package", QueryPackage)
        response = query_package(item)

        if response.success:
            print("查询成功")
            print("客户端发送物品：{}".format(item))
            print("服务端返回类别：{}".format(response.category))
            print("输出结果：{}".format(response.message))
        else:
            print("查询失败")
            print("客户端发送物品：{}".format(item))
            print("服务端返回信息：{}".format(response.message))

    except rospy.ServiceException as e:
        print("服务调用失败：{}".format(e))

if __name__ == "__main__":
    main()
```

赋予执行权限：

```bash
chmod +x scripts/package_client.py
```

## 9. 编译工作空间

回到工作空间根目录：

```bash
cd ~/raicom_submit/学校名称_队伍名称_轮式组/文档与源码/第二部分源码/package_query_ws
catkin_make
```

加载环境：

```bash
source devel/setup.bash
```

可选：写入 `.bashrc`：

```bash
echo "source ~/raicom_submit/学校名称_队伍名称_轮式组/文档与源码/第二部分源码/package_query_ws/devel/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

## 10. 启动服务端

第一个终端：

```bash
roscore
```

第二个终端：

```bash
source ~/raicom_submit/学校名称_队伍名称_轮式组/文档与源码/第二部分源码/package_query_ws/devel/setup.bash
rosrun package_query package_server.py
```

看到以下内容说明服务端启动成功：

```text
包裹类别查询服务已启动，服务名：/query_package
```

## 11. 使用 rosservice call 测试任务一

第三个终端：

```bash
source ~/raicom_submit/学校名称_队伍名称_轮式组/文档与源码/第二部分源码/package_query_ws/devel/setup.bash
rosservice list
```

应看到：

```text
/query_package
```

调用服务：

```bash
rosservice call /query_package "item: '卫生纸'"
```

正确输出示例：

```yaml
category: "日用品"
message: "物品：卫生纸，包裹类别：日用品"
success: True
```

继续测试：

```bash
rosservice call /query_package "item: '香蕉'"
rosservice call /query_package "item: '电视机'"
rosservice call /query_package "item: '空调'"
```

## 12. 运行客户端测试任务二

服务端保持运行，第三个终端执行：

```bash
source ~/raicom_submit/学校名称_队伍名称_轮式组/文档与源码/第二部分源码/package_query_ws/devel/setup.bash
rosrun package_query package_client.py 卫生纸
```

正确输出示例：

```text
查询成功
客户端发送物品：卫生纸
服务端返回类别：日用品
输出结果：物品：卫生纸，包裹类别：日用品
```

继续测试：

```bash
rosrun package_query package_client.py 香蕉
rosrun package_query package_client.py 苹果
rosrun package_query package_client.py 电视机
rosrun package_query package_client.py 冰箱
rosrun package_query package_client.py 空调
```

## 13. 录屏建议

录屏时建议按以下顺序演示：

```text
1. 打开终端，进入第二部分工作空间。
2. 执行 catkin_make，展示可以正常编译。
3. source devel/setup.bash。
4. 启动 roscore。
5. 启动服务端 package_server.py。
6. 使用 rosservice call /query_package 测试卫生纸、香蕉、电视机。
7. 使用客户端 package_client.py 测试苹果、冰箱、空调。
8. 展示终端中文输出。
```

视频重点需要出现：

```text
1. rosservice call 正确返回数据。
2. 客户端可以传入物品参数。
3. 客户端终端按格式输出服务端返回结果。
4. 视频左下角显示：学校名称 + 队伍名称 + 轮式组。
5. 录屏不超过 5 分钟，不加速。
```

## 14. 第二部分提交结构

```text
学校名称_队伍名称_轮式组/
├── 第二部分/
│   ├── 任务一/
│   │   └── 视频/
│   └── 任务二/
│       └── 视频/
└── 文档与源码/
    └── 第二部分源码/
        ├── README.md
        └── package_query_ws/
            └── src/
                └── package_query/
                    ├── CMakeLists.txt
                    ├── package.xml
                    ├── srv/
                    │   └── QueryPackage.srv
                    └── scripts/
                        ├── package_server.py
                        └── package_client.py
```

## 15. 提交前检查

- `catkin_make` 可以正常编译。
- `/query_package` 服务可以正常启动。
- `rosservice call` 能返回正确类别。
- 客户端可以接收命令行参数。
- 客户端中文输出格式清晰。
- 视频中能看到服务端、客户端和测试结果。
- 录屏不超过 5 分钟，且没有加速。


