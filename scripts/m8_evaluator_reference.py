"""Evaluator-isolated M8 CCORF calibration reference.

This module is not imported by the sender proxy implementation. CCORF is a
qualification reference only and can never be supplied to an allocator.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Mapping

import cv2
import numpy as np
from skimage.metrics import structural_similarity

from evaluation.image_quality import SSIM_PARAMETERS
from scripts.m6a_trusted_artifacts import digest
from scripts.m8_proxy_common import (
    ProxyIdentity,
    array_digest,
    require_field,
    require_rgb,
    require_unit_interval,
    validate_canonical_evidence,
)


CCORF_SCHEMA = "m8-ccorf-evidence-v1"
EVALUATOR_BOUNDARY = "evaluator_only"
CCORF_EVIDENCE_FIELDS = {
    "schema_version", "metric", "qualification_role", "source_boundary", "identity",
    "identity_digest", "config_digest", "geometry_digest", "input_digests",
    "projected_pixel_count", "original_boundary_edge_count", "eligible",
    "exclusion_reason", "soft_boundary_fidelity", "obstacle_ssim", "inverse_rgb_error",
    "score", "actual_future_usage", "evaluator_input_usage", "fallback", "replacement",
    "canonical_digest",
}


@dataclass(frozen=True)
class CCORFConfig:
    schema_version: str = "m8-ccorf-config-v1"
    canny_low: int = 50
    canny_high: int = 150
    soft_boundary_weight: float = 0.50
    obstacle_ssim_weight: float = 0.30
    inverse_rgb_error_weight: float = 0.20
    soft_distance_scale_px: float = 1.5
    distance_clip_px: float = 5.0
    min_projected_pixels: int = 64
    min_original_boundary_edges: int = 16

    def validate(self) -> None:
        if self.schema_version != "m8-ccorf-config-v1":
            raise ValueError("invalid CCORF config schema")
        if (self.canny_low, self.canny_high) != (50, 150):
            raise ValueError("invalid CCORF Canny thresholds")
        frozen_values = (
            (self.soft_boundary_weight, 0.50),
            (self.obstacle_ssim_weight, 0.30),
            (self.inverse_rgb_error_weight, 0.20),
        )
        if any(not math.isfinite(value) or value != expected for value, expected in frozen_values):
            raise ValueError("invalid frozen CCORF weight")
        weights = tuple(value for value, _ in frozen_values)
        if not math.isclose(sum(weights), 1.0):
            raise ValueError("CCORF weights must sum to one")
        if self.soft_distance_scale_px != 1.5 or self.distance_clip_px != 5.0:
            raise ValueError("invalid CCORF soft boundary definition")
        if self.min_projected_pixels != 64 or self.min_original_boundary_edges != 16:
            raise ValueError("invalid CCORF eligibility thresholds")

    def canonical(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @property
    def canonical_digest(self) -> str:
        return digest(self.canonical())


def _immutable_copy(value: np.ndarray) -> np.ndarray:
    result = np.array(value, copy=True)
    result.setflags(write=False)
    return result


@dataclass(frozen=True)
class CCORFInput:
    identity: ProxyIdentity
    original: np.ndarray
    reconstruction: np.ndarray
    critical_obstacle_mask: np.ndarray
    critical_boundary_mask: np.ndarray
    geometry_digest: str
    config: CCORFConfig

    @classmethod
    def create(
        cls,
        *,
        identity: ProxyIdentity,
        original: np.ndarray,
        reconstruction: np.ndarray,
        critical_obstacle_mask: np.ndarray,
        critical_boundary_mask: np.ndarray,
        geometry_digest: str,
        config: CCORFConfig | None = None,
        **unknown: Any,
    ) -> "CCORFInput":
        if unknown:
            raise ValueError(f"unknown CCORF evaluator fields: {sorted(unknown)}")
        identity.validate()
        require_rgb(original, name="original")
        require_rgb(reconstruction, name="reconstruction")
        require_field(critical_obstacle_mask, name="critical_obstacle_mask", boolean=True)
        require_field(critical_boundary_mask, name="critical_boundary_mask", boolean=True)
        if np.any(critical_boundary_mask & ~critical_obstacle_mask):
            raise ValueError("CCORF boundary must be contained in the obstacle mask")
        if not isinstance(geometry_digest, str) or len(geometry_digest) != 64:
            raise ValueError("CCORF requires a canonical geometry digest")
        try:
            int(geometry_digest, 16)
        except ValueError as exc:
            raise ValueError("CCORF geometry digest must be hexadecimal") from exc
        selected_config = config or CCORFConfig()
        selected_config.validate()
        return cls(
            identity,
            _immutable_copy(original),
            _immutable_copy(reconstruction),
            _immutable_copy(critical_obstacle_mask),
            _immutable_copy(critical_boundary_mask),
            geometry_digest.lower(),
            selected_config,
        )


def _canny(image: np.ndarray, config: CCORFConfig) -> np.ndarray:
    grayscale = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    return cv2.Canny(grayscale, config.canny_low, config.canny_high) > 0


def evaluate_ccorf(value: CCORFInput) -> dict[str, Any]:
    if not isinstance(value, CCORFInput):
        raise TypeError("CCORF requires validated evaluator-only CCORFInput")
    value.identity.validate()
    value.config.validate()
    projected_pixels = int(np.count_nonzero(value.critical_obstacle_mask))
    original_edges = _canny(value.original, value.config)
    reconstructed_edges = _canny(value.reconstruction, value.config)
    original_boundary = original_edges & value.critical_boundary_mask
    original_boundary_edges = int(np.count_nonzero(original_boundary))
    eligible = (
        projected_pixels >= value.config.min_projected_pixels
        and original_boundary_edges >= value.config.min_original_boundary_edges
    )
    exclusion_reason = None
    if projected_pixels < value.config.min_projected_pixels:
        exclusion_reason = "projected_pixels_below_64"
    elif original_boundary_edges < value.config.min_original_boundary_edges:
        exclusion_reason = "original_boundary_edges_below_16"

    soft_boundary_fidelity = obstacle_ssim = inverse_rgb_error = score = None
    if eligible:
        no_reconstructed_edge = (~reconstructed_edges).astype(np.uint8)
        distance = cv2.distanceTransform(no_reconstructed_edge, cv2.DIST_L2, 5)
        clipped_distance = np.minimum(distance, value.config.distance_clip_px)
        soft_boundary_fidelity = float(
            np.mean(np.exp(-clipped_distance[original_boundary] / value.config.soft_distance_scale_px))
        )
        _, ssim_map = structural_similarity(
            value.original,
            value.reconstruction,
            full=True,
            **SSIM_PARAMETERS,
        )
        selected_ssim = np.asarray(ssim_map)[value.critical_obstacle_mask]
        obstacle_ssim = float(np.clip((float(np.mean(selected_ssim)) + 1.0) / 2.0, 0.0, 1.0))
        difference = value.original.astype(np.float64) - value.reconstruction.astype(np.float64)
        color_fidelity = 1.0 - np.clip(
            np.linalg.norm(difference, axis=2) / (math.sqrt(3.0) * 255.0),
            0.0,
            1.0,
        )
        inverse_rgb_error = float(np.mean(color_fidelity[value.critical_obstacle_mask]))
        score = (
            value.config.soft_boundary_weight * soft_boundary_fidelity
            + value.config.obstacle_ssim_weight * obstacle_ssim
            + value.config.inverse_rgb_error_weight * inverse_rgb_error
        )

    base = {
        "schema_version": CCORF_SCHEMA,
        "metric": "ccorf",
        "qualification_role": "evaluator_reference_only",
        "source_boundary": EVALUATOR_BOUNDARY,
        "identity": value.identity.canonical(),
        "identity_digest": value.identity.canonical_digest,
        "config_digest": value.config.canonical_digest,
        "geometry_digest": value.geometry_digest,
        "input_digests": {
            "original": array_digest(value.original),
            "reconstruction": array_digest(value.reconstruction),
            "critical_obstacle_mask": array_digest(value.critical_obstacle_mask),
            "critical_boundary_mask": array_digest(value.critical_boundary_mask),
        },
        "projected_pixel_count": projected_pixels,
        "original_boundary_edge_count": original_boundary_edges,
        "eligible": eligible,
        "exclusion_reason": exclusion_reason,
        "soft_boundary_fidelity": soft_boundary_fidelity,
        "obstacle_ssim": obstacle_ssim,
        "inverse_rgb_error": inverse_rgb_error,
        "score": score,
        "actual_future_usage": 0,
        "evaluator_input_usage": 1,
        "fallback": False,
        "replacement": False,
    }
    return {**base, "canonical_digest": digest(base)}


def validate_ccorf_evidence(
    evidence: Mapping[str, Any],
    *,
    expected_identity: ProxyIdentity | None = None,
    source_input: CCORFInput | None = None,
) -> dict[str, Any]:
    if set(evidence) != CCORF_EVIDENCE_FIELDS:
        raise ValueError("unexpected CCORF evidence fields")
    validated = validate_canonical_evidence(
        evidence,
        expected_schema=CCORF_SCHEMA,
        expected_identity=expected_identity,
        expected_evaluator_input_usage=1,
    )
    if validated.get("metric") != "ccorf" or validated.get("source_boundary") != EVALUATOR_BOUNDARY:
        raise ValueError("invalid CCORF evaluator boundary")
    if validated.get("qualification_role") != "evaluator_reference_only":
        raise ValueError("CCORF cannot be used as a sender proxy")
    config = CCORFConfig()
    if validated.get("config_digest") != config.canonical_digest:
        raise ValueError("CCORF config digest mismatch")
    eligible = validated.get("eligible")
    if not isinstance(eligible, bool):
        raise ValueError("invalid CCORF eligibility")
    component_fields = ("soft_boundary_fidelity", "obstacle_ssim", "inverse_rgb_error", "score")
    for field in component_fields:
        require_unit_interval(validated.get(field), name=f"CCORF {field}", allow_none=True)
    if eligible and any(validated.get(field) is None for field in component_fields):
        raise ValueError("eligible CCORF evidence requires all components")
    if not eligible and any(validated.get(field) is not None for field in component_fields):
        raise ValueError("ineligible CCORF evidence must remain undefined")
    projected = validated.get("projected_pixel_count")
    boundary = validated.get("original_boundary_edge_count")
    if not isinstance(projected, int) or not isinstance(boundary, int) or projected < 0 or boundary < 0:
        raise ValueError("invalid CCORF eligibility counts")
    expected_eligible = projected >= config.min_projected_pixels and boundary >= config.min_original_boundary_edges
    if eligible is not expected_eligible:
        raise ValueError("inconsistent CCORF eligibility")
    if eligible:
        expected_score = (
            config.soft_boundary_weight * validated["soft_boundary_fidelity"]
            + config.obstacle_ssim_weight * validated["obstacle_ssim"]
            + config.inverse_rgb_error_weight * validated["inverse_rgb_error"]
        )
        if not math.isclose(validated["score"], expected_score, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("inconsistent CCORF score")
    if source_input is not None and validated != evaluate_ccorf(source_input):
        raise ValueError("CCORF evidence does not match evaluator source input")
    return validated
