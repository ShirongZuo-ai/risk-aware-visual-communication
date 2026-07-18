"""Fixed RGB image-quality metrics for Milestone 5D evaluation only."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np
from skimage.metrics import structural_similarity


DATA_RANGE = 255.0
SSIM_PARAMETERS = {
    "data_range": 255,
    "channel_axis": -1,
    "gaussian_weights": True,
    "sigma": 1.5,
    "use_sample_covariance": False,
    "win_size": 11,
}


class UndefinedMetricError(ValueError):
    """Raised when a metric's declared denominator is zero."""


@dataclass(frozen=True)
class ErrorMetrics:
    mse: float
    psnr_db: float


def require_rgb_uint8(image: np.ndarray) -> np.ndarray:
    """Validate a true RGB uint8 array without implicit grayscale conversion."""

    if not isinstance(image, np.ndarray) or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("image must have shape (height, width, 3)")
    if image.dtype != np.uint8:
        raise ValueError("image must have dtype uint8")
    return image


def compute_mse(source: np.ndarray, reconstructed: np.ndarray) -> float:
    source = require_rgb_uint8(source)
    reconstructed = require_rgb_uint8(reconstructed)
    if source.shape != reconstructed.shape:
        raise ValueError("source and reconstructed shapes must match")
    difference = source.astype(np.float64) - reconstructed.astype(np.float64)
    mse = float(np.mean(difference * difference))
    if not math.isfinite(mse) or mse < 0.0:
        raise ValueError("MSE must be finite and non-negative")
    return mse


def psnr_from_mse(mse: float) -> float:
    if not math.isfinite(mse) or mse < 0.0:
        raise ValueError("MSE must be finite and non-negative")
    if mse == 0.0:
        return math.inf
    return 10.0 * math.log10((DATA_RANGE * DATA_RANGE) / mse)


def compute_error_metrics(source: np.ndarray, reconstructed: np.ndarray) -> ErrorMetrics:
    mse = compute_mse(source, reconstructed)
    return ErrorMetrics(mse=mse, psnr_db=psnr_from_mse(mse))


def compute_ssim(source: np.ndarray, reconstructed: np.ndarray) -> float:
    source = require_rgb_uint8(source)
    reconstructed = require_rgb_uint8(reconstructed)
    if source.shape != reconstructed.shape:
        raise ValueError("source and reconstructed shapes must match")
    if source.shape[0] < SSIM_PARAMETERS["win_size"] or source.shape[1] < SSIM_PARAMETERS["win_size"]:
        raise ValueError("image is smaller than the frozen SSIM window")
    value = float(structural_similarity(source, reconstructed, **SSIM_PARAMETERS))
    if not math.isfinite(value):
        raise ValueError("SSIM must be finite")
    return value


def compute_risk_weighted_metrics(
    source: np.ndarray,
    reconstructed: np.ndarray,
    combined_risk_values: Sequence[float],
) -> tuple[ErrorMetrics, float]:
    """Compute continuous combined-risk-weighted RGB error without normalization."""

    source = require_rgb_uint8(source)
    reconstructed = require_rgb_uint8(reconstructed)
    if source.shape != reconstructed.shape:
        raise ValueError("source and reconstructed shapes must match")
    height, width, _ = source.shape
    weights = np.asarray(tuple(combined_risk_values), dtype=np.float64)
    if weights.shape != (height * width,):
        raise ValueError("combined risk values must be row-major and match image dimensions")
    if not np.all(np.isfinite(weights)) or np.any(weights < 0.0) or np.any(weights > 1.0):
        raise ValueError("combined risk values must be finite and in [0, 1]")
    risk_sum = float(np.sum(weights))
    if risk_sum == 0.0:
        raise UndefinedMetricError("risk-weighted metric is undefined when combined risk sum is zero")
    squared_error = np.mean((source.astype(np.float64) - reconstructed.astype(np.float64)) ** 2, axis=2)
    weighted_mse = float(np.sum(weights.reshape((height, width)) * squared_error) / risk_sum)
    return ErrorMetrics(weighted_mse, psnr_from_mse(weighted_mse)), risk_sum


def compute_masked_error_metrics(source: np.ndarray, reconstructed: np.ndarray, mask: Sequence[bool]) -> ErrorMetrics:
    """Compute MSE/PSNR over selected pixels and all three RGB channels."""

    source = require_rgb_uint8(source)
    reconstructed = require_rgb_uint8(reconstructed)
    if source.shape != reconstructed.shape:
        raise ValueError("source and reconstructed shapes must match")
    height, width, _ = source.shape
    selected = np.asarray(tuple(mask), dtype=bool)
    if selected.shape != (height * width,):
        raise ValueError("mask must be row-major and match image dimensions")
    if not np.any(selected):
        raise UndefinedMetricError("masked metric is undefined for an empty region")
    source_pixels = source.reshape((-1, 3))[selected].astype(np.float64)
    reconstructed_pixels = reconstructed.reshape((-1, 3))[selected].astype(np.float64)
    mse = float(np.mean((source_pixels - reconstructed_pixels) ** 2))
    return ErrorMetrics(mse=mse, psnr_db=psnr_from_mse(mse))
