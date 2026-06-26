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
