from __future__ import annotations

import math
import unittest

from xgo26.lidar import FrontWallEstimator, LidarPoint, LidarScan


class FrontWallEstimatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = {
            "front_half_width_deg": 40,
            "min_range_m": 0.08,
            "localization_max_range_m": 2.5,
            "minimum_wall_points": 8,
            "minimum_wall_span_m": 0.12,
            "wall_residual_limit_m": 0.025,
            "maximum_wall_rmse_m": 0.02,
            "surface_depth_window_m": 0.12,
            "sensor_forward_offset_m": 0.10,
        }

    def test_estimates_wall_with_outliers(self) -> None:
        slope = math.tan(math.radians(10))
        points = []
        for index in range(41):
            y = -0.4 + index * 0.02
            x = 0.8 + slope * y + (0.002 if index % 2 else -0.002)
            points.append(
                LidarPoint(
                    angle_rad=math.atan2(y, x),
                    range_m=math.hypot(x, y),
                    intensity=100,
                )
            )
        for angle_deg, distance in ((-30, 1.8), (-10, 1.6), (15, 2.0), (32, 1.7)):
            points.append(LidarPoint(math.radians(angle_deg), distance, 100))

        estimate = FrontWallEstimator(self.config).estimate(
            LidarScan(tuple(points), captured_at=0.0, scan_frequency_hz=10.0)
        )

        self.assertTrue(estimate.valid)
        self.assertAlmostEqual(estimate.sensor_distance_m, 0.8, delta=0.01)
        self.assertAlmostEqual(estimate.robot_distance_m, 0.9, delta=0.01)
        self.assertAlmostEqual(estimate.yaw_deg, 10.0, delta=0.5)
        self.assertGreater(estimate.confidence, 0.8)

    def test_rejects_too_few_points(self) -> None:
        scan = LidarScan(
            tuple(LidarPoint(math.radians(angle), 0.8, 100) for angle in (-5, 0, 5)),
            captured_at=0.0,
        )
        estimate = FrontWallEstimator(self.config).estimate(scan)
        self.assertFalse(estimate.valid)
        self.assertEqual(estimate.reason, "前向有效点不足")


if __name__ == "__main__":
    unittest.main()
