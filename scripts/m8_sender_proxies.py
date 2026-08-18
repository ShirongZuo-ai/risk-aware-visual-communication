"""Sender-visible M8 FROPU and STRCF proxy candidates.

This module deliberately has no evaluator-geometry or CCORF import.
Passing its unit tests does not qualify either proxy for allocator use.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Mapping

import cv2
import numpy as np

from scripts.m6a_trusted_artifacts import digest
from scripts.m8_proxy_common import (
    QUALIFICATION_STATUS,
    ProxyIdentity,
    array_digest,
    require_field,
    require_rgb,
    require_unit_interval,
    validate_canonical_evidence,
)


FROPU_SCHEMA = "m8-fropu-evidence-v1"
STRCF_SCHEMA = "m8-strcf-evidence-v1"
SENDER_BOUNDARY = "sender_visible_only"
FORBIDDEN_FIELDS = {
    "actual_future_trajectory",
    "future_frame",
    "ground_truth_obstacle_geometry",
    "tcobr",
    "eligibility_label",
    "ccorf",
    "evaluator_mask",
    "navigation_outcome",
}
FROPU_EVIDENCE_FIELDS = {
    "schema_version", "proxy", "qualification_status", "source_boundary", "identity",
    "identity_digest", "config_digest", "input_digests", "score", "defined",
    "undefined_reason", "original_proposal_count", "reconstructed_proposal_count",
    "original_proposals", "reconstructed_proposals", "matches", "weight_sum",
    "actual_future_usage", "evaluator_input_usage", "fallback", "replacement",
    "canonical_digest",
}
STRCF_EVIDENCE_FIELDS = {
    "schema_version", "proxy", "qualification_status", "source_boundary", "identity",
    "identity_digest", "config_digest", "input_digests", "score", "color_fidelity",
    "gradient_fidelity", "risk_normalization_max", "uncertainty_normalization_max",
    "weight_sum", "actual_future_usage", "evaluator_input_usage", "fallback",
    "replacement", "canonical_digest",
}
PROPOSAL_FIELDS = {
    "proposal_id", "top", "left", "height", "width", "contour_area_px",
    "boundary_edge_pixels", "confidence", "corridor_overlap_fraction", "relevance",
    "boundary_digest", "support_digest",
}
MATCH_FIELDS = {
    "original_proposal_id", "reconstructed_proposal_id", "weight", "iou",
    "centroid_distance_px", "centroid_fidelity", "one_pixel_boundary_recall", "fidelity",
}


@dataclass(frozen=True)
class FROPUConfig:
    schema_version: str = "m8-fropu-config-v1"
    gaussian_kernel: tuple[int, int] = (3, 3)
    gaussian_sigma: float = 0.0
    canny_low: int = 50
    canny_high: int = 150
    close_kernel: tuple[int, int] = (3, 3)
    close_iterations: int = 1
    min_width_px: int = 3
    min_height_px: int = 3
    min_contour_area_px: float = 16.0
    min_boundary_edge_pixels: int = 8
    confidence_edge_scale: float = 32.0
    confidence_area_scale: float = 128.0
    relevance_floor: float = 0.10
    relevance_overlap_weight: float = 0.90
    iou_weight: float = 0.40
    centroid_weight: float = 0.30
    boundary_weight: float = 0.30
    centroid_scale_px: float = 20.0
    boundary_match_radius_px: int = 1

    def validate(self) -> None:
        if self.schema_version != "m8-fropu-config-v1":
            raise ValueError("invalid FROPU config schema")
        if self.gaussian_kernel != (3, 3) or self.close_kernel != (3, 3):
            raise ValueError("invalid FROPU kernel")
        if (self.canny_low, self.canny_high) != (50, 150):
            raise ValueError("invalid FROPU Canny thresholds")
        if self.close_iterations != 1 or self.boundary_match_radius_px != 1:
            raise ValueError("invalid FROPU morphology")
        frozen_values = (
            (self.gaussian_sigma, 0.0),
            (self.min_contour_area_px, 16.0),
            (self.confidence_edge_scale, 32.0),
            (self.confidence_area_scale, 128.0),
            (self.relevance_floor, 0.10),
            (self.relevance_overlap_weight, 0.90),
            (self.iou_weight, 0.40),
            (self.centroid_weight, 0.30),
            (self.boundary_weight, 0.30),
            (self.centroid_scale_px, 20.0),
        )
        if any(not math.isfinite(value) or value != expected for value, expected in frozen_values):
            raise ValueError("invalid frozen FROPU config value")
        if self.min_width_px != 3 or self.min_height_px != 3 or self.min_boundary_edge_pixels != 8:
            raise ValueError("invalid FROPU proposal thresholds")
        if not math.isclose(
            self.iou_weight + self.centroid_weight + self.boundary_weight,
            1.0,
        ):
            raise ValueError("FROPU fidelity weights must sum to one")
        if not math.isclose(self.relevance_floor + self.relevance_overlap_weight, 1.0):
            raise ValueError("FROPU relevance weights must sum to one")

    def canonical(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @property
    def canonical_digest(self) -> str:
        return digest(self.canonical())


@dataclass(frozen=True)
class STRCFConfig:
    schema_version: str = "m8-strcf-config-v1"
    weight_floor: float = 0.05
    risk_weight: float = 0.475
    uncertainty_weight: float = 0.475
    color_weight: float = 0.5
    gradient_weight: float = 0.5
    gradient_stabilizer: float = 10.0
    sobel_kernel_size: int = 3

    def validate(self) -> None:
        if self.schema_version != "m8-strcf-config-v1":
            raise ValueError("invalid STRCF config schema")
        frozen_values = (
            (self.weight_floor, 0.05),
            (self.risk_weight, 0.475),
            (self.uncertainty_weight, 0.475),
            (self.color_weight, 0.5),
            (self.gradient_weight, 0.5),
            (self.gradient_stabilizer, 10.0),
        )
        if any(not math.isfinite(value) or value != expected for value, expected in frozen_values):
            raise ValueError("invalid frozen STRCF config value")
        if not math.isclose(self.weight_floor + self.risk_weight + self.uncertainty_weight, 1.0):
            raise ValueError("STRCF spatial weights must sum to one")
        if not math.isclose(self.color_weight + self.gradient_weight, 1.0):
            raise ValueError("STRCF fidelity weights must sum to one")
        if self.gradient_stabilizer != 10.0 or self.sobel_kernel_size != 3:
            raise ValueError("invalid STRCF gradient definition")

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


def _reject_unknown_fields(fields: Mapping[str, Any]) -> None:
    if not fields:
        return
    names = set(fields)
    leakage = sorted(names & FORBIDDEN_FIELDS)
    if leakage:
        raise ValueError(f"evaluator/future fields are forbidden at the sender boundary: {leakage}")
    raise ValueError(f"unknown sender proxy fields: {sorted(names)}")


@dataclass(frozen=True)
class FROPUInput:
    identity: ProxyIdentity
    original: np.ndarray
    reconstruction: np.ndarray
    union_corridor: np.ndarray
    config: FROPUConfig

    @classmethod
    def create(
        cls,
        *,
        identity: ProxyIdentity,
        original: np.ndarray,
        reconstruction: np.ndarray,
        union_corridor: np.ndarray,
        config: FROPUConfig | None = None,
        **unknown: Any,
    ) -> "FROPUInput":
        _reject_unknown_fields(unknown)
        identity.validate()
        require_rgb(original, name="original")
        require_rgb(reconstruction, name="reconstruction")
        require_field(union_corridor, name="union_corridor", boolean=True)
        selected_config = config or FROPUConfig()
        selected_config.validate()
        return cls(
            identity,
            _immutable_copy(original),
            _immutable_copy(reconstruction),
            _immutable_copy(union_corridor),
            selected_config,
        )


@dataclass(frozen=True)
class STRCFInput:
    identity: ProxyIdentity
    original: np.ndarray
    reconstruction: np.ndarray
    union_risk: np.ndarray
    union_uncertainty: np.ndarray
    config: STRCFConfig

    @classmethod
    def create(
        cls,
        *,
        identity: ProxyIdentity,
        original: np.ndarray,
        reconstruction: np.ndarray,
        union_risk: np.ndarray,
        union_uncertainty: np.ndarray,
        config: STRCFConfig | None = None,
        **unknown: Any,
    ) -> "STRCFInput":
        _reject_unknown_fields(unknown)
        identity.validate()
        require_rgb(original, name="original")
        require_rgb(reconstruction, name="reconstruction")
        require_field(union_risk, name="union_risk")
        require_field(union_uncertainty, name="union_uncertainty")
        selected_config = config or STRCFConfig()
        selected_config.validate()
        return cls(
            identity,
            _immutable_copy(original),
            _immutable_copy(reconstruction),
            _immutable_copy(union_risk),
            _immutable_copy(union_uncertainty),
            selected_config,
        )


@dataclass(frozen=True)
class _Proposal:
    proposal_id: int
    top: int
    left: int
    height: int
    width: int
    contour_area_px: float
    boundary_edge_pixels: int
    confidence: float
    corridor_overlap_fraction: float
    relevance: float
    boundary_digest: str
    support_digest: str


@dataclass(frozen=True)
class _ProposalWork:
    proposal: _Proposal
    boundary: np.ndarray
    support: np.ndarray


def _proposal_work(image: np.ndarray, corridor: np.ndarray, config: FROPUConfig) -> tuple[_ProposalWork, ...]:
    grayscale = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(grayscale, config.gaussian_kernel, config.gaussian_sigma)
    edges = cv2.Canny(blurred, config.canny_low, config.canny_high) > 0
    closed = cv2.morphologyEx(
        edges.astype(np.uint8),
        cv2.MORPH_CLOSE,
        np.ones(config.close_kernel, dtype=np.uint8),
        iterations=config.close_iterations,
    )
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[tuple[tuple[int, int, int, int], float, int, np.ndarray, np.ndarray]] = []
    for contour in contours:
        left, top, width, height = cv2.boundingRect(contour)
        area = float(cv2.contourArea(contour))
        boundary = np.zeros(closed.shape, dtype=np.uint8)
        support = np.zeros(closed.shape, dtype=np.uint8)
        cv2.drawContours(boundary, [contour], -1, 1, thickness=1)
        cv2.drawContours(support, [contour], -1, 1, thickness=cv2.FILLED)
        boundary_edge_pixels = int(np.count_nonzero(edges & (boundary > 0)))
        if (
            width < config.min_width_px
            or height < config.min_height_px
            or area < config.min_contour_area_px
            or boundary_edge_pixels < config.min_boundary_edge_pixels
        ):
            continue
        candidates.append(((top, left, height, width), area, boundary_edge_pixels, boundary, support))
    candidates.sort(key=lambda item: item[0])
    result: list[_ProposalWork] = []
    for proposal_id, (box, area, edge_count, boundary, support) in enumerate(candidates):
        top, left, height, width = box
        support_count = int(np.count_nonzero(support))
        overlap = (
            float(np.count_nonzero((support > 0) & corridor)) / support_count
            if support_count
            else 0.0
        )
        confidence = min(1.0, edge_count / config.confidence_edge_scale) * min(
            1.0, area / config.confidence_area_scale
        )
        relevance = config.relevance_floor + config.relevance_overlap_weight * overlap
        proposal = _Proposal(
            proposal_id,
            top,
            left,
            height,
            width,
            area,
            edge_count,
            confidence,
            overlap,
            relevance,
            array_digest(boundary.astype(bool)),
            array_digest(support.astype(bool)),
        )
        result.append(_ProposalWork(proposal, boundary.astype(bool), support.astype(bool)))
    return tuple(result)


def _box_iou(left: _Proposal, right: _Proposal) -> float:
    x0 = max(left.left, right.left)
    y0 = max(left.top, right.top)
    x1 = min(left.left + left.width, right.left + right.width)
    y1 = min(left.top + left.height, right.top + right.height)
    intersection = max(0, x1 - x0) * max(0, y1 - y0)
    union = left.width * left.height + right.width * right.height - intersection
    return float(intersection / union) if union else 0.0


def _centroid_distance(left: _Proposal, right: _Proposal) -> float:
    left_center = (left.left + left.width / 2.0, left.top + left.height / 2.0)
    right_center = (right.left + right.width / 2.0, right.top + right.height / 2.0)
    return float(math.hypot(left_center[0] - right_center[0], left_center[1] - right_center[1]))


def evaluate_fropu(value: FROPUInput) -> dict[str, Any]:
    if not isinstance(value, FROPUInput):
        raise TypeError("FROPU requires validated FROPUInput")
    value.identity.validate()
    value.config.validate()
    original_proposals = _proposal_work(value.original, value.union_corridor, value.config)
    reconstructed_proposals = _proposal_work(value.reconstruction, value.union_corridor, value.config)
    matches: list[dict[str, Any]] = []
    numerator = 0.0
    denominator = 0.0
    kernel_size = value.config.boundary_match_radius_px * 2 + 1
    for original in original_proposals:
        weight = original.proposal.confidence * original.proposal.relevance
        denominator += weight
        best = None
        if reconstructed_proposals:
            best = max(
                reconstructed_proposals,
                key=lambda candidate: (
                    _box_iou(original.proposal, candidate.proposal),
                    -candidate.proposal.proposal_id,
                ),
            )
        if best is None:
            reconstructed_id = None
            iou = distance = boundary_recall = centroid_fidelity = fidelity = 0.0
        else:
            reconstructed_id = best.proposal.proposal_id
            iou = _box_iou(original.proposal, best.proposal)
            distance = _centroid_distance(original.proposal, best.proposal)
            centroid_fidelity = math.exp(-distance / value.config.centroid_scale_px)
            matched_boundary = cv2.dilate(
                best.boundary.astype(np.uint8),
                np.ones((kernel_size, kernel_size), dtype=np.uint8),
                iterations=1,
            ) > 0
            original_boundary_count = int(np.count_nonzero(original.boundary))
            boundary_recall = (
                float(np.count_nonzero(original.boundary & matched_boundary)) / original_boundary_count
                if original_boundary_count
                else 0.0
            )
            fidelity = (
                value.config.iou_weight * iou
                + value.config.centroid_weight * centroid_fidelity
                + value.config.boundary_weight * boundary_recall
            )
        numerator += weight * fidelity
        matches.append(
            {
                "original_proposal_id": original.proposal.proposal_id,
                "reconstructed_proposal_id": reconstructed_id,
                "weight": weight,
                "iou": iou,
                "centroid_distance_px": distance,
                "centroid_fidelity": centroid_fidelity,
                "one_pixel_boundary_recall": boundary_recall,
                "fidelity": fidelity,
            }
        )
    score = numerator / denominator if denominator > 0.0 else None
    base = {
        "schema_version": FROPU_SCHEMA,
        "proxy": "fropu",
        "qualification_status": QUALIFICATION_STATUS,
        "source_boundary": SENDER_BOUNDARY,
        "identity": value.identity.canonical(),
        "identity_digest": value.identity.canonical_digest,
        "config_digest": value.config.canonical_digest,
        "input_digests": {
            "original": array_digest(value.original),
            "reconstruction": array_digest(value.reconstruction),
            "union_corridor": array_digest(value.union_corridor),
        },
        "score": score,
        "defined": score is not None,
        "undefined_reason": None if score is not None else "no_original_proposals",
        "original_proposal_count": len(original_proposals),
        "reconstructed_proposal_count": len(reconstructed_proposals),
        "original_proposals": [asdict(item.proposal) for item in original_proposals],
        "reconstructed_proposals": [asdict(item.proposal) for item in reconstructed_proposals],
        "matches": matches,
        "weight_sum": denominator,
        "actual_future_usage": 0,
        "evaluator_input_usage": 0,
        "fallback": False,
        "replacement": False,
    }
    return {**base, "canonical_digest": digest(base)}


def _normalize_field(field: np.ndarray) -> tuple[np.ndarray, float]:
    maximum = float(np.max(field))
    return (field / maximum if maximum > 0.0 else np.zeros_like(field)), maximum


def _gradient_magnitude(image: np.ndarray, kernel_size: int) -> np.ndarray:
    grayscale = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY).astype(np.float64)
    dx = cv2.Sobel(grayscale, cv2.CV_64F, 1, 0, ksize=kernel_size)
    dy = cv2.Sobel(grayscale, cv2.CV_64F, 0, 1, ksize=kernel_size)
    return np.hypot(dx, dy)


def evaluate_strcf(value: STRCFInput) -> dict[str, Any]:
    if not isinstance(value, STRCFInput):
        raise TypeError("STRCF requires validated STRCFInput")
    value.identity.validate()
    value.config.validate()
    risk, risk_maximum = _normalize_field(value.union_risk)
    uncertainty, uncertainty_maximum = _normalize_field(value.union_uncertainty)
    spatial_weight = (
        value.config.weight_floor
        + value.config.risk_weight * risk
        + value.config.uncertainty_weight * uncertainty
    )
    difference = value.original.astype(np.float64) - value.reconstruction.astype(np.float64)
    color_fidelity = 1.0 - np.clip(
        np.linalg.norm(difference, axis=2) / (math.sqrt(3.0) * 255.0),
        0.0,
        1.0,
    )
    original_gradient = _gradient_magnitude(value.original, value.config.sobel_kernel_size)
    reconstructed_gradient = _gradient_magnitude(value.reconstruction, value.config.sobel_kernel_size)
    gradient_fidelity = 1.0 - np.clip(
        np.abs(original_gradient - reconstructed_gradient)
        / (original_gradient + reconstructed_gradient + value.config.gradient_stabilizer),
        0.0,
        1.0,
    )
    weight_sum = float(np.sum(spatial_weight))
    color_score = float(np.sum(spatial_weight * color_fidelity) / weight_sum)
    gradient_score = float(np.sum(spatial_weight * gradient_fidelity) / weight_sum)
    score = value.config.color_weight * color_score + value.config.gradient_weight * gradient_score
    base = {
        "schema_version": STRCF_SCHEMA,
        "proxy": "strcf",
        "qualification_status": QUALIFICATION_STATUS,
        "source_boundary": SENDER_BOUNDARY,
        "identity": value.identity.canonical(),
        "identity_digest": value.identity.canonical_digest,
        "config_digest": value.config.canonical_digest,
        "input_digests": {
            "original": array_digest(value.original),
            "reconstruction": array_digest(value.reconstruction),
            "union_risk": array_digest(value.union_risk),
            "union_uncertainty": array_digest(value.union_uncertainty),
            "spatial_weight": array_digest(spatial_weight),
        },
        "score": score,
        "color_fidelity": color_score,
        "gradient_fidelity": gradient_score,
        "risk_normalization_max": risk_maximum,
        "uncertainty_normalization_max": uncertainty_maximum,
        "weight_sum": weight_sum,
        "actual_future_usage": 0,
        "evaluator_input_usage": 0,
        "fallback": False,
        "replacement": False,
    }
    return {**base, "canonical_digest": digest(base)}


def validate_fropu_evidence(
    evidence: Mapping[str, Any],
    *,
    expected_identity: ProxyIdentity | None = None,
    source_input: FROPUInput | None = None,
) -> dict[str, Any]:
    if set(evidence) != FROPU_EVIDENCE_FIELDS:
        raise ValueError("unexpected FROPU evidence fields")
    value = validate_canonical_evidence(
        evidence,
        expected_schema=FROPU_SCHEMA,
        expected_identity=expected_identity,
    )
    if value.get("proxy") != "fropu" or value.get("source_boundary") != SENDER_BOUNDARY:
        raise ValueError("invalid FROPU evidence boundary")
    if value.get("qualification_status") != QUALIFICATION_STATUS:
        raise ValueError("FROPU must remain an unvalidated candidate")
    if value.get("config_digest") != FROPUConfig().canonical_digest:
        raise ValueError("FROPU config digest mismatch")
    score = require_unit_interval(value.get("score"), name="FROPU score", allow_none=True)
    if value.get("defined") is not (score is not None):
        raise ValueError("inconsistent FROPU defined status")
    proposals = value.get("original_proposals")
    reconstructed = value.get("reconstructed_proposals")
    matches = value.get("matches")
    if not isinstance(proposals, list) or len(proposals) != value.get("original_proposal_count"):
        raise ValueError("invalid FROPU original proposal count")
    if not isinstance(reconstructed, list) or len(reconstructed) != value.get("reconstructed_proposal_count"):
        raise ValueError("invalid FROPU reconstructed proposal count")
    if not isinstance(matches, list) or len(matches) != len(proposals):
        raise ValueError("invalid FROPU match count")
    if any(not isinstance(item, dict) or set(item) != PROPOSAL_FIELDS for item in proposals + reconstructed):
        raise ValueError("unexpected FROPU proposal fields")
    weighted_sum = 0.0
    weight_sum = 0.0
    config = FROPUConfig()
    for match in matches:
        if not isinstance(match, dict) or set(match) != MATCH_FIELDS:
            raise ValueError("unexpected FROPU match fields")
        for field in ("iou", "centroid_fidelity", "one_pixel_boundary_recall", "fidelity"):
            require_unit_interval(match.get(field), name=f"FROPU {field}")
        expected_fidelity = (
            config.iou_weight * match["iou"]
            + config.centroid_weight * match["centroid_fidelity"]
            + config.boundary_weight * match["one_pixel_boundary_recall"]
        )
        if not math.isclose(match["fidelity"], expected_fidelity, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("inconsistent FROPU match fidelity")
        weight = float(match.get("weight"))
        if not math.isfinite(weight) or weight < 0.0:
            raise ValueError("invalid FROPU match weight")
        weight_sum += weight
        weighted_sum += weight * match["fidelity"]
    if not math.isclose(float(value.get("weight_sum")), weight_sum, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("inconsistent FROPU weight sum")
    expected_score = weighted_sum / weight_sum if weight_sum > 0.0 else None
    if score != expected_score:
        raise ValueError("inconsistent FROPU score")
    expected_reason = None if expected_score is not None else "no_original_proposals"
    if value.get("undefined_reason") != expected_reason:
        raise ValueError("inconsistent FROPU undefined reason")
    if source_input is not None and value != evaluate_fropu(source_input):
        raise ValueError("FROPU evidence does not match source input")
    return value


def validate_strcf_evidence(
    evidence: Mapping[str, Any],
    *,
    expected_identity: ProxyIdentity | None = None,
    source_input: STRCFInput | None = None,
) -> dict[str, Any]:
    if set(evidence) != STRCF_EVIDENCE_FIELDS:
        raise ValueError("unexpected STRCF evidence fields")
    value = validate_canonical_evidence(
        evidence,
        expected_schema=STRCF_SCHEMA,
        expected_identity=expected_identity,
    )
    if value.get("proxy") != "strcf" or value.get("source_boundary") != SENDER_BOUNDARY:
        raise ValueError("invalid STRCF evidence boundary")
    if value.get("qualification_status") != QUALIFICATION_STATUS:
        raise ValueError("STRCF must remain an unvalidated candidate")
    config = STRCFConfig()
    if value.get("config_digest") != config.canonical_digest:
        raise ValueError("STRCF config digest mismatch")
    for field in ("score", "color_fidelity", "gradient_fidelity"):
        require_unit_interval(value.get(field), name=f"STRCF {field}")
    expected_score = (
        config.color_weight * value["color_fidelity"]
        + config.gradient_weight * value["gradient_fidelity"]
    )
    if not math.isclose(value["score"], expected_score, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("inconsistent STRCF score")
    for field in ("risk_normalization_max", "uncertainty_normalization_max", "weight_sum"):
        observed = value.get(field)
        if isinstance(observed, bool) or not isinstance(observed, (int, float)) or not math.isfinite(observed) or observed < 0.0:
            raise ValueError(f"invalid STRCF {field}")
    if source_input is not None and value != evaluate_strcf(source_input):
        raise ValueError("STRCF evidence does not match source input")
    return value
