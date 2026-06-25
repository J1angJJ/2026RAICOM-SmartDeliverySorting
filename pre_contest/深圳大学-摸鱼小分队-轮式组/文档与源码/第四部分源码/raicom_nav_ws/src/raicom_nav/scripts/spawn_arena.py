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

    for name in ["north_wall", "south_wall", "east_wall", "west_wall", "cylinder_1", "cylinder_2", "cylinder_3"]:
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
