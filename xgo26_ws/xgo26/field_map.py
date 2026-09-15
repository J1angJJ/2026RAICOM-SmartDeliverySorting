from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .config import resolve_path


@dataclass(frozen=True)
class Point2:
    x: float
    y: float


@dataclass(frozen=True)
class CubeLandmark:
    name: str
    center: Point2
    width: float
    depth: float
    height: float
    yaw_deg: float | None
    placement_uncertainty_m: float


class FieldMap:
    def __init__(self, data: dict[str, Any]):
        self.data = data
        self.width = float(data["field"]["width"])
        self.height = float(data["field"]["height"])
        source = data["source_image"]
        self.canvas_width_px = int(source["canvas_pixels"][0])
        self.canvas_height_px = int(source["canvas_pixels"][1])
        self.pixels_per_meter_x = float(source["pixels_per_meter"][0])
        self.pixels_per_meter_y = float(source["pixels_per_meter"][1])

    def pixel_to_field(self, pixel_x: float, pixel_y: float) -> Point2:
        return Point2(
            x=pixel_x / self.pixels_per_meter_x,
            y=self.height - pixel_y / self.pixels_per_meter_y,
        )

    def field_to_pixel(self, x: float, y: float) -> Point2:
        return Point2(
            x=x * self.pixels_per_meter_x,
            y=(self.height - y) * self.pixels_per_meter_y,
        )

    def cube(self, name: str) -> CubeLandmark:
        raw = self.data["landmarks"][name]
        center = raw["center"]
        size = raw["size"]
        yaw = raw.get("yaw_deg")
        return CubeLandmark(
            name=name,
            center=Point2(float(center[0]), float(center[1])),
            width=float(size[0]),
            depth=float(size[1]),
            height=float(size[2]),
            yaw_deg=None if yaw is None else float(yaw),
            placement_uncertainty_m=float(
                self.data.get("uncertainty", {}).get("cube_placement", 0.0)
            ),
        )

    def line_route(self) -> tuple[Point2, ...]:
        return tuple(Point2(float(x), float(y)) for x, y in self.data["line_route"]["points"])

    def drop_target(self, letter: str) -> tuple[Point2, float]:
        raw = self.data["drop_zone"]["targets"][letter.upper()]
        return Point2(float(raw["center"][0]), float(raw["center"][1])), float(
            raw["radius"]
        )


def load_field_map(path: str | Path = "maps/field_map.json") -> FieldMap:
    resolved = resolve_path(path)
    with resolved.open("r", encoding="utf-8") as file:
        return FieldMap(json.load(file))
