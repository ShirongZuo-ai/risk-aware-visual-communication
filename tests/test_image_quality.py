import math
import unittest

import numpy as np

from evaluation.image_quality import (
    UndefinedMetricError,
    compute_error_metrics,
    compute_masked_error_metrics,
    compute_mse,
    compute_risk_weighted_metrics,
    compute_ssim,
    psnr_from_mse,
)


def image(value=0):
    return np.full((12, 12, 3), value, dtype=np.uint8)


class ImageQualityTests(unittest.TestCase):
    def test_identical_images_have_zero_mse_and_infinite_psnr(self):
        metrics = compute_error_metrics(image(20), image(20))
        self.assertEqual(metrics.mse, 0.0)
        self.assertTrue(math.isinf(metrics.psnr_db))
        self.assertEqual(compute_ssim(image(20), image(20)), 1.0)

    def test_known_mse_psnr_and_rgb_aggregation(self):
        source = image(0)
        reconstructed = image(0)
        reconstructed[0, 0] = (3, 4, 5)
        self.assertAlmostEqual(compute_mse(source, reconstructed), (9 + 16 + 25) / (12 * 12 * 3))
        self.assertAlmostEqual(psnr_from_mse(1.0), 10 * math.log10(255 * 255))

    def test_uint8_overflow_is_prevented(self):
        self.assertEqual(compute_mse(image(0), image(255)), 255.0 * 255.0)

    def test_ssim_degraded_and_shape_mode_validation(self):
        degraded = image(0)
        degraded[0:6] = 255
        self.assertLess(compute_ssim(image(0), degraded), 1.0)
        with self.assertRaises(ValueError):
            compute_mse(image(), np.zeros((12, 12), dtype=np.uint8))
        with self.assertRaises(ValueError):
            compute_mse(image(), np.zeros((11, 12, 3), dtype=np.uint8))

    def test_risk_weighted_metrics_use_continuous_weights(self):
        source = image(0)
        reconstructed = image(0)
        reconstructed[0, 0] = (10, 10, 10)
        weights = [0.0] * 144
        weights[0] = 0.25
        metrics, risk_sum = compute_risk_weighted_metrics(source, reconstructed, weights)
        self.assertEqual(risk_sum, 0.25)
        self.assertEqual(metrics.mse, 100.0)
        self.assertAlmostEqual(metrics.psnr_db, psnr_from_mse(100.0))

    def test_risk_weighted_empty_and_zero_error_are_explicit(self):
        with self.assertRaises(UndefinedMetricError):
            compute_risk_weighted_metrics(image(), image(), [0.0] * 144)
        metrics, _ = compute_risk_weighted_metrics(image(), image(), [0.1] * 144)
        self.assertEqual(metrics.mse, 0.0)
        self.assertTrue(math.isinf(metrics.psnr_db))

    def test_masked_metrics_reject_empty_region(self):
        with self.assertRaises(UndefinedMetricError):
            compute_masked_error_metrics(image(), image(), [False] * 144)
        metrics = compute_masked_error_metrics(image(), image(10), [True] + [False] * 143)
        self.assertEqual(metrics.mse, 100.0)


if __name__ == "__main__":
    unittest.main()
