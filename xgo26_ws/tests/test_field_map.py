from __future__ import annotations

import unittest

from xgo26.field_map import load_field_map


class FieldMapTest(unittest.TestCase):
    def setUp(self) -> None:
        self.field_map = load_field_map()

    def test_canvas_corners_match_physical_field(self) -> None:
        top_left = self.field_map.pixel_to_field(0, 0)
        bottom_right = self.field_map.pixel_to_field(8504, 7087)
        self.assertAlmostEqual(top_left.x, 0.0)
        self.assertAlmostEqual(top_left.y, 2.5)
        self.assertAlmostEqual(bottom_right.x, 3.0)
        self.assertAlmostEqual(bottom_right.y, 0.0)

    def test_cubes_are_centered_in_recognition_zones(self) -> None:
        for index in (1, 2):
            cube = self.field_map.cube(f"recognition_cube_{index}")
            zone = self.field_map.data["recognition_zones"][f"recognition_{index}"]
            self.assertAlmostEqual(cube.center.x, zone["center"][0], places=6)
            self.assertAlmostEqual(cube.center.y, zone["center"][1], places=6)
            self.assertAlmostEqual(cube.width, 0.3)
            self.assertAlmostEqual(cube.depth, 0.3)
            self.assertAlmostEqual(cube.height, 0.3)

    def test_drop_targets_keep_source_order(self) -> None:
        centers = [self.field_map.drop_target(letter)[0] for letter in "ABCD"]
        self.assertTrue(all(left.x < right.x for left, right in zip(centers, centers[1:])))
        self.assertTrue(all(abs(point.y - centers[0].y) < 1e-6 for point in centers))


if __name__ == "__main__":
    unittest.main()
