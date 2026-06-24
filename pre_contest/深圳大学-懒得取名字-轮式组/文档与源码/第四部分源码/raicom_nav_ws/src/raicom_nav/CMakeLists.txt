cmake_minimum_required(VERSION 3.0.2)
project(raicom_nav)

find_package(catkin REQUIRED COMPONENTS
  actionlib
  gazebo_msgs
  geometry_msgs
  move_base_msgs
  nav_msgs
  rospy
)

catkin_package()

catkin_install_python(PROGRAMS
  scripts/spawn_arena.py
  scripts/write_zu_nav.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

install(DIRECTORY launch maps
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}
)
