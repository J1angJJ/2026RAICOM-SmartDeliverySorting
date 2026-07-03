#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import math
import rospy
import actionlib
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from nav_msgs.msg import Path, Odometry
from geometry_msgs.msg import PoseStamped

path_msg = Path()
path_pub = None

# 监听小车轮子的实时位置（里程计），并画到 Path 里
def odom_callback(data):
    global path_msg, path_pub
    if path_pub is None:
        return

    # 提取当前坐标点
    pose = PoseStamped()
    pose.header = data.header
    pose.pose = data.pose.pose

    # 把坐标点加到轨迹上并发布出去
    path_msg.header = data.header
    path_msg.poses.append(pose)
    path_pub.publish(path_msg)

def yaw_to_quaternion(yaw):
    qz = math.sin(yaw / 2.0)
    qw = math.cos(yaw / 2.0)
    return qz, qw

def make_goal(x, y, yaw):
    goal = MoveBaseGoal()
    goal.target_pose.header.frame_id = "map"
    goal.target_pose.header.stamp = rospy.Time.now()
    goal.target_pose.pose.position.x = x
    goal.target_pose.pose.position.y = y
    goal.target_pose.pose.position.z = 0.0
    qz, qw = yaw_to_quaternion(yaw)
    goal.target_pose.pose.orientation.z = qz
    goal.target_pose.pose.orientation.w = qw
    return goal

def main():
    global path_pub
    rospy.init_node("write_zu_nav")

    # 【新增的核心功能】：注册发布者，向 /zu_actual_path 广播画线轨迹
    path_pub = rospy.Publisher('/zu_actual_path', Path, queue_size=10)
    # 监听 /odom，实时获取小车位置
    rospy.Subscriber('/odom', Odometry, odom_callback)

    client = actionlib.SimpleActionClient("move_base", MoveBaseAction)
    rospy.loginfo("等待 move_base...")
    client.wait_for_server()
    rospy.loginfo("move_base 已连接，开始执行足字轨迹。")

    # 完美版“足”字坐标
    POINTS = [
        # --- 1. 画顶部的“口” ---
        ( 0.00,  0.70,  0.00),
        ( 0.25,  0.70,  1.57),
        ( 0.25,  1.10,  3.14),
        (-0.25,  1.10, -1.57),
        (-0.25,  0.70,  0.00),
        ( 0.00,  0.70, -1.57),

        # --- 2. 画主线 -> 画【绝对笔直】的单边短横 ---
        ( 0.00,  0.40,  0.00),
        ( 0.35,  0.40,  3.14),
        ( 0.00,  0.40, -1.57),

        # --- 3. 补全主线底部，并逆向走到绿色长弧线的起点 ---
        ( 0.00, -0.30,  2.82),
        (-0.30, -0.20,  1.89),
        (-0.40,  0.10, -1.25),

        # --- 4. 顺滑地画出“绿色大弧线” ---
        (-0.30, -0.20, -0.32),
        ( 0.00, -0.30, -0.17),
        ( 0.60, -0.40,  0.00),
    ]

    for i, (x, y, yaw) in enumerate(POINTS, start=1):
        rospy.loginfo("发送目标点 %d: x=%.2f, y=%.2f", i, x, y)
        goal = make_goal(x, y, yaw)
        client.send_goal(goal)

        finished = client.wait_for_result(rospy.Duration(90))
        if not finished:
            rospy.logwarn("目标点 %d 超时，取消该目标。", i)
            client.cancel_goal()
        else:
            rospy.loginfo("目标点 %d 完成。", i)

        rospy.sleep(0.5)

    rospy.loginfo("足字轨迹执行完成。")

if __name__ == "__main__":
    main()