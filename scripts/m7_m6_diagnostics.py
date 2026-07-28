"""Read-only M7 diagnosis of the frozen M6 v3 allocation baselines.

The extractor reloads the 32 finalized episodes, reproduces every codec case,
and writes only derived publication sources under ``docs/``.  It never starts
Webots and never writes into the frozen runtime or analysis directories.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from compression.tile_container import serialize_tiled_frame
from compression.tiled_jpeg import DEFAULT_M5_GRID, encode_rgb_frame_to_tiles
from evaluation.image_quality import compute_masked_error_metrics
from evaluation.region_masks import _rasterize_polygon
from navigation.trajectory_prediction import CommandSegment
from perception.camera_projection import project_obstacle_box
from scripts.m6_multiscene_study import load_completed_episodes
from scripts.m6_tcobr import (
    CANNY_HIGH,
    CANNY_LOW,
    _boundary_mask,
    _camera_models,
    _obstacle_box,
    validate_tcobr_evidence,
)
from scripts.m6a_dual_roi import CurrentState, ScheduleEvidence
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_codec_audit import (
    BUDGET_ORDER,
    SnapshotCodecInput,
    build_method_mask,
    encode_reconstruct_case,
    evaluate_codec_case,
)
from simulator.m5e_scenarios import generate_scenario


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION_PATH = PROJECT_ROOT / "docs/results/m6_multiscene_v3_preregistration.json"
PACKAGE_ROOT = PROJECT_ROOT / "results/m6a_v2_control/prepared"
SOURCE_DIR = PROJECT_ROOT / "docs/figures/data"
FIGURE_DIR = PROJECT_ROOT / "docs/figures"
SUMMARY_PATH = PROJECT_ROOT / "docs/results/m7_m6_diagnostic_summary.json"
METHODS = ("state_only_risk_roi", "command_conditioned_risk_roi")
METHOD_LABELS = {METHODS[0]: "State-only", METHODS[1]: "Command-conditioned"}
BUDGETS = tuple(BUDGET_ORDER)
SCENES = tuple(f"S{index}" for index in range(1, 9))
WIDTH, HEIGHT, PIXELS = 160, 120, 160 * 120
QUALITY_CANDIDATES = (95, 75, 55, 35, 15, 1)
COLORS = {METHODS[0]: "#0072B2", METHODS[1]: "#D55E00"}
SUMMARY_SCHEMA = "m7-frozen-m6-diagnostic-summary-v1"

OVERLAP_FIELDS = (
    "episode_id", "scene", "seed", "snapshot_id", "budget",
    "state_roi_pixels", "command_roi_pixels", "roi_intersection_pixels",
    "roi_union_pixels", "roi_jaccard", "roi_xor_pixels", "roi_xor_fraction",
    "state_selected_tiles", "command_selected_tiles", "tile_intersection",
    "tile_union", "tile_jaccard", "tile_xor_count", "tile_xor_fraction",
    "quality_xor_tiles", "quality_xor_fraction", "identical_reconstruction",
)
CASE_FIELDS = (
    "episode_id", "scene", "seed", "snapshot_id", "method", "budget",
    "roi_pixels", "selected_tiles", "enhanced_quality", "background_quality",
    "charged_bytes", "tile_payload_bytes", "critical_tile_payload_bytes",
    "critical_tile_payload_fraction", "critical_region_pixels",
    "critical_boundary_edge_pixels", "eligible_boundary_edge_pixels",
    "critical_boundary_high_quality_coverage", "eligible_boundary_high_quality_coverage",
    "critical_region_mse", "critical_region_psnr_db", "eligible_boundary_mse",
    "eligible_boundary_psnr_db", "tcobr_eligible", "tcobr_recalled", "tcobr",
    "reconstruction_sha256",
)
EPISODE_FIELDS = (
    "episode_id", "scene", "seed", "method", "budget", "eligible_instances",
    "recalled_instances", "absolute_tcobr", "mean_critical_region_psnr_db",
    "mean_eligible_boundary_psnr_db", "mean_critical_tile_payload_bytes",
    "mean_critical_boundary_high_quality_coverage",
)
REASON_FIELDS = ("scene", "reason", "count")
PATTERN_FIELDS = (
    "scene", "budget", "n_snapshots", "mean_roi_jaccard", "mean_roi_xor_fraction",
    "mean_tile_jaccard", "mean_tile_xor_fraction", "mean_quality_xor_fraction",
    "identical_reconstruction_fraction", "state_defined_episodes", "command_defined_episodes",
    "state_absolute_tcobr", "command_absolute_tcobr", "state_critical_tile_payload_bytes",
    "command_critical_tile_payload_bytes", "state_critical_boundary_coverage",
    "command_critical_boundary_coverage", "state_critical_region_psnr_db",
    "command_critical_region_psnr_db",
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_bytes())


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _mean(values: Iterable[float | int | None]) -> float | None:
    finite = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return sum(finite) / len(finite) if finite else None


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _tile_selection(mask: np.ndarray) -> tuple[bool, ...]:
    if mask.shape != (HEIGHT, WIDTH):
        raise ValueError("M7 diagnostic requires the frozen 160x120 mask")
    return tuple(bool(mask[top:bottom, left:right].any()) for _, _, _, (left, top, right, bottom) in DEFAULT_M5_GRID.iter_tiles())


def allocation_overlap(state_mask: np.ndarray, command_mask: np.ndarray) -> dict[str, float | int]:
    """Return deterministic pixel and 8x6 tile overlap diagnostics."""
    state = np.asarray(state_mask, dtype=bool)
    command = np.asarray(command_mask, dtype=bool)
    if state.shape != command.shape or state.shape != (HEIGHT, WIDTH):
        raise ValueError("allocation masks must share the frozen image shape")
    intersection = int(np.count_nonzero(state & command))
    union = int(np.count_nonzero(state | command))
    xor = int(np.count_nonzero(state ^ command))
    state_tiles = np.asarray(_tile_selection(state), dtype=bool)
    command_tiles = np.asarray(_tile_selection(command), dtype=bool)
    tile_intersection = int(np.count_nonzero(state_tiles & command_tiles))
    tile_union = int(np.count_nonzero(state_tiles | command_tiles))
    tile_xor = int(np.count_nonzero(state_tiles ^ command_tiles))
    return {
        "state_roi_pixels": int(np.count_nonzero(state)),
        "command_roi_pixels": int(np.count_nonzero(command)),
        "roi_intersection_pixels": intersection,
        "roi_union_pixels": union,
        "roi_jaccard": _ratio(intersection, union) or 0.0,
        "roi_xor_pixels": xor,
        "roi_xor_fraction": xor / PIXELS,
        "state_selected_tiles": int(np.count_nonzero(state_tiles)),
        "command_selected_tiles": int(np.count_nonzero(command_tiles)),
        "tile_intersection": tile_intersection,
        "tile_union": tile_union,
        "tile_jaccard": _ratio(tile_intersection, tile_union) or 0.0,
        "tile_xor_count": tile_xor,
        "tile_xor_fraction": tile_xor / DEFAULT_M5_GRID.tile_count,
    }


def _snapshot_input(runtime: dict[str, Any], attempt_root: Path, snapshot_id: str) -> SnapshotCodecInput:
    metadata = _read_json(attempt_root / "raw" / f"{snapshot_id}.json")
    raw = (attempt_root / "raw" / f"{snapshot_id}.rgb").read_bytes()
    if _sha(raw) != metadata["frame_sha256"]:
        raise ValueError("raw snapshot hash mismatch")
    image = np.frombuffer(raw, dtype=np.uint8).reshape((HEIGHT, WIDTH, 3)).copy()
    schedule = ScheduleEvidence(
        metadata["schedule_id"],
        metadata["schedule_available_time_s"],
        tuple(CommandSegment(**segment) for segment in metadata["schedule_segments"]),
    )
    return SnapshotCodecInput.create(
        runtime_config=runtime,
        snapshot_id=snapshot_id,
        timestamp_s=metadata["simulation_timestamp_s"],
        image=image,
        state=CurrentState(**metadata["state"]),
        schedule=schedule,
        camera_context=metadata["camera_context"],
    )


def _load_mask(attempt_root: Path, snapshot_id: str, method: str, expected_hash: str) -> np.ndarray:
    value = _read_json(attempt_root / "snapshots" / snapshot_id / method / "mask.json")
    payload = tuple(float(item) for item in value["mask_payload"])
    if value.get("mask_hash") != expected_hash or digest(payload) != expected_hash or len(payload) != PIXELS:
        raise ValueError("persisted method mask failed canonical validation")
    array = np.asarray(payload, dtype=float).reshape((HEIGHT, WIDTH))
    if not np.isin(array, (0.0, 1.0)).all():
        raise ValueError("method mask is not binary")
    return array.astype(bool)


def _critical_masks(snapshot: SnapshotCodecInput, evidence: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray, Counter]:
    """Rebuild method-independent projected critical regions from frozen evidence."""
    checked = validate_tcobr_evidence(evidence)
    intrinsics, extrinsics = _camera_models(snapshot.camera_context)
    original_edges = cv2.Canny(cv2.cvtColor(snapshot.image, cv2.COLOR_RGB2GRAY), CANNY_LOW, CANNY_HIGH) > 0
    instances = {item["obstacle_id"]: item for item in checked["instances"]}
    critical_region = np.zeros((HEIGHT, WIDTH), dtype=bool)
    critical_boundary = np.zeros_like(critical_region)
    eligible_boundary = np.zeros_like(critical_region)
    reasons: Counter = Counter()
    geometry_items: list[dict[str, Any]] = []
    scene = generate_scenario(checked["scene"], "formal", checked["seed"])
    for spec in sorted(scene.obstacle_specs, key=lambda item: item.obstacle_id):
        if spec.obstacle_id not in instances:
            raise ValueError("TCOBR obstacle evidence is incomplete")
        item = instances[spec.obstacle_id]
        projection = project_obstacle_box(_obstacle_box(spec), intrinsics, extrinsics)
        polygon = tuple((point.u_px, point.v_px) for point in projection.clipped_polygon)
        boundary, projected = _boundary_mask(polygon, WIDTH, HEIGHT)
        edge_count = int(np.count_nonzero(original_edges & boundary))
        if projected != item["projected_pixel_count"] or edge_count != item["original_boundary_edge_count"]:
            raise ValueError("critical-region reconstruction disagrees with frozen TCOBR evidence")
        geometry_items.append({"obstacle_id": spec.obstacle_id, "critical": item["critical"], "polygon": polygon})
        reasons[item["exclusion_reason"] or "eligible"] += 1
        if item["critical"]:
            for u, v in _rasterize_polygon(polygon, WIDTH, HEIGHT):
                critical_region[v, u] = True
            critical_boundary |= original_edges & boundary
        if item["eligible"]:
            eligible_boundary |= original_edges & boundary
    if digest(geometry_items) != checked["geometry_digest"]:
        raise ValueError("method-independent TCOBR geometry digest mismatch")
    return critical_region, critical_boundary, eligible_boundary, reasons


def _candidate_allocations(image: np.ndarray, selection: tuple[bool, ...]) -> dict[int, tuple[tuple[Any, ...], bytes, tuple[int, ...]]]:
    pil = Image.fromarray(image, "RGB")
    output = {}
    for enhanced in QUALITY_CANDIDATES:
        qualities = tuple(enhanced if selected else max(1, enhanced - 30) for selected in selection)
        tiles = encode_rgb_frame_to_tiles(pil, DEFAULT_M5_GRID, qualities)
        output[enhanced] = (tiles, serialize_tiled_frame(DEFAULT_M5_GRID, tiles), qualities)
    return output


def _masked_quality(original: np.ndarray, reconstruction: np.ndarray, mask: np.ndarray) -> tuple[float | None, float | None]:
    if not mask.any():
        return None, None
    metrics = compute_masked_error_metrics(original, reconstruction, tuple(bool(value) for value in mask.ravel()))
    return metrics.mse, metrics.psnr_db


def _high_quality_mask(qualities: tuple[int, ...]) -> np.ndarray:
    output = np.zeros((HEIGHT, WIDTH), dtype=bool)
    background = min(qualities)
    for tile_id, _, _, (left, top, right, bottom) in DEFAULT_M5_GRID.iter_tiles():
        if qualities[tile_id] > background:
            output[top:bottom, left:right] = True
    return output


def _recover_case(
    runtime: dict[str, Any], snapshot: SnapshotCodecInput, mask_evidence: Any,
    mask_payload: tuple[float, ...], recorded: dict[str, Any], candidates: dict[int, tuple],
) -> tuple[Any, tuple[Any, ...], tuple[int, ...]]:
    case = encode_reconstruct_case(runtime, snapshot, mask_evidence, mask_payload, recorded["budget"])
    evaluation = evaluate_codec_case(runtime, snapshot, case)
    if case.case_sha256 != recorded["case_sha256"] or evaluation.evaluation_sha256 != recorded["evaluation_sha256"]:
        raise ValueError("frozen codec case failed deterministic reproduction")
    if case.charged_bytes != recorded["charged_bytes"] or evaluation.reconstruction_sha256 != recorded["tcobr_evidence"]["reconstruction_sha256"]:
        raise ValueError("frozen codec case fields disagree with reproduction")
    selected = None
    for enhanced in QUALITY_CANDIDATES:
        tiles, payload, qualities = candidates[enhanced]
        if len(payload) + case.mask_signal_bytes + case.metadata_bytes <= case.budget_bytes:
            selected = (tiles, payload, qualities)
            break
    if selected is None or selected[1] != case.payload:
        raise ValueError("could not recover authoritative tile allocation")
    return case, selected[0], selected[2]


def _case_geometry_signature(case: dict[str, Any]) -> tuple[Any, ...]:
    evidence = case["tcobr_evidence"]
    return (
        evidence["geometry_digest"],
        tuple((item["obstacle_id"], item["critical"], item["projected_pixel_count"],
               item["original_boundary_edge_count"], item["eligible"], item["exclusion_reason"])
              for item in evidence["instances"]),
    )


def extract_diagnostics() -> dict[str, Any]:
    """Strictly reload and reproduce all frozen cases, returning derived tables."""
    load_completed_episodes()  # Existing strict package/runtime/aggregate/joint validation.
    prereg = _read_json(PREREGISTRATION_PATH)
    if len(prereg.get("matrix", [])) != 32:
        raise ValueError("M7 diagnostics require the frozen 32-episode M6 v3 study")
    overlap_rows: list[dict[str, Any]] = []
    case_rows: list[dict[str, Any]] = []
    reason_counts: dict[str, Counter] = {scene: Counter() for scene in SCENES}
    evidence_bindings: list[dict[str, str]] = []
    for registration in prereg["matrix"]:
        package_path = PACKAGE_ROOT / registration["attempt_id"] / "package.json"
        package = _read_json(package_path)
        if (package["attempt_id"], package["identity_id"]) != (registration["attempt_id"], registration["episode_id"]):
            raise ValueError("prepared package identity mismatch")
        attempt_root = Path(package["prospective_attempt_root"])
        runtime_path = Path(package["launch_spec"]["runtime_config"]["path"])
        runtime = _read_json(runtime_path)
        aggregate_path = attempt_root / "codec_aggregate.json"
        aggregate = _read_json(aggregate_path)
        if aggregate.get("aggregate_sha256") != digest({key: value for key, value in aggregate.items() if key != "aggregate_sha256"}):
            raise ValueError("aggregate canonical digest mismatch")
        if (runtime["episode_id"], runtime["scene"], runtime["seed"], runtime["split"]) != (
            registration["episode_id"], registration["scene"], registration["seed"], "formal"
        ):
            raise ValueError("runtime identity mismatch")
        evidence_bindings.append({
            "attempt_id": registration["attempt_id"], "package_sha256": _sha(package_path.read_bytes()),
            "runtime_config_sha256": _sha(runtime_path.read_bytes()), "aggregate_sha256": aggregate["aggregate_sha256"],
        })
        snapshots = {item["snapshot_id"]: item for item in aggregate["snapshot_evidence"]}
        if set(snapshots) != {item["snapshot_id"] for item in runtime["snapshots"]}:
            raise ValueError("snapshot matrix mismatch")
        for snapshot_id in sorted(snapshots, key=int):
            snapshot = _snapshot_input(runtime, attempt_root, snapshot_id)
            recorded_cases = snapshots[snapshot_id]["cases"]
            if len(recorded_cases) != 8:
                raise ValueError("snapshot does not contain the frozen 2x4 case matrix")
            signatures = {_case_geometry_signature(case) for case in recorded_cases}
            if len(signatures) != 1:
                raise ValueError("TCOBR eligibility is not method-independent")
            reference = next(case for case in recorded_cases if case["method"] == METHODS[0] and case["budget"] == BUDGETS[0])
            critical_region, critical_boundary, eligible_boundary, reasons = _critical_masks(snapshot, reference["tcobr_evidence"])
            reason_counts[registration["scene"]].update(reasons)
            masks: dict[str, np.ndarray] = {}
            method_details: dict[str, dict[str, Any]] = {}
            for method in METHODS:
                mask_evidence, mask_payload = build_method_mask(runtime, snapshot, method)
                masks[method] = _load_mask(attempt_root, snapshot_id, method, mask_evidence.mask_sha256)
                if not np.array_equal(masks[method].ravel(), np.asarray(mask_payload, dtype=bool)):
                    raise ValueError("persisted mask differs from regenerated trusted mask")
                selection = _tile_selection(masks[method])
                candidates = _candidate_allocations(snapshot.image, selection)
                per_budget = {}
                for budget in BUDGETS:
                    recorded = next(case for case in recorded_cases if case["method"] == method and case["budget"] == budget)
                    case, tiles, qualities = _recover_case(runtime, snapshot, mask_evidence, mask_payload, recorded, candidates)
                    high_quality = _high_quality_mask(qualities)
                    critical_mse, critical_psnr = _masked_quality(snapshot.image, case.reconstruction, critical_region)
                    boundary_mse, boundary_psnr = _masked_quality(snapshot.image, case.reconstruction, eligible_boundary)
                    critical_tile_ids = []
                    for tile_id, _, _, (left, top, right, bottom) in DEFAULT_M5_GRID.iter_tiles():
                        if critical_region[top:bottom, left:right].any():
                            critical_tile_ids.append(tile_id)
                    critical_payload = sum(len(tiles[tile_id].jpeg_payload) for tile_id in critical_tile_ids)
                    total_tile_payload = sum(len(tile.jpeg_payload) for tile in tiles)
                    tcobr = validate_tcobr_evidence(recorded["tcobr_evidence"])
                    row = {
                        "episode_id": registration["episode_id"], "scene": registration["scene"], "seed": registration["seed"],
                        "snapshot_id": snapshot_id, "method": method, "budget": budget,
                        "roi_pixels": int(masks[method].sum()), "selected_tiles": sum(selection),
                        "enhanced_quality": max(qualities), "background_quality": min(qualities),
                        "charged_bytes": case.charged_bytes, "tile_payload_bytes": total_tile_payload,
                        "critical_tile_payload_bytes": critical_payload,
                        "critical_tile_payload_fraction": _ratio(critical_payload, total_tile_payload),
                        "critical_region_pixels": int(critical_region.sum()),
                        "critical_boundary_edge_pixels": int(critical_boundary.sum()),
                        "eligible_boundary_edge_pixels": int(eligible_boundary.sum()),
                        "critical_boundary_high_quality_coverage": _ratio(int(np.count_nonzero(critical_boundary & high_quality)), int(critical_boundary.sum())),
                        "eligible_boundary_high_quality_coverage": _ratio(int(np.count_nonzero(eligible_boundary & high_quality)), int(eligible_boundary.sum())),
                        "critical_region_mse": critical_mse, "critical_region_psnr_db": critical_psnr,
                        "eligible_boundary_mse": boundary_mse, "eligible_boundary_psnr_db": boundary_psnr,
                        "tcobr_eligible": tcobr["eligible_count"], "tcobr_recalled": tcobr["recalled_count"],
                        "tcobr": tcobr["tcobr"], "reconstruction_sha256": case.reconstruction_sha256,
                    }
                    case_rows.append(row)
                    per_budget[budget] = {"qualities": qualities, "reconstruction_sha256": case.reconstruction_sha256}
                method_details[method] = per_budget
            overlap = allocation_overlap(masks[METHODS[0]], masks[METHODS[1]])
            for budget in BUDGETS:
                state = method_details[METHODS[0]][budget]
                command = method_details[METHODS[1]][budget]
                quality_xor = sum(left != right for left, right in zip(state["qualities"], command["qualities"]))
                overlap_rows.append({
                    "episode_id": registration["episode_id"], "scene": registration["scene"], "seed": registration["seed"],
                    "snapshot_id": snapshot_id, "budget": budget, **overlap,
                    "quality_xor_tiles": quality_xor, "quality_xor_fraction": quality_xor / DEFAULT_M5_GRID.tile_count,
                    "identical_reconstruction": int(state["reconstruction_sha256"] == command["reconstruction_sha256"]),
                })
    episode_rows = _build_episode_rows(case_rows)
    reason_rows = [{"scene": scene, "reason": reason, "count": count}
                   for scene in SCENES for reason, count in sorted(reason_counts[scene].items())]
    pattern_rows = _build_pattern_rows(overlap_rows, case_rows, episode_rows)
    summary = _build_summary(overlap_rows, case_rows, episode_rows, reason_rows, pattern_rows, evidence_bindings)
    return {"overlap": overlap_rows, "cases": case_rows, "episodes": episode_rows,
            "reasons": reason_rows, "patterns": pattern_rows, "summary": summary}


def _build_episode_rows(case_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for row in case_rows:
        groups[(row["episode_id"], row["scene"], row["seed"], row["method"], row["budget"])].append(row)
    output = []
    for key, rows in sorted(groups.items()):
        eligible = sum(row["tcobr_eligible"] for row in rows)
        recalled = sum(row["tcobr_recalled"] for row in rows)
        output.append({
            "episode_id": key[0], "scene": key[1], "seed": key[2], "method": key[3], "budget": key[4],
            "eligible_instances": eligible, "recalled_instances": recalled,
            "absolute_tcobr": _ratio(recalled, eligible),
            "mean_critical_region_psnr_db": _mean(row["critical_region_psnr_db"] for row in rows),
            "mean_eligible_boundary_psnr_db": _mean(row["eligible_boundary_psnr_db"] for row in rows),
            "mean_critical_tile_payload_bytes": _mean(row["critical_tile_payload_bytes"] for row in rows if row["critical_region_pixels"]),
            "mean_critical_boundary_high_quality_coverage": _mean(row["critical_boundary_high_quality_coverage"] for row in rows),
        })
    if len(output) != 32 * 2 * 4:
        raise ValueError("episode diagnostic matrix is incomplete")
    return output


def _build_pattern_rows(overlap_rows, case_rows, episode_rows) -> list[dict[str, Any]]:
    output = []
    for scene in SCENES:
        for budget in BUDGETS:
            overlaps = [row for row in overlap_rows if row["scene"] == scene and row["budget"] == budget]
            cases = [row for row in case_rows if row["scene"] == scene and row["budget"] == budget]
            episodes = [row for row in episode_rows if row["scene"] == scene and row["budget"] == budget]
            base = {
                "scene": scene, "budget": budget, "n_snapshots": len(overlaps),
                "mean_roi_jaccard": _mean(row["roi_jaccard"] for row in overlaps),
                "mean_roi_xor_fraction": _mean(row["roi_xor_fraction"] for row in overlaps),
                "mean_tile_jaccard": _mean(row["tile_jaccard"] for row in overlaps),
                "mean_tile_xor_fraction": _mean(row["tile_xor_fraction"] for row in overlaps),
                "mean_quality_xor_fraction": _mean(row["quality_xor_fraction"] for row in overlaps),
                "identical_reconstruction_fraction": _mean(row["identical_reconstruction"] for row in overlaps),
            }
            for method, prefix in ((METHODS[0], "state"), (METHODS[1], "command")):
                method_episodes = [row for row in episodes if row["method"] == method and row["absolute_tcobr"] is not None]
                method_cases = [row for row in cases if row["method"] == method]
                base[f"{prefix}_defined_episodes"] = len(method_episodes)
                base[f"{prefix}_absolute_tcobr"] = _mean(row["absolute_tcobr"] for row in method_episodes)
                base[f"{prefix}_critical_tile_payload_bytes"] = _mean(row["critical_tile_payload_bytes"] for row in method_cases if row["critical_region_pixels"])
                base[f"{prefix}_critical_boundary_coverage"] = _mean(row["critical_boundary_high_quality_coverage"] for row in method_cases)
                base[f"{prefix}_critical_region_psnr_db"] = _mean(row["critical_region_psnr_db"] for row in method_cases)
            output.append(base)
    return output


def _build_summary(overlap_rows, case_rows, episode_rows, reason_rows, pattern_rows, evidence_bindings) -> dict[str, Any]:
    absolute = {}
    for budget in BUDGETS:
        absolute[budget] = {}
        for method in METHODS:
            values = [row["absolute_tcobr"] for row in episode_rows if row["budget"] == budget and row["method"] == method and row["absolute_tcobr"] is not None]
            absolute[budget][method] = {"n_episodes": len(values), "mean": _mean(values),
                                        "at_one": sum(value == 1.0 for value in values), "at_zero": sum(value == 0.0 for value in values)}
    identical = {budget: _mean(row["identical_reconstruction"] for row in overlap_rows if row["budget"] == budget) for budget in BUDGETS}
    actual_change = {budget: _mean(row["quality_xor_fraction"] for row in overlap_rows if row["budget"] == budget) for budget in BUDGETS}
    empty = {}
    for scene in ("S1", "S7", "S8"):
        empty[scene] = {row["reason"]: row["count"] for row in reason_rows if row["scene"] == scene}
    base = {
        "schema_version": SUMMARY_SCHEMA,
        "source": {
            "study": "frozen M6 v3 formal study", "episodes": 32, "snapshots": 128, "codec_cases": 1024,
            "preregistration_sha256": _sha(PREREGISTRATION_PATH.read_bytes()),
            "evidence_binding_sha256": digest(evidence_bindings),
        },
        "allocation_divergence": {
            "mean_state_roi_pixels": _mean(row["state_roi_pixels"] for row in overlap_rows[::4]),
            "mean_command_roi_pixels": _mean(row["command_roi_pixels"] for row in overlap_rows[::4]),
            "mean_roi_jaccard": _mean(row["roi_jaccard"] for row in overlap_rows[::4]),
            "mean_pixel_change_fraction": _mean(row["roi_xor_fraction"] for row in overlap_rows[::4]),
            "mean_tile_jaccard": _mean(row["tile_jaccard"] for row in overlap_rows[::4]),
            "mean_tile_change_fraction": _mean(row["tile_xor_fraction"] for row in overlap_rows[::4]),
            "quality_allocation_change_fraction_by_budget": actual_change,
            "identical_reconstruction_fraction_by_budget": identical,
        },
        "absolute_tcobr": absolute,
        "empty_scene_diagnosis": empty,
        "critical_region": {
            budget: {
                method: {
                    "mean_tile_payload_bytes": _mean(row["critical_tile_payload_bytes"] for row in case_rows if row["budget"] == budget and row["method"] == method and row["critical_region_pixels"]),
                    "mean_boundary_high_quality_coverage": _mean(row["critical_boundary_high_quality_coverage"] for row in case_rows if row["budget"] == budget and row["method"] == method),
                    "mean_region_psnr_db": _mean(row["critical_region_psnr_db"] for row in case_rows if row["budget"] == budget and row["method"] == method),
                } for method in METHODS
            } for budget in BUDGETS
        },
        "interpretation": {
            "confirmed_cause": "sparse trajectory-point masks plus coarse 8x6 tile quantization made the two allocations nearly identical; TCOBR was also saturated on eligible episodes",
            "causal_status": "descriptive mechanism diagnosis from frozen evidence; no new method is evaluated",
        },
    }
    base["summary_sha256"] = digest(base)
    return base


def persist_diagnostics(bundle: dict[str, Any]) -> None:
    _write_csv(SOURCE_DIR / "m7_allocation_overlap.csv", bundle["overlap"], OVERLAP_FIELDS)
    _write_csv(SOURCE_DIR / "m7_case_diagnostics.csv", bundle["cases"], CASE_FIELDS)
    _write_csv(SOURCE_DIR / "m7_episode_absolute_tcobr.csv", bundle["episodes"], EPISODE_FIELDS)
    _write_csv(SOURCE_DIR / "m7_empty_scene_reasons.csv", bundle["reasons"], REASON_FIELDS)
    _write_csv(SOURCE_DIR / "m7_scene_budget_patterns.csv", bundle["patterns"], PATTERN_FIELDS)
    _write_json(SUMMARY_PATH, bundle["summary"])


def validate_checked_sources() -> dict[str, Any]:
    summary = _read_json(SUMMARY_PATH)
    supplied = summary.pop("summary_sha256", None)
    if summary.get("schema_version") != SUMMARY_SCHEMA or supplied != digest(summary):
        raise ValueError("invalid M7 diagnostic summary digest")
    summary["summary_sha256"] = supplied
    overlap = _read_csv(SOURCE_DIR / "m7_allocation_overlap.csv")
    cases = _read_csv(SOURCE_DIR / "m7_case_diagnostics.csv")
    episodes = _read_csv(SOURCE_DIR / "m7_episode_absolute_tcobr.csv")
    reasons = _read_csv(SOURCE_DIR / "m7_empty_scene_reasons.csv")
    patterns = _read_csv(SOURCE_DIR / "m7_scene_budget_patterns.csv")
    if (len(overlap), len(cases), len(episodes), len(patterns)) != (512, 1024, 256, 32):
        raise ValueError("M7 checked-source coverage mismatch")
    if len({(row["episode_id"], row["snapshot_id"], row["budget"]) for row in overlap}) != 512:
        raise ValueError("duplicate overlap diagnostics")
    if len({(row["episode_id"], row["snapshot_id"], row["method"], row["budget"]) for row in cases}) != 1024:
        raise ValueError("duplicate case diagnostics")
    if {row["scene"] for row in patterns} != set(SCENES):
        raise ValueError("scene coverage mismatch")
    return {"summary": summary, "overlap": overlap, "cases": cases, "episodes": episodes, "reasons": reasons, "patterns": patterns}


def _float(row: dict[str, str], key: str) -> float | None:
    value = row[key]
    return None if value == "" else float(value)


def _style() -> None:
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.titlesize": 11,
                         "axes.labelsize": 9, "legend.fontsize": 8, "figure.dpi": 120,
                         "savefig.dpi": 360, "axes.spines.top": False, "axes.spines.right": False,
                         "svg.hashsalt": "ravc-m7-frozen-diagnostic-v1"})


def _save(fig, stem: str) -> None:
    metadata = {"Creator": "scripts.m7_m6_diagnostics", "Date": "2026-07-28"}
    svg_path = FIGURE_DIR / f"{stem}.svg"
    fig.savefig(svg_path, bbox_inches="tight", metadata=metadata)
    # Matplotlib leaves spaces after multiline SVG path commands.  Normalize
    # them so the tracked vector artifact also passes repository whitespace QA.
    svg_path.write_text(
        "\n".join(line.rstrip() for line in svg_path.read_text(encoding="utf-8").splitlines()) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    fig.savefig(FIGURE_DIR / f"{stem}.png", dpi=360, bbox_inches="tight", metadata=metadata)
    plt.close(fig)


def render_figures() -> tuple[str, ...]:
    data = validate_checked_sources()
    _style()
    budgets = list(BUDGETS)
    labels = [item.title() for item in budgets]
    summary = data["summary"]

    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.2))
    alloc = summary["allocation_divergence"]
    axes[0].bar([0, 1], [100 * alloc["mean_pixel_change_fraction"], 100 * alloc["mean_tile_change_fraction"]], color=["#56B4E9", "#009E73"])
    axes[0].set_xticks([0, 1], ["ROI pixels", "Selected tiles"]); axes[0].set_ylabel("Changed allocation (%)"); axes[0].set_title("A. Method divergence")
    identical = [100 * alloc["identical_reconstruction_fraction_by_budget"][budget] for budget in budgets]
    axes[1].bar(labels, identical, color="#0072B2"); axes[1].set_ylim(0, 100); axes[1].set_ylabel("Identical reconstructions (%)"); axes[1].set_title("B. Codec outcomes (n=128/budget)")
    quality = [100 * alloc["quality_allocation_change_fraction_by_budget"][budget] for budget in budgets]
    axes[2].bar(labels, quality, color="#D55E00"); axes[2].set_ylabel("Tiles with changed JPEG quality (%)"); axes[2].set_title("C. Actual quality-map divergence")
    fig.suptitle("M6 command conditioning rarely changed transmitted allocation", fontweight="bold")
    fig.tight_layout(); _save(fig, "m7_allocation_divergence")

    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    x = np.arange(4); width = .34
    for offset, method in ((-.17, METHODS[0]), (.17, METHODS[1])):
        values = [summary["absolute_tcobr"][budget][method]["mean"] for budget in budgets]
        ax.bar(x + offset, values, width, color=COLORS[method], label=METHOD_LABELS[method])
        for xpos, value, budget in zip(x + offset, values, budgets):
            n = summary["absolute_tcobr"][budget][method]["n_episodes"]
            ax.text(xpos, value + .025, f"n={n}", ha="center", va="bottom", fontsize=7)
    ax.set_xticks(x, labels); ax.set_ylim(0, 1.12); ax.set_ylabel("Absolute episode TCOBR"); ax.axhline(1, color="#666666", lw=.8, ls="--")
    ax.set_title("Absolute task performance is equal and near ceiling", pad=12)
    ax.legend(frameon=False, ncol=2, loc="lower left")
    fig.tight_layout(); _save(fig, "m7_absolute_tcobr")

    fig, axes = plt.subplots(1, 3, figsize=(10.8, 3.4))
    metrics = (("mean_tile_payload_bytes", "Critical-region tile payload (bytes)"),
               ("mean_boundary_high_quality_coverage", "Critical-boundary HQ coverage"),
               ("mean_region_psnr_db", "Critical-region PSNR (dB)"))
    for ax, (metric, ylabel) in zip(axes, metrics):
        for method in METHODS:
            values = [summary["critical_region"][budget][method][metric] for budget in budgets]
            ax.plot(labels, values, marker="o", lw=1.8, color=COLORS[method], label=METHOD_LABELS[method])
        ax.set_ylabel(ylabel); ax.set_title(ylabel.replace("Critical-", "")); ax.grid(axis="y", alpha=.25)
        if metric in {"mean_tile_payload_bytes", "mean_boundary_high_quality_coverage"}:
            ax.set_ylim(bottom=0, top=1 if metric == "mean_boundary_high_quality_coverage" else 14000)
    axes[0].legend(frameon=False, fontsize=7)
    fig.suptitle("Critical-region allocation and reconstruction remain method-equivalent", fontweight="bold")
    fig.tight_layout(); _save(fig, "m7_critical_region_diagnostics")

    reason_rows = data["reasons"]
    reasons = ("eligible", "not_trajectory_critical", "projected_pixels_below_64", "original_boundary_edges_below_16")
    reason_labels = ("Eligible", "Not trajectory-critical", "Projection <64 px", "Boundary <16 edges")
    colors = ("#009E73", "#999999", "#E69F00", "#CC79A7")
    fig, ax = plt.subplots(figsize=(8.4, 4.0)); bottom = np.zeros(8)
    for reason, label, color in zip(reasons, reason_labels, colors):
        values = [sum(int(row["count"]) for row in reason_rows if row["scene"] == scene and row["reason"] == reason) for scene in SCENES]
        ax.bar(SCENES, values, bottom=bottom, label=label, color=color); bottom += values
    ax.set_ylabel("Obstacle-snapshot instances (n=4 episodes/scene)"); ax.set_title("Why trajectory-critical obstacles are undefined in S1, S7, and S8")
    ax.legend(frameon=False, ncol=2); fig.tight_layout(); _save(fig, "m7_empty_scene_diagnosis")

    patterns = data["patterns"]
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.8))
    matrices = []
    for key in ("mean_quality_xor_fraction", "identical_reconstruction_fraction"):
        matrices.append(np.asarray([[100 * _float(next(row for row in patterns if row["scene"] == scene and row["budget"] == budget), key) for budget in budgets] for scene in SCENES]))
    titles = ("Tiles with different quality (%)", "Identical reconstructions (%)")
    for ax, matrix, title in zip(axes, matrices, titles):
        image = ax.imshow(matrix, aspect="auto", cmap="viridis", vmin=0, vmax=100)
        ax.set_xticks(range(4), labels); ax.set_yticks(range(8), SCENES); ax.set_title(title)
        for row in range(8):
            for col in range(4):
                ax.text(col, row, f"{matrix[row, col]:.1f}", ha="center", va="center", color="white" if matrix[row, col] < 55 else "black", fontsize=7)
        fig.colorbar(image, ax=ax, fraction=.046, pad=.04)
    fig.suptitle("Scene- and budget-level allocation collapse", fontweight="bold")
    fig.tight_layout(); _save(fig, "m7_scene_budget_failure_patterns")
    return ("m7_allocation_divergence", "m7_absolute_tcobr", "m7_critical_region_diagnostics", "m7_empty_scene_diagnosis", "m7_scene_budget_failure_patterns")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-source-data", action="store_true", help="re-extract checked sources from frozen M6 evidence")
    args = parser.parse_args(argv)
    if args.refresh_source_data:
        persist_diagnostics(extract_diagnostics())
    figures = render_figures()
    print(json.dumps({"summary": str(SUMMARY_PATH), "figures": list(figures), "validated": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
