#!/usr/bin/env python3
import argparse
import math
import rospy
import actionlib
from geometry_msgs.msg import Point, PoseStamped, PoseWithCovarianceStamped
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from nav_msgs.msg import Odometry, Path
from visualization_msgs.msg import Marker


POINTS = [
    (-0.55,  1.20, 0.0),
    ( 0.55,  1.20, 0.0),
    ( 0.55,  0.75, -math.pi),
    (-0.55,  0.75, -math.pi),
    (-0.55,  1.20, math.pi / 2),
    ( 0.00,  0.95, -math.pi / 2),
    ( 0.00,  0.35, -math.pi / 2),
    (-0.65,  0.35, 0.0),
    ( 0.65,  0.35, 0.0),
    ( 0.00,  0.35, -math.pi / 2),
    ( 0.00, -0.55, -math.pi / 2),
    (-0.55, -1.15, -2.35),
    ( 0.00, -0.55, -0.65),
    ( 0.80, -1.15, -0.45),
]


STROKES = [
    [(-0.55, 1.20), (0.55, 1.20), (0.55, 0.75), (-0.55, 0.75), (-0.55, 1.20)],
    [(0.00, 0.95), (0.00, 0.35)],
    [(-0.65, 0.35), (0.65, 0.35)],
    [(0.00, 0.35), (0.00, -0.55)],
    [(0.00, -0.55), (-0.55, -1.15)],
    [(0.00, -0.55), (0.80, -1.15)],
]


actual_path = Path()
actual_path.header.frame_id = "odom"
actual_path_pub = None


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


def make_initial_pose():
    pose = PoseWithCovarianceStamped()
    pose.header.frame_id = "map"
    pose.pose.pose.position.x = 0.0
    pose.pose.pose.position.y = 0.0
    pose.pose.pose.position.z = 0.0
    pose.pose.pose.orientation.w = 1.0
    pose.pose.covariance[0] = 0.25
    pose.pose.covariance[7] = 0.25
    pose.pose.covariance[35] = 0.0685
    return pose


def build_reference_path():
    path = Path()
    path.header.frame_id = "map"
    path.header.stamp = rospy.Time.now()

    for x, y, yaw in POINTS:
        pose = PoseStamped()
        pose.header = path.header
        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.position.z = 0.0
        qz, qw = yaw_to_quaternion(yaw)
        pose.pose.orientation.z = qz
        pose.pose.orientation.w = qw
        path.poses.append(pose)

    return path


def build_reference_marker():
    marker = Marker()
    marker.header.frame_id = "map"
    marker.header.stamp = rospy.Time.now()
    marker.ns = "zu_reference"
    marker.id = 1
    marker.type = Marker.LINE_LIST
    marker.action = Marker.ADD
    marker.scale.x = 0.06
    marker.color.r = 1.0
    marker.color.g = 0.2
    marker.color.b = 0.05
    marker.color.a = 1.0
    marker.pose.orientation.w = 1.0

    for stroke in STROKES:
        for start, end in zip(stroke, stroke[1:]):
            for x, y in (start, end):
                point = Point()
                point.x = x
                point.y = y
                point.z = 0.05
                marker.points.append(point)

    return marker


def odom_callback(msg):
    global actual_path

    pose = PoseStamped()
    pose.header = msg.header
    pose.pose = msg.pose.pose
    actual_path.header.stamp = rospy.Time.now()
    actual_path.poses.append(pose)

    if len(actual_path.poses) > 3000:
        actual_path.poses = actual_path.poses[-3000:]

    if actual_path_pub is not None:
        actual_path_pub.publish(actual_path)


def main():
    global actual_path_pub

    parser = argparse.ArgumentParser()
    parser.add_argument("--start-delay", type=float, default=0.0)
    parser.add_argument("--set-initial-pose", action="store_true")
    args, _ = parser.parse_known_args()

    rospy.init_node("write_zu_nav")
    client = actionlib.SimpleActionClient("move_base", MoveBaseAction)
    initial_pose_pub = rospy.Publisher(
        "initialpose", PoseWithCovarianceStamped, queue_size=1
    )
    reference_path_pub = rospy.Publisher(
        "zu_reference_path", Path, queue_size=1, latch=True
    )
    reference_marker_pub = rospy.Publisher(
        "zu_reference_marker", Marker, queue_size=1, latch=True
    )
    actual_path_pub = rospy.Publisher("zu_actual_path", Path, queue_size=1)
    rospy.Subscriber("odom", Odometry, odom_callback, queue_size=20)

    if args.start_delay > 0:
        rospy.loginfo("等待 %.1f 秒，让 Gazebo、AMCL、RViz 稳定。", args.start_delay)
        rospy.sleep(args.start_delay)

    rospy.sleep(1.0)
    reference_path_pub.publish(build_reference_path())
    reference_marker_pub.publish(build_reference_marker())

    if args.set_initial_pose:
        rospy.loginfo("发布初始位姿到 /initialpose。")
        for _ in range(10):
            pose = make_initial_pose()
            pose.header.stamp = rospy.Time.now()
            initial_pose_pub.publish(pose)
            rospy.sleep(0.2)

    rospy.loginfo("等待 move_base...")
    client.wait_for_server()
    rospy.loginfo("move_base 已连接，开始执行足字轨迹。")

    for i, (x, y, yaw) in enumerate(POINTS, start=1):
        reference_path_pub.publish(build_reference_path())
        reference_marker_pub.publish(build_reference_marker())
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

    reference_path_pub.publish(build_reference_path())
    reference_marker_pub.publish(build_reference_marker())
    actual_path_pub.publish(actual_path)
    rospy.loginfo("足字轨迹执行完成。")


if __name__ == "__main__":
    main()
