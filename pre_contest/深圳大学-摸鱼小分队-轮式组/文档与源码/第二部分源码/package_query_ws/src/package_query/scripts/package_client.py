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

    except rospy.ServiceException as exc:
        print("服务调用失败：{}".format(exc))


if __name__ == "__main__":
    main()
