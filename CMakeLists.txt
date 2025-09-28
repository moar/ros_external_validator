cmake_minimum_required(VERSION 3.0.2)
project(ulises_test_utils)

find_package(catkin REQUIRED COMPONENTS
  rospy
)
catkin_python_setup()
catkin_add_nosetests(test)