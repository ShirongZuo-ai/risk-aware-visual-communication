"""Deterministic repository-owned synthetic fixtures for M8-B0 unit validation."""

from __future__ import annotations

import cv2
import numpy as np

from scripts.m6a_trusted_artifacts import digest
from scripts.m8_proxy_common import ProxyIdentity


JPEG_QUALITY_LADDER = (5, 15, 35, 55, 75, 95)


def synthetic_identity(reconstruction_id: str = "original") -> ProxyIdentity:
    return ProxyIdentity.create(
        identity_id="m8b0-synthetic-001",
        split="synthetic_unit",
        scene="M8B0_SYNTHETIC",
        episode_id="episode_0001",
        seed=0,
        snapshot_id="snapshot_00",
        reconstruction_id=reconstruction_id,
    )


def synthetic_fixture() -> dict[str, np.ndarray | str]:
    height, width = 120, 160
    y, x = np.indices((height, width))
    background = (28 + (x // 16) + (y // 20)).astype(np.uint8)
    image = np.stack((background, background + 4, background + 8), axis=-1)

    obstacle_mask = np.zeros((height, width), dtype=bool)
    obstacle_mask[35:91, 58:106] = True
    image[obstacle_mask] = np.array([210, 218, 226], dtype=np.uint8)
    cv2.rectangle(image, (58, 35), (105, 90), (250, 250, 250), thickness=2)
    cv2.line(image, (62, 82), (100, 43), (70, 90, 110), thickness=2)

    # A small off-corridor distractor supplies a controlled background target.
    cv2.rectangle(image, (128, 16), (149, 34), (150, 165, 180), thickness=2)

    eroded_obstacle = cv2.erode(obstacle_mask.astype(np.uint8), np.ones((7, 7), np.uint8), 1) > 0
    boundary = obstacle_mask & ~eroded_obstacle

    corridor = np.zeros((height, width), dtype=bool)
    corridor[25:105, 46:118] = True
    distance = ((x - 82.0) / 45.0) ** 2 + ((y - 66.0) / 55.0) ** 2
    risk = np.exp(-2.0 * distance)
    uncertainty = np.exp(-0.8 * distance)
    risk[~corridor] = 0.0
    uncertainty[~cv2.dilate(corridor.astype(np.uint8), np.ones((7, 7), np.uint8), 1).astype(bool)] = 0.0
    return {
        "original": image.astype(np.uint8),
        "union_corridor": corridor,
        "union_risk": risk.astype(np.float64),
        "union_uncertainty": uncertainty.astype(np.float64),
        "critical_obstacle_mask": obstacle_mask,
        "critical_boundary_mask": boundary,
        "geometry_digest": digest({"fixture": "m8b0-synthetic-critical-obstacle-v1"}),
    }


def jpeg_reconstruction(image: np.ndarray, quality: int) -> np.ndarray:
    if quality not in JPEG_QUALITY_LADDER:
        raise ValueError("quality is outside the frozen synthetic ladder")
    ok, payload = cv2.imencode(
        ".jpg",
        cv2.cvtColor(image, cv2.COLOR_RGB2BGR),
        [cv2.IMWRITE_JPEG_QUALITY, int(quality)],
    )
    if not ok:
        raise RuntimeError("synthetic JPEG encoding failed")
    decoded = cv2.imdecode(payload, cv2.IMREAD_COLOR)
    if decoded is None:
        raise RuntimeError("synthetic JPEG decoding failed")
    return cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB)


def controlled_perturbations(fixture: dict[str, np.ndarray | str]) -> dict[str, np.ndarray]:
    original = np.asarray(fixture["original"])
    obstacle = np.asarray(fixture["critical_obstacle_mask"], dtype=bool)
    blur = cv2.GaussianBlur(original, (9, 9), 0)
    contrast = np.clip((original.astype(np.float64) - 128.0) * 0.25 + 128.0, 0, 255).astype(np.uint8)

    localization = original.copy()
    patch = original[32:94, 55:109].copy()
    background_color = np.array([33, 37, 41], dtype=np.uint8)
    localization[32:94, 55:117] = background_color
    localization[32:94, 63:117] = patch

    occlusion = original.copy()
    occlusion[48:79, 68:96] = background_color

    irrelevant_background = cv2.GaussianBlur(original, (15, 15), 0)
    protected = cv2.dilate(obstacle.astype(np.uint8), np.ones((9, 9), np.uint8), 1).astype(bool)
    irrelevant_background[protected] = original[protected]

    return {
        "perfect": original.copy(),
        "blur": blur,
        "compression_q15": jpeg_reconstruction(original, 15),
        "contrast_loss": contrast,
        "localization_shift": localization,
        "occlusion": occlusion,
        "irrelevant_background": irrelevant_background,
    }
