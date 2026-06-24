#!/usr/bin/env python3
import math
import rospy
import actionlib
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal


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
    rospy.init_node("write_zu_nav")
    client = actionlib.SimpleActionClient("move_base", MoveBaseAction)

    rospy.loginfo("等待 move_base...")
    client.wait_for_server()
    rospy.loginfo("move_base 已连接，开始执行足字轨迹。")

    points = [
        (-0.65,  1.15, 0.0),
        ( 0.65,  1.15, 0.0),
        ( 0.65,  0.60, -math.pi),
        (-0.65,  0.60, -math.pi),
        (-0.65,  1.15, math.pi / 2),
        ( 0.00,  1.15, -math.pi / 2),
        ( 0.00,  0.00, -math.pi / 2),
        (-0.60, -1.10, -2.4),
        ( 0.00,  0.00, 0.0),
        ( 0.70, -1.10, -0.6),
    ]

    for i, (x, y, yaw) in enumerate(points, start=1):
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
