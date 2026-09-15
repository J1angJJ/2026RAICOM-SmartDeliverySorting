from __future__ import annotations

import math
import unittest

from xgo26.lidar import CubeLandmarkEstimator, LidarPoint, LidarScan


class CubeLandmarkEstimatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = {
            "front_half_width_deg": 40,
            "min_range_m": 0.08,
            "localization_max_range_m": 2.5,
            "minimum_face_points": 8,
            "face_residual_limit_m": 0.025,
            "maximum_face_rmse_m": 0.02,
            "cube_face_width_m": 0.30,
            "cube_face_width_tolerance_m": 0.08,
            "cluster_gap_m": 0.08,
            "cluster_depth_jump_m": 0.12,
            "sensor_forward_offset_m": 0.10,
        }

    def test_selects_cube_face_in_front_of_long_boundary(self) -> None:
        slope = math.tan(math.radians(10))
        points = []
        for index in range(31):
            y = -0.05 + index * 0.01
            x = 0.8 + slope * y + (0.002 if index % 2 else -0.002)
            points.append(
                LidarPoint(
                    angle_rad=math.atan2(y, x),
                    range_m=math.hypot(x, y),
                    intensity=100,
                )
            )
        for y in [(-0.9 + index * 0.05) for index in range(11)]:
            x = 1.5
            points.append(LidarPoint(math.atan2(y, x), math.hypot(x, y), 100))
        for y in [(0.6 + index * 0.05) for index in range(11)]:
            x = 1.5
            points.append(LidarPoint(math.atan2(y, x), math.hypot(x, y), 100))

        estimate = CubeLandmarkEstimator(self.config).estimate(
            LidarScan(tuple(points), captured_at=0.0, scan_frequency_hz=10.0)
        )

        self.assertTrue(estimate.valid)
        self.assertAlmostEqual(estimate.sensor_distance_m, 0.8, delta=0.01)
        self.assertAlmostEqual(estimate.robot_distance_m, 0.9, delta=0.01)
        self.assertAlmostEqual(estimate.yaw_deg, 10.0, delta=0.5)
        self.assertAlmostEqual(estimate.face_width_m, 0.3, delta=0.02)
        self.assertGreater(estimate.confidence, 0.8)

    def test_rejects_too_few_points(self) -> None:
        scan = LidarScan(
            tuple(LidarPoint(math.radians(angle), 0.8, 100) for angle in (-5, 0, 5)),
            captured_at=0.0,
        )
        estimate = CubeLandmarkEstimator(self.config).estimate(scan)
        self.assertFalse(estimate.valid)
        self.assertEqual(estimate.reason, "前向有效点不足")

    def test_rejects_long_boundary_without_cube(self) -> None:
        points = []
        for index in range(41):
            y = -0.8 + index * 0.04
            x = 1.2
            points.append(
                LidarPoint(
                    angle_rad=math.atan2(y, x),
                    range_m=math.hypot(x, y),
                    intensity=100,
                )
            )
        estimate = CubeLandmarkEstimator(self.config).estimate(
            LidarScan(tuple(points), captured_at=0.0)
        )
        self.assertFalse(estimate.valid)
        self.assertIn("30cm", estimate.reason)


if __name__ == "__main__":
    unittest.main()
