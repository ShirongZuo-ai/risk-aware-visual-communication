"""M7 v2 constrained offline allocator and development-corpus evaluation.

The allocator consumes sender-time evidence only. Evaluator-only geometry is
loaded after every allocation for an episode has been finalized and validated.
M7 v1 outputs are read-only and never rewritten by this module.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from compression.tile_container import serialize_tiled_frame
from compression.tiled_jpeg import DEFAULT_M5_GRID, decode_tiles_to_rgb
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_codec_audit import BUDGET_ORDER, METHODS, build_method_mask
from scripts.m6a_v2_pilot_completion import load_codec_aggregate
from scripts.m6a_v2_prepared_launch import load_prepared_launch_package_for_audit
from scripts.m7_m6_diagnostics import _snapshot_input
from scripts.m7_v1_corpus import validate_completed_corpus
from scripts.m7_v1_episode_source import load_evaluator_only_geometry
from scripts.m7_visual_voi import (
    BOOTSTRAP_REPLICATES,
    BOOTSTRAP_SEED,
    CANNY_HIGH,
    CANNY_LOW,
    CORPUS_REPORT,
    FROZEN_HEAD,
    HEIGHT,
    PACKAGE_ROOT,
    PREREGISTRATION,
    PROJECT_ROOT,
    WIDTH,
    VisualVoIInput,
    _baseline_candidates,
    _baseline_case,
    _bytes,
    _case_row,
    _critical_geometry,
    _episode_rows,
    _evaluate_reconstruction,
    _mean,
    _read,
    _save_figure,
    _sha_bytes,
    _tile_cache,
    stratified_ci,
)


OUTPUT_ROOT = PROJECT_ROOT / "docs/results"
FIGURE_ROOT = PROJECT_ROOT / "docs/figures"
SOURCE_ROOT = FIGURE_ROOT / "data"
SUMMARY_PATH = OUTPUT_ROOT / "m7_v2_summary.json"
CASE_PATH = OUTPUT_ROOT / "m7_v2_cases.csv"
EPISODE_PATH = OUTPUT_ROOT / "m7_v2_episodes.csv"
GATE_PATH = OUTPUT_ROOT / "m7_v2_gates.csv"
COMPARISON_PATH = OUTPUT_ROOT / "m7_v2_candidate_comparison.csv"
PROVENANCE_PATH = OUTPUT_ROOT / "m7_v2_provenance.json"
V1_SUMMARY_PATH = OUTPUT_ROOT / "m7_visual_voi_summary.json"
V1_SUMMARY_SHA256 = "492ebfc799735f83336c484001a1550659fddede5c44377716c3ab28e5e55831"
IMPLEMENTATION_BASE_HEAD = "92b99aa8c5aa05fa687b7d8a33f9390d3c5c9f24"
QUALITY_LADDER = (1, 5, 15, 25, 35, 45, 55, 65, 75, 95)
FAIRNESS_FRACTION = 0.005

CANDIDATE_CONFIGS: dict[str, dict[str, float]] = {
    "v2_global_only": {"whole_tile": 1.0},
    "v2_visible_edges": {"visible_edges": 0.50, "projected_corridor": 0.30, "whole_tile": 0.20},
    "v2_corridor_edges": {"corridor_edges": 0.50, "projected_corridor": 0.30, "whole_tile": 0.20},
}
CANDIDATES = tuple(CANDIDATE_CONFIGS)
ALL_METHODS = METHODS + CANDIDATES


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _metadata(candidate_id: str) -> bytes:
    if candidate_id not in CANDIDATE_CONFIGS:
        raise ValueError("unknown M7 v2 candidate")
    return _bytes({"candidate": candidate_id, "codec": "m7-visual-voi-v2", "mask_signal": "none"})


@dataclass(frozen=True)
class MatchedByteEnvelope:
    budget: str
    budget_bytes: int
    state_only_bytes: int
    command_conditioned_bytes: int
    midpoint_cap_bytes: int
    tolerance_bytes: float
    canonical_digest: str

    @classmethod
    def create(cls, *, budget: str, budget_bytes: int, state_only_bytes: int, command_conditioned_bytes: int):
        if budget not in BUDGET_ORDER or not all(isinstance(value, int) and value > 0 for value in (budget_bytes, state_only_bytes, command_conditioned_bytes)):
            raise ValueError("invalid matched-byte envelope")
        if max(state_only_bytes, command_conditioned_bytes) > budget_bytes:
            raise ValueError("baseline exceeds common budget")
        cap = (state_only_bytes + command_conditioned_bytes) // 2
        base = {"schema_version": "m7-v2-matched-byte-envelope-v1", "budget": budget, "budget_bytes": budget_bytes,
                "state_only_bytes": state_only_bytes, "command_conditioned_bytes": command_conditioned_bytes,
                "midpoint_cap_bytes": cap, "tolerance_bytes": FAIRNESS_FRACTION * budget_bytes}
        return cls(budget, budget_bytes, state_only_bytes, command_conditioned_bytes, cap,
                   FAIRNESS_FRACTION * budget_bytes, digest(base))

    def validate(self) -> "MatchedByteEnvelope":
        expected = MatchedByteEnvelope.create(budget=self.budget, budget_bytes=self.budget_bytes,
                                              state_only_bytes=self.state_only_bytes,
                                              command_conditioned_bytes=self.command_conditioned_bytes)
        if self != expected:
            raise ValueError("matched-byte envelope digest or fields")
        return self


@dataclass(frozen=True)
class V2Case:
    snapshot_id: str
    candidate_id: str
    budget: str
    qualities: tuple[int, ...]
    payload: bytes
    charged_bytes: int
    reconstruction: np.ndarray
    provenance: dict
    case_digest: str


def _masked_mse(original: np.ndarray, reconstructed: np.ndarray, mask: np.ndarray) -> float | None:
    if not np.any(mask):
        return None
    difference = original.astype(float) - reconstructed.astype(float)
    return float(np.mean(np.square(difference[mask])))


def prepare_v2(value: VisualVoIInput, *, tile_cache=None) -> dict:
    if any((value.actual_future_usage, value.evaluator_geometry_usage, value.method_specific_evaluation_usage)):
        raise ValueError("M7 v2 allocator leakage")
    encoded = tile_cache or _tile_cache(value.image)
    if any((tile_id, quality) not in encoded for tile_id in range(48) for quality in QUALITY_LADDER):
        raise ValueError("incomplete M7 v2 tile cache")
    state = np.asarray(value.state_mask, dtype=bool).reshape(HEIGHT, WIDTH)
    command = np.asarray(value.command_mask, dtype=bool).reshape(HEIGHT, WIDTH)
    corridor = state | command
    expanded_corridor = cv2.dilate(corridor.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=1) > 0
    edges = cv2.Canny(cv2.cvtColor(value.image, cv2.COLOR_RGB2GRAY), CANNY_LOW, CANNY_HIGH) > 0
    masks = {
        "whole_tile": np.ones((HEIGHT, WIDTH), dtype=bool),
        "visible_edges": edges,
        "projected_corridor": corridor,
        "corridor_edges": edges & expanded_corridor,
    }
    decoded: dict[tuple[int, int], np.ndarray] = {}
    component_mse: dict[tuple[int, int, str], float | None] = {}
    for tile_id, _, _, (left, top, right, bottom) in DEFAULT_M5_GRID.iter_tiles():
        original = value.image[top:bottom, left:right]
        for quality in QUALITY_LADDER:
            reconstruction = np.asarray(Image.open(io.BytesIO(encoded[(tile_id, quality)].jpeg_payload)).convert("RGB"), dtype=np.uint8)
            decoded[(tile_id, quality)] = reconstruction
            for name, mask in masks.items():
                component_mse[(tile_id, quality, name)] = _masked_mse(original, reconstruction, mask[top:bottom, left:right])
    distortions: dict[str, dict[tuple[int, int], float]] = {}
    for candidate_id, weights in CANDIDATE_CONFIGS.items():
        table = {}
        for tile_id in range(48):
            active = {name: weight for name, weight in weights.items()
                      if component_mse[(tile_id, QUALITY_LADDER[0], name)] is not None}
            scale = sum(active.values())
            if scale <= 0:
                raise ValueError("M7 v2 empty distortion definition")
            for quality in QUALITY_LADDER:
                table[(tile_id, quality)] = sum(
                    active[name] / scale * float(component_mse[(tile_id, quality, name)] or 0.0)
                    for name in active
                )
        distortions[candidate_id] = table
    base = {
        "schema_version": "m7-v2-prepared-allocation-v1",
        "source_digest": value.source_digest,
        "quality_ladder": list(QUALITY_LADDER),
        "candidate_configs": CANDIDATE_CONFIGS,
        "mask_sha256": {name: _sha_bytes(mask.astype(np.uint8).tobytes()) for name, mask in masks.items()},
        "distortion_sha256": {
            candidate_id: digest([{"tile": tile, "quality": quality, "value": table[(tile, quality)]}
                                  for tile in range(48) for quality in QUALITY_LADDER])
            for candidate_id, table in distortions.items()
        },
    }
    return {"source_digest": value.source_digest, "encoded": encoded, "distortions": distortions,
            "prepared_provenance": base, "prepared_digest": digest(base)}


def _container(encoded, qualities: list[int] | tuple[int, ...]) -> tuple[tuple, bytes]:
    tiles = tuple(encoded[(tile_id, quality)] for tile_id, quality in enumerate(qualities))
    return tiles, serialize_tiled_frame(DEFAULT_M5_GRID, tiles)


def validate_v2_provenance(value: dict) -> dict:
    supplied = value.get("canonical_digest")
    base = {key: item for key, item in value.items() if key != "canonical_digest"}
    if supplied != digest(base) or value.get("schema_version") != "m7-visual-voi-allocation-v2":
        raise ValueError("M7 v2 provenance digest")
    candidate_id = value.get("candidate_id")
    if candidate_id not in CANDIDATE_CONFIGS or value.get("distortion_weights") != CANDIDATE_CONFIGS[candidate_id]:
        raise ValueError("M7 v2 candidate configuration")
    if tuple(value.get("quality_ladder", ())) != QUALITY_LADDER:
        raise ValueError("M7 v2 quality ladder")
    if any(value.get(key) != 0 for key in ("actual_future_usage", "evaluator_geometry_usage",
                                           "method_specific_evaluation_usage", "fallback", "replacement")):
        raise ValueError("M7 v2 prohibited usage")
    qualities = value.get("final_qualities")
    floor = value.get("minimum_quality_floor")
    if not isinstance(qualities, list) or len(qualities) != 48 or floor not in QUALITY_LADDER or any(q not in QUALITY_LADDER or q < floor for q in qualities):
        raise ValueError("M7 v2 quality safeguard")
    if value.get("charged_bytes") != value.get("payload_bytes") + value.get("metadata_bytes"):
        raise ValueError("M7 v2 byte accounting")
    if value.get("charged_bytes") > value.get("midpoint_cap_bytes") or value.get("charged_bytes") > value.get("budget_bytes"):
        raise ValueError("M7 v2 byte cap")
    tolerance = float(value.get("fairness_tolerance_bytes", -1))
    if tolerance < 0 or any(abs(value["charged_bytes"] - value[key]) > tolerance + 1e-12
                            for key in ("state_only_bytes", "command_conditioned_bytes")):
        raise ValueError("M7 v2 byte fairness")
    if any(item["exact_delta_bytes"] <= 0 or item["delta_distortion"] <= 0 for item in value.get("chosen_transitions", [])):
        raise ValueError("M7 v2 unsafe transition")
    if value.get("exact_container_recomputations", 0) < len(value.get("chosen_transitions", [])):
        raise ValueError("M7 v2 recomputation evidence")
    return value


def validate_v2_provenance_record(value: dict) -> dict:
    supplied = value.get("record_digest")
    base = {key: item for key, item in value.items() if key != "record_digest"}
    if supplied != digest(base) or value.get("schema_version") != "m7-v2-allocation-record-v1":
        raise ValueError("M7 v2 provenance record digest")
    if not isinstance(value.get("episode_id"), str) or not isinstance(value.get("scene"), str) or not isinstance(value.get("seed"), int):
        raise ValueError("M7 v2 provenance record identity")
    if value.get("deterministic_double_run") is not True:
        raise ValueError("M7 v2 provenance reproduction")
    validate_v2_provenance(value.get("allocation", {}))
    return value


def validate_v2_provenance_bundle(value: dict) -> dict:
    supplied = value.get("canonical_digest")
    base = {key: item for key, item in value.items() if key != "canonical_digest"}
    records = value.get("allocations")
    if supplied != digest(base) or value.get("schema_version") != "m7-visual-voi-v2-provenance-v1":
        raise ValueError("M7 v2 provenance bundle digest")
    if not isinstance(records, list) or len(records) != 16 * 4 * len(CANDIDATES) * 4:
        raise ValueError("M7 v2 provenance bundle coverage")
    for record in records:
        validate_v2_provenance_record(record)
    identities = {(record["episode_id"], record["allocation"]["snapshot_id"],
                   record["allocation"]["candidate_id"], record["allocation"]["budget"])
                  for record in records}
    if len(identities) != len(records):
        raise ValueError("M7 v2 duplicate provenance identity")
    return value


def load_v2_summary(path: Path = SUMMARY_PATH) -> dict:
    value = _read(path)
    supplied = value.get("canonical_digest")
    base = {key: item for key, item in value.items() if key != "canonical_digest"}
    if supplied != digest(base) or value.get("schema_version") != "m7-visual-voi-v2-development-evaluation-v1":
        raise ValueError("M7 v2 summary digest")
    expected = {str(item.relative_to(PROJECT_ROOT)).replace("\\", "/"): item for item in
                (CASE_PATH, EPISODE_PATH, GATE_PATH, COMPARISON_PATH, PROVENANCE_PATH)}
    if set(value.get("source_sha256", {})) != set(expected):
        raise ValueError("M7 v2 summary source set")
    for relative, source in expected.items():
        if not source.is_file() or _sha_bytes(source.read_bytes()) != value["source_sha256"][relative]:
            raise ValueError("M7 v2 source digest")
    validate_v2_provenance_bundle(_read(PROVENANCE_PATH))
    if value.get("decision") not in {"GO", "NO-GO"}:
        raise ValueError("M7 v2 decision")
    if (value["decision"] == "GO") != (value.get("selected_candidate") is not None):
        raise ValueError("M7 v2 selection decision")
    return value


def allocate_v2(value: VisualVoIInput, candidate_id: str, envelope: MatchedByteEnvelope, *, prepared=None) -> V2Case:
    envelope.validate()
    if candidate_id not in CANDIDATE_CONFIGS:
        raise ValueError("unknown M7 v2 candidate")
    if any((value.actual_future_usage, value.evaluator_geometry_usage, value.method_specific_evaluation_usage)):
        raise ValueError("M7 v2 allocator leakage")
    prepared = prepared or prepare_v2(value)
    if prepared.get("source_digest") != value.source_digest:
        raise ValueError("M7 v2 prepared source mismatch")
    encoded = prepared["encoded"]
    distortion = prepared["distortions"][candidate_id]
    metadata = _metadata(candidate_id)
    floor_options = []
    recomputations = 0
    for quality in QUALITY_LADDER:
        tiles, payload = _container(encoded, [quality] * 48)
        recomputations += 1
        charged = len(payload) + len(metadata)
        floor_options.append((quality, tiles, payload, charged))
    feasible_floors = [item for item in floor_options if item[3] <= envelope.midpoint_cap_bytes]
    if not feasible_floors:
        raise ValueError("minimum quality exceeds matched byte cap")
    floor, tiles, payload, charged = feasible_floors[-1]
    qualities = [floor] * 48
    transitions = []
    while True:
        feasible = []
        for tile_id in range(48):
            index = QUALITY_LADDER.index(qualities[tile_id])
            if index + 1 >= len(QUALITY_LADDER):
                continue
            target = QUALITY_LADDER[index + 1]
            trial_qualities = qualities.copy()
            trial_qualities[tile_id] = target
            trial_tiles, trial_payload = _container(encoded, trial_qualities)
            recomputations += 1
            trial_charged = len(trial_payload) + len(metadata)
            delta_bytes = trial_charged - charged
            delta_distortion = distortion[(tile_id, qualities[tile_id])] - distortion[(tile_id, target)]
            if delta_bytes > 0 and delta_distortion > 0 and trial_charged <= envelope.midpoint_cap_bytes:
                feasible.append({"tile_id": tile_id, "from_quality": qualities[tile_id], "to_quality": target,
                                 "delta_distortion": delta_distortion, "exact_delta_bytes": delta_bytes,
                                 "score": delta_distortion / delta_bytes, "trial_tiles": trial_tiles,
                                 "trial_payload": trial_payload, "trial_charged": trial_charged})
        if not feasible:
            break
        selected = min(feasible, key=lambda item: (-item["score"], item["tile_id"], item["to_quality"]))
        before = charged
        qualities[selected["tile_id"]] = selected["to_quality"]
        tiles, payload, charged = selected["trial_tiles"], selected["trial_payload"], selected["trial_charged"]
        transitions.append({"step": len(transitions), "tile_id": selected["tile_id"],
                            "from_quality": selected["from_quality"], "to_quality": selected["to_quality"],
                            "delta_distortion": selected["delta_distortion"],
                            "exact_delta_bytes": selected["exact_delta_bytes"], "score": selected["score"],
                            "charged_bytes_before": before, "charged_bytes_after": charged,
                            "payload_sha256_after": _sha_bytes(payload)})
    if any(abs(charged - baseline_bytes) > envelope.tolerance_bytes + 1e-12
           for baseline_bytes in (envelope.state_only_bytes, envelope.command_conditioned_bytes)):
        raise ValueError("M7 v2 allocator could not satisfy byte fairness")
    reconstruction = np.asarray(decode_tiles_to_rgb(tiles, DEFAULT_M5_GRID), dtype=np.uint8)
    provenance = {
        "schema_version": "m7-visual-voi-allocation-v2", "candidate_id": candidate_id,
        "snapshot_id": value.snapshot_id, "budget": envelope.budget, "source_digest": value.source_digest,
        "prepared_digest": prepared["prepared_digest"], "distortion_weights": CANDIDATE_CONFIGS[candidate_id],
        "quality_ladder": list(QUALITY_LADDER), "minimum_quality_floor": floor,
        "byte_target_rule": "floor midpoint of exact state-only and command-conditioned charged bytes",
        "budget_bytes": envelope.budget_bytes, "state_only_bytes": envelope.state_only_bytes,
        "command_conditioned_bytes": envelope.command_conditioned_bytes,
        "midpoint_cap_bytes": envelope.midpoint_cap_bytes, "fairness_tolerance_bytes": envelope.tolerance_bytes,
        "envelope_digest": envelope.canonical_digest, "chosen_transitions": transitions,
        "tie_break": "highest-benefit-per-exact-byte,lower-row-major-tile-id,lower-target-quality",
        "final_qualities": qualities, "payload_sha256": _sha_bytes(payload), "payload_bytes": len(payload),
        "metadata_sha256": _sha_bytes(metadata), "metadata_bytes": len(metadata), "charged_bytes": charged,
        "exact_container_recomputations": recomputations, "all_overhead_charged": True,
        "actual_future_usage": 0, "evaluator_geometry_usage": 0, "method_specific_evaluation_usage": 0,
        "fallback": 0, "replacement": 0,
    }
    provenance["canonical_digest"] = digest(provenance)
    validate_v2_provenance(provenance)
    case_base = {"snapshot_id": value.snapshot_id, "candidate_id": candidate_id, "budget": envelope.budget,
                 "qualities": qualities, "charged_bytes": charged, "payload_sha256": _sha_bytes(payload),
                 "reconstruction_sha256": _sha_bytes(reconstruction.tobytes()),
                 "provenance_digest": provenance["canonical_digest"]}
    return V2Case(value.snapshot_id, candidate_id, envelope.budget, tuple(qualities), payload, charged,
                  reconstruction, provenance, digest(case_base))


def extract_evaluation() -> tuple[list[dict], list[dict], list[dict]]:
    if _sha_bytes(V1_SUMMARY_PATH.read_bytes()) != V1_SUMMARY_SHA256:
        raise ValueError("frozen M7 v1 summary changed")
    validation = validate_completed_corpus(head=FROZEN_HEAD)
    if not validation["passed"] or validation["completed_episode_count"] != 16:
        raise ValueError("M7 v1 corpus incomplete")
    registration = _read(PREREGISTRATION)
    case_rows: list[dict] = []
    provenance: list[dict] = []
    for item in registration["matrix"]:
        package_path = PACKAGE_ROOT / item["attempt_id"] / "package.json"
        package = load_prepared_launch_package_for_audit(package_path)
        root = Path(package["prospective_attempt_root"])
        runtime = _read(Path(package["launch_spec"]["runtime_config"]["path"]))
        aggregate = load_codec_aggregate(root / "codec_aggregate.json", runtime, root=root)
        snapshots = {snapshot_id: _snapshot_input(runtime, root, snapshot_id) for snapshot_id in ("0", "1", "2", "3")}
        recorded_snapshots = {entry["snapshot_id"]: entry for entry in aggregate["snapshot_evidence"]}
        baseline_data = {}
        candidate_data = {}
        for snapshot_id, snapshot in snapshots.items():
            state, state_payload = build_method_mask(runtime, snapshot, METHODS[0])
            command, command_payload = build_method_mask(runtime, snapshot, METHODS[1])
            allocator_input = VisualVoIInput.create(snapshot=snapshot, state_mask=state_payload,
                                                     command_mask=command_payload,
                                                     state_mask_sha256=state.mask_sha256,
                                                     command_mask_sha256=command.mask_sha256)
            tile_cache = _tile_cache(snapshot.image)
            prepared = prepare_v2(allocator_input, tile_cache=tile_cache)
            baseline_candidates = {}
            for method, mask_payload in ((METHODS[0], state_payload), (METHODS[1], command_payload)):
                array = np.asarray(mask_payload, dtype=bool).reshape(HEIGHT, WIDTH)
                selection = tuple(bool(array[top:bottom, left:right].any())
                                  for _, _, _, (left, top, right, bottom) in DEFAULT_M5_GRID.iter_tiles())
                baseline_candidates[method] = _baseline_candidates(tile_cache, selection)
            recorded_cases = recorded_snapshots[snapshot_id]["cases"]
            for budget in BUDGET_ORDER:
                baselines = {}
                for method, mask, mask_payload in ((METHODS[0], state, state_payload),
                                                   (METHODS[1], command, command_payload)):
                    recorded = next(row for row in recorded_cases if row["method"] == method and row["budget"] == budget)
                    baselines[method] = _baseline_case(runtime, snapshot, recorded, method, mask, mask_payload,
                                                       baseline_candidates[method])
                baseline_data[(snapshot_id, budget)] = baselines
                envelope = MatchedByteEnvelope.create(
                    budget=budget, budget_bytes=int(runtime["budgets"][budget]),
                    state_only_bytes=baselines[METHODS[0]][0].charged_bytes,
                    command_conditioned_bytes=baselines[METHODS[1]][0].charged_bytes)
                for candidate_id in CANDIDATES:
                    case = allocate_v2(allocator_input, candidate_id, envelope, prepared=prepared)
                    repeated = allocate_v2(allocator_input, candidate_id, envelope, prepared=prepared)
                    if case.case_digest != repeated.case_digest or case.payload != repeated.payload or case.provenance["canonical_digest"] != repeated.provenance["canonical_digest"]:
                        raise ValueError("M7 v2 allocation nondeterminism")
                    candidate_data[(snapshot_id, budget, candidate_id)] = case
                    record = {"schema_version": "m7-v2-allocation-record-v1",
                              "episode_id": item["episode_id"], "scene": item["scene"], "seed": item["seed"],
                              "deterministic_double_run": True, "allocation": case.provenance}
                    record["record_digest"] = digest(record)
                    validate_v2_provenance_record(record)
                    provenance.append(record)
        geometry = load_evaluator_only_geometry(root / "evaluator_only_geometry.json", runtime, root)
        for snapshot_id, snapshot in snapshots.items():
            critical = _critical_geometry(snapshot, geometry)
            for budget in BUDGET_ORDER:
                baselines = baseline_data[(snapshot_id, budget)]
                for method in METHODS:
                    baseline, qualities = baselines[method]
                    evaluation = _evaluate_reconstruction(snapshot, baseline.reconstruction, qualities, critical)
                    high_area = sum(value > min(qualities) for value in qualities) / 48
                    case_rows.append(_case_row(item, snapshot_id, method, budget, baseline.charged_bytes,
                                               baseline.budget_bytes, qualities, high_area, evaluation,
                                               baseline.case_sha256))
                for candidate_id in CANDIDATES:
                    case = candidate_data[(snapshot_id, budget, candidate_id)]
                    evaluation = _evaluate_reconstruction(snapshot, case.reconstruction, case.qualities, critical)
                    high_area = sum(value > min(case.qualities) for value in case.qualities) / 48
                    case_rows.append(_case_row(item, snapshot_id, candidate_id, budget, case.charged_bytes,
                                               int(runtime["budgets"][budget]), case.qualities, high_area,
                                               evaluation, case.case_digest))
    expected = 16 * 4 * len(ALL_METHODS) * 4
    identity = {(row["episode_id"], row["snapshot_id"], row["method"], row["budget"]) for row in case_rows}
    if len(case_rows) != expected or len(identity) != expected or len(provenance) != 16 * 4 * len(CANDIDATES) * 4:
        raise ValueError("M7 v2 evaluation coverage")
    return case_rows, _episode_rows(case_rows), provenance


def _effect_rows(episodes: list[dict], candidate_id: str) -> list[dict]:
    index = {(row["episode_id"], row["method"], row["budget"]): row for row in episodes}
    output = []
    for episode in sorted({row["episode_id"] for row in episodes}):
        for budget in BUDGET_ORDER:
            candidate = index[(episode, candidate_id, budget)]
            baselines = [index[(episode, method, budget)] for method in METHODS]
            result = {"episode_id": episode, "scene": candidate["scene"], "seed": candidate["seed"], "budget": budget}
            for metric in ("tcobr", "continuous_boundary_utility", "critical_boundary_hq_coverage",
                           "critical_region_psnr_db", "full_psnr_db", "full_ssim"):
                defined = [base[metric] for base in baselines if base[metric] is not None and math.isfinite(float(base[metric]))]
                value = candidate[metric]
                result[metric + "_effect"] = value - max(defined) if value is not None and math.isfinite(float(value)) and defined else None
            output.append(result)
    return output


def _primary_rows(effects: list[dict]) -> list[dict]:
    output = []
    for episode in sorted({row["episode_id"] for row in effects}):
        rows = [row for row in effects if row["episode_id"] == episode and row["budget"] in {"severe", "low"}
                and row["continuous_boundary_utility_effect"] is not None]
        if rows:
            output.append({"episode_id": episode, "scene": rows[0]["scene"],
                           "effect": _mean(row["continuous_boundary_utility_effect"] for row in rows)})
    return output


def evaluate_candidate(candidate_id: str, case_rows: list[dict], episodes: list[dict], provenance: list[dict]) -> tuple[list[dict], dict]:
    if candidate_id not in CANDIDATES:
        raise ValueError("unknown M7 v2 gate candidate")
    candidate_cases = [row for row in case_rows if row["method"] == candidate_id]
    candidate_provenance = [row for row in provenance if row["allocation"]["candidate_id"] == candidate_id]
    effects = _effect_rows(episodes, candidate_id)
    gates = []
    byte_gaps = {method: max(abs(row["charged_bytes"] - next(base["charged_bytes"] for base in case_rows
                            if base["episode_id"] == row["episode_id"] and base["snapshot_id"] == row["snapshot_id"]
                            and base["budget"] == row["budget"] and base["method"] == method)) / row["budget_bytes"]
                            for row in candidate_cases) for method in METHODS}
    gate1 = all(row["charged_bytes"] <= row["budget_bytes"] for row in candidate_cases) and max(byte_gaps.values()) <= FAIRNESS_FRACTION
    gates.append({"gate": 1, "name": "Exact byte fairness", "passed": gate1,
                  "value": f"max gaps state={byte_gaps[METHODS[0]]:.6f}, command={byte_gaps[METHODS[1]]:.6f}",
                  "threshold": "every case <= budget and <=0.005 from both baselines"})
    leakage = sum(row["allocation"][key] for row in candidate_provenance for key in
                  ("actual_future_usage", "evaluator_geometry_usage", "method_specific_evaluation_usage", "fallback", "replacement"))
    nonfinite = sum(1 for row in candidate_cases for value in row.values() if isinstance(value, float) and not math.isfinite(value))
    gate2 = len(candidate_cases) == 256 and len(candidate_provenance) == 256 and leakage == 0 and nonfinite == 0
    gates.append({"gate": 2, "name": "Integrity and leakage", "passed": gate2,
                  "value": f"cases={len(candidate_cases)}, provenance={len(candidate_provenance)}, prohibited={leakage}, nonfinite={nonfinite}",
                  "threshold": "complete finite coverage and zero prohibited usage"})
    actuation = {}
    for budget in ("severe", "low"):
        for method in METHODS:
            changed = 0
            total = 0
            for row in (item for item in candidate_cases if item["budget"] == budget):
                baseline = next(base for base in case_rows if base["episode_id"] == row["episode_id"]
                                and base["snapshot_id"] == row["snapshot_id"] and base["budget"] == budget
                                and base["method"] == method)
                total += 1
                changed += row["quality_map"] != baseline["quality_map"]
            actuation[f"{budget}_vs_{method}"] = changed / total
    gate3 = all(value >= 0.75 for value in actuation.values())
    gates.append({"gate": 3, "name": "Allocation actuation", "passed": gate3,
                  "value": "; ".join(f"{key}={value:.3f}" for key, value in actuation.items()),
                  "threshold": ">=0.75 snapshots differ by >=1 tile at Severe/Low"})
    primary = _primary_rows(effects)
    continuous_ci = stratified_ci(primary, "effect")
    gate4 = continuous_ci["ci_low"] is not None and continuous_ci["ci_low"] > 0
    gates.append({"gate": 4, "name": "Continuous task utility", "passed": gate4,
                  "value": f"effect={continuous_ci.get('mean')}, CI={continuous_ci.get('ci_low')},{continuous_ci.get('ci_high')}",
                  "threshold": "Severe/Low scene-stratified CI lower bound >0"})
    critical_psnr = {budget: _mean(row["critical_region_psnr_db_effect"] for row in effects if row["budget"] == budget)
                     for budget in ("severe", "low")}
    full_psnr = {budget: _mean(row["full_psnr_db_effect"] for row in effects if row["budget"] == budget)
                 for budget in ("severe", "low")}
    gate5 = all(critical_psnr[budget] is not None and critical_psnr[budget] >= -0.25 for budget in critical_psnr)
    gates.append({"gate": 5, "name": "Critical quality", "passed": gate5,
                  "value": json.dumps({"critical_psnr_db": critical_psnr, "full_psnr_db": full_psnr}, sort_keys=True),
                  "threshold": "critical-region PSNR >=-0.25 dB at Severe and Low"})
    tcobr = {budget: [row["tcobr_effect"] for row in effects if row["budget"] == budget and row["tcobr_effect"] is not None]
             for budget in ("severe", "low")}
    gate6 = all(values and min(values) >= 0 and _mean(values) >= 0 for values in tcobr.values())
    gates.append({"gate": 6, "name": "TCOBR non-degradation", "passed": gate6,
                  "value": "; ".join(f"{budget} mean={_mean(values)}, min={min(values) if values else None}" for budget, values in tcobr.items()),
                  "threshold": "no defined negative episode and nonnegative budget means"})
    fidelity = {budget: _mean(row["continuous_boundary_utility_effect"] for row in effects if row["budget"] == budget)
                for budget in ("severe", "low")}
    gate7 = all(value is not None and value > 0 for value in fidelity.values())
    gates.append({"gate": 7, "name": "Critical-boundary fidelity", "passed": gate7,
                  "value": "; ".join(f"{key}={value}" for key, value in fidelity.items()),
                  "threshold": "positive mean continuous effect at Severe and Low"})
    scene_effect = {scene: _mean(row["effect"] for row in primary if row["scene"] == scene)
                    for scene in sorted({row["scene"] for row in primary})}
    loo = {scene: _mean(value for other, value in scene_effect.items() if other != scene)
           for scene in scene_effect}
    positive_total = sum(max(0.0, value or 0.0) for value in scene_effect.values())
    max_contribution = max((max(0.0, value or 0.0) / positive_total for value in scene_effect.values()), default=0.0) if positive_total else 1.0
    gate8 = bool(loo) and all(value is not None and value > 0 for value in loo.values()) and max_contribution <= 0.50
    gates.append({"gate": 8, "name": "Scene balance", "passed": gate8,
                  "value": f"min LOO={min(loo.values()) if loo else None}, max positive contribution={max_contribution}",
                  "threshold": "all leave-one-scene-out effects >0 and max contribution <=0.50"})
    gate9 = len(candidate_provenance) == 256 and all(row.get("deterministic_double_run") is True for row in candidate_provenance)
    gates.append({"gate": 9, "name": "Deterministic reproduction", "passed": gate9,
                  "value": f"double-run matches={sum(row.get('deterministic_double_run') is True for row in candidate_provenance)}/256",
                  "threshold": "all 256 allocations and derived artifacts reproduce"})
    details = {"byte_gaps": byte_gaps, "actuation": actuation, "continuous_ci": continuous_ci,
               "critical_psnr_db": critical_psnr, "full_psnr_db": full_psnr,
               "tcobr_effects": {key: {"mean": _mean(values), "min": min(values) if values else None, "n": len(values)} for key, values in tcobr.items()},
               "fidelity": fidelity, "scene_effect": scene_effect, "leave_one_scene_out": loo,
               "max_positive_scene_contribution": max_contribution}
    return gates, details


def choose_candidate(results: dict[str, dict]) -> str | None:
    eligible = [candidate_id for candidate_id, result in results.items() if all(gate["passed"] for gate in result["gates"])]
    if not eligible:
        return None
    return min(eligible, key=lambda candidate_id: (
        -min(results[candidate_id]["details"]["leave_one_scene_out"].values()),
        -min(results[candidate_id]["details"]["critical_psnr_db"].values()),
        candidate_id,
    ))


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _render_figures(results: dict[str, dict], comparison: list[dict], target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 9, "font.family": "DejaVu Sans", "svg.hashsalt": "m7-visual-voi-v2"})
    palette = {True: "#009E73", False: "#D55E00"}
    matrix = np.asarray([[1 if gate["passed"] else 0 for gate in results[candidate]["gates"]] for candidate in CANDIDATES])
    fig, ax = plt.subplots(figsize=(8.0, 3.2))
    ax.imshow(matrix, cmap=matplotlib.colors.ListedColormap([palette[False], palette[True]]), vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(9), [f"G{index}" for index in range(1, 10)])
    ax.set_yticks(range(3), CANDIDATES)
    for row in range(3):
        for column in range(9):
            ax.text(column, row, "PASS" if matrix[row, column] else "FAIL", ha="center", va="center", color="white", fontweight="bold", fontsize=7)
    ax.set_title("M7 v2 preregistered candidate gates")
    fig.tight_layout(); _save_figure(fig, target / "m7_v2_candidate_gates")

    x = np.arange(len(CANDIDATES)); width = 0.34
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.5))
    continuous = [next(row for row in comparison if row["candidate_id"] == candidate)["primary_continuous_effect"] for candidate in CANDIDATES]
    ci_low = [next(row for row in comparison if row["candidate_id"] == candidate)["primary_continuous_ci_low"] for candidate in CANDIDATES]
    ci_high = [next(row for row in comparison if row["candidate_id"] == candidate)["primary_continuous_ci_high"] for candidate in CANDIDATES]
    axes[0].bar(x, continuous, color="#0072B2")
    axes[0].errorbar(x, continuous, yerr=[np.asarray(continuous)-np.asarray(ci_low), np.asarray(ci_high)-np.asarray(continuous)], fmt="none", color="black", capsize=3)
    axes[0].axhline(0, color="black", linewidth=.8); axes[0].set_xticks(x, CANDIDATES, rotation=20, ha="right")
    axes[0].set_ylabel("Continuous-boundary effect"); axes[0].set_title("Severe/Low scene-stratified effect (n=9)")
    severe = [next(row for row in comparison if row["candidate_id"] == candidate)["severe_critical_psnr_db_effect"] for candidate in CANDIDATES]
    low = [next(row for row in comparison if row["candidate_id"] == candidate)["low_critical_psnr_db_effect"] for candidate in CANDIDATES]
    axes[1].bar(x-width/2, severe, width, label="Severe", color="#CC79A7")
    axes[1].bar(x+width/2, low, width, label="Low", color="#56B4E9")
    axes[1].axhline(-.25, color="black", linewidth=.8, linestyle="--", label="-0.25 dB gate")
    axes[1].set_xticks(x, CANDIDATES, rotation=20, ha="right"); axes[1].set_ylabel("Critical PSNR effect (dB)")
    axes[1].set_title("Critical-quality safeguard"); axes[1].legend(frameon=False)
    fig.tight_layout(); _save_figure(fig, target / "m7_v2_task_quality")

    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.5))
    gaps = [next(row for row in comparison if row["candidate_id"] == candidate)["max_byte_utilization_gap"] for candidate in CANDIDATES]
    axes[0].bar(CANDIDATES, gaps, color="#0072B2"); axes[0].axhline(.005, color="black", linewidth=.8, linestyle="--")
    axes[0].set_xticks(x, CANDIDATES, rotation=20, ha="right"); axes[0].set_ylabel("Maximum utilization gap")
    axes[0].set_title("Exact-byte fairness (256 cases/candidate)")
    scenes = sorted({scene for result in results.values() for scene in result["details"]["scene_effect"]})
    scene_matrix = np.asarray([[results[candidate]["details"]["scene_effect"].get(scene, np.nan) for scene in scenes] for candidate in CANDIDATES])
    limit = max(abs(float(np.nanmin(scene_matrix))), abs(float(np.nanmax(scene_matrix))), .001)
    image = axes[1].imshow(scene_matrix, cmap="RdBu", vmin=-limit, vmax=limit, aspect="auto")
    axes[1].set_xticks(range(len(scenes)), scenes); axes[1].set_yticks(range(3), CANDIDATES)
    axes[1].set_title("Primary continuous effect by eligible scene")
    fig.colorbar(image, ax=axes[1], label="Effect")
    fig.tight_layout(); _save_figure(fig, target / "m7_v2_byte_scene")


def run_evaluation() -> dict:
    case_rows, episode_rows, provenance = extract_evaluation()
    results = {}
    gate_rows = []
    comparison = []
    for candidate_id in CANDIDATES:
        gates, details = evaluate_candidate(candidate_id, case_rows, episode_rows, provenance)
        results[candidate_id] = {"gates": gates, "details": details}
        gate_rows.extend({"candidate_id": candidate_id, **gate} for gate in gates)
        comparison.append({"candidate_id": candidate_id, "passed_gates": sum(gate["passed"] for gate in gates),
                           "all_gates_passed": all(gate["passed"] for gate in gates),
                           "primary_continuous_effect": details["continuous_ci"]["mean"],
                           "primary_continuous_ci_low": details["continuous_ci"]["ci_low"],
                           "primary_continuous_ci_high": details["continuous_ci"]["ci_high"],
                           "severe_continuous_effect": details["fidelity"]["severe"],
                           "low_continuous_effect": details["fidelity"]["low"],
                           "severe_critical_psnr_db_effect": details["critical_psnr_db"]["severe"],
                           "low_critical_psnr_db_effect": details["critical_psnr_db"]["low"],
                           "max_byte_utilization_gap": max(details["byte_gaps"].values()),
                           "min_leave_one_scene_out_effect": min(details["leave_one_scene_out"].values()) if details["leave_one_scene_out"] else None,
                           "max_positive_scene_contribution": details["max_positive_scene_contribution"]})
    chosen = choose_candidate(results)
    _write_csv(CASE_PATH, case_rows); _write_csv(EPISODE_PATH, episode_rows)
    _write_csv(GATE_PATH, gate_rows); _write_csv(COMPARISON_PATH, comparison)
    SOURCE_ROOT.mkdir(parents=True, exist_ok=True)
    for source in (CASE_PATH, EPISODE_PATH, GATE_PATH, COMPARISON_PATH):
        (SOURCE_ROOT / source.name).write_bytes(source.read_bytes())
    provenance_value = {"schema_version": "m7-visual-voi-v2-provenance-v1", "allocations": provenance}
    provenance_value["canonical_digest"] = digest(provenance_value)
    validate_v2_provenance_bundle(provenance_value)
    PROVENANCE_PATH.write_bytes(_bytes(provenance_value))
    _render_figures(results, comparison, FIGURE_ROOT)
    summary = {
        "schema_version": "m7-visual-voi-v2-development-evaluation-v1",
        "decision": "GO" if chosen else "NO-GO", "selected_candidate": chosen,
        "implementation_base_head": IMPLEMENTATION_BASE_HEAD, "frozen_corpus_head": FROZEN_HEAD,
        "v1_summary_sha256": V1_SUMMARY_SHA256, "episodes": 16, "snapshots": 64,
        "candidates": CANDIDATE_CONFIGS, "quality_ladder": list(QUALITY_LADDER),
        "fairness_fraction": FAIRNESS_FRACTION,
        "bootstrap": {"replicates": BOOTSTRAP_REPLICATES, "seed": BOOTSTRAP_SEED, "ci": .95,
                      "stratification": "within eligible scene; equal scene weights"},
        "information_boundary": {"actual_future_reads": 0, "evaluator_geometry_allocator_reads": 0,
                                 "method_specific_evaluation_inputs": 0,
                                 "allowed": ["current_rgb", "current_state", "predefined_schedule", "projection",
                                             "predicted_corridors", "baseline_exact_byte_counts"]},
        "selection_rule": "all nine gates; max minimum LOO continuous effect; max worst-budget critical PSNR; candidate ID",
        "candidate_results": results,
        "source_sha256": {str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"): _sha_bytes(path.read_bytes())
                          for path in (CASE_PATH, EPISODE_PATH, GATE_PATH, COMPARISON_PATH, PROVENANCE_PATH)},
        "figures": ["docs/figures/m7_v2_candidate_gates.svg", "docs/figures/m7_v2_task_quality.svg",
                    "docs/figures/m7_v2_byte_scene.svg"],
    }
    summary["canonical_digest"] = digest(summary)
    SUMMARY_PATH.write_bytes(_bytes(summary))
    return load_v2_summary(SUMMARY_PATH)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="M7 v2 constrained offline allocator evaluation")
    parser.add_argument("command", choices=("evaluate",))
    parser.parse_args(argv)
    print(json.dumps(run_evaluation(), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
