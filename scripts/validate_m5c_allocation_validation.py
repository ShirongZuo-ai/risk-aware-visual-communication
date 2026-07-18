"""Independently recompute and validate Milestone 5C allocation evidence."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from compression.budget_matcher import match_uniform_quality_to_budget  # noqa: E402
from compression.spatial_allocation import (  # noqa: E402
    DEFAULT_ALLOCATION_SEARCH_SPACE,
    build_tile_cache,
    match_spatial_allocations_to_budgets,
)
from compression.tile_container import MAGIC, VERSION, deserialize_tiled_frame  # noqa: E402
from compression.tile_scoring import center_roi_scores, object_roi_scores, risk_roi_scores  # noqa: E402
from compression.tiled_jpeg import DEFAULT_M5_GRID, decode_tiles_to_rgb  # noqa: E402
from scripts.m5c_allocation_common import (  # noqa: E402
    CSV_FIELDS,
    DEVELOPMENT_BUDGETS,
    M5C_CONTAINER_DIR,
    M5C_CSV_PATH,
    M5C_METADATA_PATH,
    grid_json,
    jpeg_parameters_json,
    load_m4d_evidence,
    pillow_version,
    sha256_file,
)


def read_csv(path: Path = M5C_CSV_PATH) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != CSV_FIELDS:
            raise ValueError("M5C CSV schema mismatch")
        return list(reader)


def validate(path: Path = M5C_CSV_PATH) -> list[str]:
    errors: list[str] = []
    if not path.exists() or not M5C_METADATA_PATH.exists():
        return ["missing M5C generated CSV or metadata"]
    try:
        rows = read_csv(path)
        saved_metadata = json.loads(M5C_METADATA_PATH.read_text(encoding="utf-8"))
        image, metadata, _m4d_rows, mask, polygons = load_m4d_evidence()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [str(exc)]

    expected_hash = sha256_file(PROJECT_ROOT / metadata["frame_path"])
    expected_keys = {(method, budget_id) for method in ("uniform", "center_roi", "object_roi", "risk_roi") for budget_id, _ in DEVELOPMENT_BUDGETS}
    actual_keys = {(row.get("method"), row.get("budget_id")) for row in rows}
    if len(rows) != 16 or actual_keys != expected_keys or len(actual_keys) != len(rows):
        errors.append("M5C matrix must contain exactly 16 unique method-budget rows")
        return errors
    if saved_metadata.get("row_count") != 16 or saved_metadata.get("actual_future_trajectory_used") is not False:
        errors.append("M5C metadata row count or no-future-actual declaration is invalid")
    if saved_metadata.get("source_frame_sha256") != expected_hash:
        errors.append("M5C metadata source frame hash mismatch")
    if saved_metadata.get("grid") != grid_json() or saved_metadata.get("jpeg_parameters") != jpeg_parameters_json():
        errors.append("M5C metadata grid or JPEG parameters mismatch")
    if saved_metadata.get("pillow_version") != pillow_version():
        errors.append("M5C Pillow runtime version mismatch")

    cache = build_tile_cache(image)
    score_maps = {
        "center_roi": center_roi_scores((float(metadata["camera"]["cx_px"]), float(metadata["camera"]["cy_px"]))),
        "object_roi": object_roi_scores(polygons),
        "risk_roi": risk_roi_scores(mask),
    }
    target_values = tuple(target for _, target in DEVELOPMENT_BUDGETS)
    expected_spatial = {
        method: {match.target_bytes: match for match in match_spatial_allocations_to_budgets(score_map, cache, target_values, DEFAULT_ALLOCATION_SEARCH_SPACE)}
        for method, score_map in score_maps.items()
    }

    for row in rows:
        method = row["method"]
        target = int(row["target_bytes"])
        _check_row_common(row, expected_hash, errors)
        if method == "uniform":
            match = match_uniform_quality_to_budget(image, target, DEFAULT_M5_GRID)
            expected_scores = [0.0] * 48
            expected_config = {"background_quality": match.quality, "enhancement_quality": match.quality, "top_k": 0, "matcher": "m5b_uniform"}
            _compare_row_to_expected(
                row, match.actual_total_bytes, match.unused_bytes, match.utilization, expected_scores,
                list(match.encoded_frame.qualities), list(match.tile_payload_bytes), match.container_overhead_bytes,
                expected_config, len(match.candidates), sum(candidate.actual_total_bytes <= target for candidate in match.candidates), errors,
            )
            container = match.encoded_frame.container_bytes
        else:
            match = expected_spatial[method][target]
            expected_config = {
                "background_quality": match.selected_config.background_quality,
                "enhancement_quality": match.selected_config.enhancement_quality,
                "top_k": match.selected_config.top_k,
                "tie_break": match.deterministic_tie_break,
            }
            _compare_row_to_expected(
                row, match.actual_total_bytes, match.unused_bytes, match.utilization, list(match.score_map.scores),
                list(match.qualities), list(match.tile_payload_bytes), match.container_overhead_bytes,
                expected_config, match.candidate_count, match.feasible_candidate_count, errors,
            )
            container = match.container_bytes
            _check_monotonicity(match.score_map.scores, match.qualities, errors, f"{method}/{row['budget_id']}")
        _check_container_and_artifacts(row, container, errors)
    _check_uniform_regression(rows, errors)
    return errors


def _check_row_common(row: dict[str, str], expected_hash: str, errors: list[str]) -> None:
    if row["frame_id"] != "image_risk_validation_episode_0001" or row["frame_hash"] != expected_hash:
        errors.append(f"{row['method']}/{row['budget_id']}: frame identity mismatch")
    if row["grid_json"] != json.dumps(grid_json(), ensure_ascii=True, separators=(",", ":"), sort_keys=True):
        errors.append(f"{row['method']}/{row['budget_id']}: grid mismatch")
    if row["jpeg_parameters_json"] != json.dumps(jpeg_parameters_json(), ensure_ascii=True, separators=(",", ":"), sort_keys=True):
        errors.append(f"{row['method']}/{row['budget_id']}: JPEG parameter mismatch")
    if row["pillow_version"] != pillow_version() or row["container_magic"] != MAGIC.decode("ascii") or row["container_version"] != str(VERSION):
        errors.append(f"{row['method']}/{row['budget_id']}: runtime/container identity mismatch")
    if row["actual_future_trajectory_used"] != "false":
        errors.append(f"{row['method']}/{row['budget_id']}: future actual leakage declaration mismatch")


def _compare_row_to_expected(row, actual, unused, utilization, scores, qualities, tile_bytes, overhead, config, candidates, feasible, errors) -> None:
    label = f"{row['method']}/{row['budget_id']}"
    comparisons = {
        "actual_total_bytes": str(actual), "unused_bytes": str(unused), "tile_scores_json": json.dumps(scores, ensure_ascii=True, separators=(",", ":"), sort_keys=True),
        "tile_qualities_json": json.dumps(qualities, ensure_ascii=True, separators=(",", ":"), sort_keys=True),
        "tile_jpeg_bytes_json": json.dumps(tile_bytes, ensure_ascii=True, separators=(",", ":"), sort_keys=True),
        "container_overhead_bytes": str(overhead), "selected_allocation_json": json.dumps(config, ensure_ascii=True, separators=(",", ":"), sort_keys=True),
        "candidate_count": str(candidates), "feasible_candidate_count": str(feasible),
    }
    for field, expected in comparisons.items():
        if row[field] != expected:
            errors.append(f"{label}: {field} mismatch")
    if abs(float(row["utilization"]) - utilization) > 1e-15:
        errors.append(f"{label}: utilization mismatch")
    if int(row["actual_total_bytes"]) > int(row["target_bytes"]):
        errors.append(f"{label}: over budget")
    if int(row["unused_bytes"]) != int(row["target_bytes"]) - int(row["actual_total_bytes"]):
        errors.append(f"{label}: unused byte accounting mismatch")
    if sum(json.loads(row["tile_jpeg_bytes_json"])) + int(row["container_overhead_bytes"]) != int(row["actual_total_bytes"]):
        errors.append(f"{label}: tile byte accounting mismatch")
    if len(json.loads(row["tile_scores_json"])) != 48 or len(json.loads(row["tile_qualities_json"])) != 48:
        errors.append(f"{label}: scores or qualities length mismatch")


def _check_monotonicity(scores, qualities, errors, label: str) -> None:
    for i, score_i in enumerate(scores):
        for j, score_j in enumerate(scores):
            if score_i > score_j and qualities[i] < qualities[j]:
                errors.append(f"{label}: score-quality monotonicity violation")
                return


def _check_container_and_artifacts(row: dict[str, str], expected_container: bytes, errors: list[str]) -> None:
    label = f"{row['method']}/{row['budget_id']}"
    try:
        parsed = deserialize_tiled_frame(expected_container)
        decoded = decode_tiles_to_rgb(parsed.tiles, parsed.grid)
    except ValueError as exc:
        errors.append(f"{label}: invalid regenerated container: {exc}")
        return
    if len(expected_container) != int(row["actual_total_bytes"]) or decoded.size != (160, 120) or decoded.mode != "RGB":
        errors.append(f"{label}: regenerated container/decode mismatch")
    container_path = M5C_CONTAINER_DIR / f"{row['method']}_{row['budget_id']}.ravcjt"
    image_path = M5C_CONTAINER_DIR / f"{row['method']}_{row['budget_id']}.png"
    if not container_path.exists() or container_path.read_bytes() != expected_container:
        errors.append(f"{label}: saved container is not the regenerated selected container")
    if not image_path.exists():
        errors.append(f"{label}: saved decoded image is missing")


def _check_uniform_regression(rows: list[dict[str, str]], errors: list[str]) -> None:
    expected = {"severe": (31348, 5), "low": (32105, 25), "medium": (32729, 50), "high": (33959, 80)}
    for row in rows:
        if row["method"] != "uniform":
            continue
        actual, quality = expected[row["budget_id"]]
        qualities = json.loads(row["tile_qualities_json"])
        if int(row["actual_total_bytes"]) != actual or qualities != [quality] * 48:
            errors.append(f"Uniform regression failed for {row['budget_id']}")


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("m5c_allocation_validation: validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
