#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

import rospy
from package_query.srv import QueryPackage


def call_service(query_package, item):
    response = query_package(item)

    print("-" * 30)
    print("客户端发送物品：{}".format(item))
    if response.success:
        print("查询成功")
        print("服务端返回类别：{}".format(response.category))
        print("输出结果：{}".format(response.message))
    else:
        print("查询失败")
        print("服务端返回信息：{}".format(response.message))
    print("-" * 30)


def main():
    rospy.init_node("package_query_client")

    try:
        rospy.wait_for_service("query_package", timeout=5.0)
    except rospy.ROSException:
        print("错误：无法连接到服务端，请确认 package_server.py 已经运行。")
        sys.exit(1)

    try:
        query_package = rospy.ServiceProxy("query_package", QueryPackage)

        if len(sys.argv) > 1:
            print("【模式：命令行传参】")
            call_service(query_package, sys.argv[1])
        else:
            print("【模式：交互式查询】")
            print("提示：输入物品名称进行查询，输入 q 或 Ctrl+C 退出。")
            while not rospy.is_shutdown():
                item = input("\n请输入要查询的物品：").strip()
                if item.lower() == "q":
                    print("退出查询程序。")
                    break
                if item:
                    call_service(query_package, item)

    except rospy.ServiceException as exc:
        print("服务调用失败：{}".format(exc))


if __name__ == "__main__":
    main()
