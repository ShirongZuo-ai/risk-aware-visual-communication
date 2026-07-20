"""Frozen constants for the M5E-B static-AABB dataset generator."""

from __future__ import annotations

from pathlib import Path

from simulator.m3c_config import PREDICTION_HORIZON_S, PREDICTION_STEP_S, RISK_PARAMETERS


M5E_GENERATOR_VERSION = "m5e-b-static-aabb-v1"
M5E_EPISODE_PREFIX = "m5e"
SCENARIO_IDS = tuple(f"S{index}" for index in range(1, 9))
SNAPSHOT_PROGRESS_TARGETS = (0.20, 0.45, 0.70, 0.90)
SNAPSHOT_PROGRESS_TOLERANCE = 0.006
MAX_REPLACEMENTS = {"calibration": 10, "formal": 30, "smoke": 8}

CAMERA_DEVICE_NAME = "camera"
LEFT_WHEEL_DEVICE_NAME = "left wheel motor"
RIGHT_WHEEL_DEVICE_NAME = "right wheel motor"
EXPECTED_CAMERA_WIDTH_PX = 160
EXPECTED_CAMERA_HEIGHT_PX = 120
EXPECTED_HORIZONTAL_FOV_RAD = 0.84
EXPECTED_NEAR_CLIP_M = 0.0055

M5E_FRAME_DIR = Path("data/frames/m5e")
M5E_MASK_DIR = Path("data/masks/m5e")
M5E_METADATA_DIR = Path("data/metadata/m5e")
M5E_LOG_DIR = Path("data/logs/m5")
M5E_RESULTS_DIR = Path("results/m5_compression/m5e_smoke")
M5E_MANIFEST_PATH = M5E_LOG_DIR / "m5e_dataset_manifest.csv"
M5E_EPISODE_MANIFEST_PATH = M5E_METADATA_DIR / "m5e_episode_manifest.json"


def primary_seed_indices(split: str) -> tuple[int, ...]:
    if split == "calibration":
        return (0, 1)
    if split == "formal":
        return tuple(range(8))
    if split == "smoke":
        return (0,)
    raise ValueError(f"unsupported dataset split: {split}")


def primary_seed(split: str, scenario_index: int, seed_index: int) -> int:
    if scenario_index not in range(1, 9):
        raise ValueError("scenario_index must be in 1..8")
    if seed_index not in primary_seed_indices(split):
        raise ValueError(f"seed index {seed_index} is not valid for {split}")
    if split == "calibration":
        return 100000 + 100 * scenario_index + seed_index
    if split == "formal":
        return 200000 + 100 * scenario_index + seed_index
    return 9000 + scenario_index


def replacement_seed(split: str, scenario_index: int, replacement_index: int) -> int:
    if scenario_index not in range(1, 9):
        raise ValueError("scenario_index must be in 1..8")
    if not 0 <= replacement_index < MAX_REPLACEMENTS[split]:
        raise ValueError("replacement index is outside the frozen pool")
    if split == "calibration":
        return 100000 + 100 * scenario_index + 50 + replacement_index
    if split == "formal":
        return 200000 + 100 * scenario_index + 50 + replacement_index
    return 9000 + scenario_index + 100 * (replacement_index + 1)


__all__ = [
    "CAMERA_DEVICE_NAME", "EXPECTED_CAMERA_HEIGHT_PX", "EXPECTED_CAMERA_WIDTH_PX",
    "EXPECTED_HORIZONTAL_FOV_RAD", "EXPECTED_NEAR_CLIP_M", "LEFT_WHEEL_DEVICE_NAME",
    "M5E_EPISODE_MANIFEST_PATH", "M5E_EPISODE_PREFIX", "M5E_FRAME_DIR", "M5E_GENERATOR_VERSION",
    "M5E_LOG_DIR", "M5E_MANIFEST_PATH", "M5E_MASK_DIR", "M5E_METADATA_DIR", "M5E_RESULTS_DIR",
    "MAX_REPLACEMENTS", "PREDICTION_HORIZON_S", "PREDICTION_STEP_S", "RISK_PARAMETERS",
    "RIGHT_WHEEL_DEVICE_NAME", "SCENARIO_IDS", "SNAPSHOT_PROGRESS_TARGETS", "SNAPSHOT_PROGRESS_TOLERANCE",
    "primary_seed", "primary_seed_indices", "replacement_seed",
]
