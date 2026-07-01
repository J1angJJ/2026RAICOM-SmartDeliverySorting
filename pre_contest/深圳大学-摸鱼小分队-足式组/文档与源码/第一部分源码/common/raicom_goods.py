from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GoodsClass:
    id: int
    name: str
    item_cn: str
    package_cn: str


GOODS_CLASSES: tuple[GoodsClass, ...] = (
    GoodsClass(0, "tv", "电视机", "家电"),
    GoodsClass(1, "air_conditioner", "空调", "家电"),
    GoodsClass(2, "fridge", "冰箱", "家电"),
    GoodsClass(3, "paper", "卫生纸", "日用品"),
    GoodsClass(4, "clothes", "衣服", "日用品"),
    GoodsClass(5, "toothbrush", "牙刷", "日用品"),
    GoodsClass(6, "banana", "香蕉", "水果"),
    GoodsClass(7, "orange", "橘子", "水果"),
    GoodsClass(8, "apple", "苹果", "水果"),
)

CLASS_NAMES = [item.name for item in GOODS_CLASSES]
CLASS_NAME_TO_ID = {item.name: item.id for item in GOODS_CLASSES}
CLASS_INFO = {item.name: (item.item_cn, item.package_cn) for item in GOODS_CLASSES}


def format_detection(class_name: str) -> str:
    item_cn, package_cn = CLASS_INFO.get(class_name, (class_name, "未知类别"))
    return f"图中包裹是{item_cn}，类别为{package_cn}。"


def yolo_names_yaml() -> str:
    lines = ["names:"]
    for item in GOODS_CLASSES:
        lines.append(f"  {item.id}: {item.name}")
    return "\n".join(lines) + "\n"
