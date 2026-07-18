"""Validate Milestone 4D image-risk dataset by recomputing snapshot products."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import sys

from PIL import Image, ImageDraw


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from perception.camera_models import VisibilityStatus  # noqa: E402
from risk_map.image_risk_map import bind_projection_to_risk, build_image_risk_masks  # noqa: E402
from risk_map.trajectory_obstacle_risk import analyze_dual_trajectory_obstacle, compute_trajectory_disagreement  # noqa: E402
from scripts.m4d_image_risk_common import (  # noqa: E402
    assert_no_future_actual_leakage,
    camera_models_from_metadata,
    exclusive_pixels,
    mask_from_json,
    nonzero_pixels,
    obstacle_boxes_from_metadata,
    obstacle_footprint_from_box,
    overlap_pixels,
    parse_optional_float,
    quantize_mask_value,
    trajectories_from_metadata,
)
from perception.camera_projection import project_obstacle_box  # noqa: E402
from simulator.m4d_config import (  # noqa: E402
    COLOR_DISTANCE_THRESHOLD,
    DOMINANCE_MARGIN,
    EXPECTED_CAMERA_HEIGHT_PX,
    EXPECTED_CAMERA_WIDTH_PX,
    EXPECTED_HORIZONTAL_FOV_RAD,
    EXPECTED_NEAR_CLIP_M,
    FULLY_VISIBLE_BBOX_IOU_MIN,
    FULLY_VISIBLE_CENTER_ERROR_PX_MAX,
    FULLY_VISIBLE_POLYGON_IOU_MIN,
    M4_LOG_DIR,
    M4_RESULTS_DIR,
    OBSTACLE_SPECS,
    OVERLAP_PAIR,
    PARTIAL_BBOX_IOU_MIN,
    PARTIAL_CENTER_ERROR_PX_MAX,
    PARTIAL_POLYGON_IOU_MIN,
    RISK_PARAMETERS,
    RISK_TOLERANCE,
    ROLE_ORDER,
    SHARED_RISK_MIN,
    SNAPSHOT_TIME_S,
    VISIBILITY_DOMINANCE_MARGIN,
    obstacle_spec_by_id,
)


def _latest_csv() -> Path:
    candidates = sorted((PROJECT_ROOT / M4_LOG_DIR).glob("image_risk_validation_episode_*.csv"))
    if not candidates:
        raise FileNotFoundError("No M4D image-risk CSV found")
    return candidates[-1]


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _float(row: dict[str, str], field: str) -> float:
    value = float(row[field])
    if not math.isfinite(value):
        raise ValueError(f"{field} is not finite")
    return value


def _json(value: str):
    return json.loads(value) if value else None


def _bbox_from_row(row: dict[str, str]) -> tuple[float, float, float, float] | None:
    data = _json(row["bbox"])
    if data is None:
        return None
    return tuple(float(value) for value in data)  # type: ignore[return-value]


def _polygon_from_row(row: dict[str, str]) -> list[tuple[float, float]]:
    return [(float(item[0]), float(item[1])) for item in json.loads(row["clipped_polygon"])]


def _ensure(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _mask_from_color(image: Image.Image, target: tuple[int, int, int]) -> set[tuple[int, int]]:
    pixels = image.convert("RGB").load()
    threshold_sq = COLOR_DISTANCE_THRESHOLD * COLOR_DISTANCE_THRESHOLD
    result = set()
    for y in range(image.height):
        for x in range(image.width):
            r, g, b = pixels[x, y]
            if (r - target[0]) ** 2 + (g - target[1]) ** 2 + (b - target[2]) ** 2 <= threshold_sq:
                result.add((x, y))
    return result


def _bbox_from_pixels(points: set[tuple[int, int]]) -> tuple[float, float, float, float] | None:
    if not points:
        return None
    return (float(min(x for x, _ in points)), float(min(y for _, y in points)), float(max(x for x, _ in points)), float(max(y for _, y in points)))


def _bbox_iou(left, right) -> float:
    if left is None or right is None:
        return 0.0
    l0, l1, l2, l3 = left
    r0, r1, r2, r3 = right
    i0, i1, i2, i3 = max(l0, r0), max(l1, r1), min(l2, r2), min(l3, r3)
    if i2 < i0 or i3 < i1:
        return 0.0
    inter = (i2 - i0 + 1.0) * (i3 - i1 + 1.0)
    la = (l2 - l0 + 1.0) * (l3 - l1 + 1.0)
    ra = (r2 - r0 + 1.0) * (r3 - r1 + 1.0)
    return inter / (la + ra - inter)


def _center_error(left, right) -> float:
    if left is None or right is None:
        return math.inf
    return math.hypot((left[0] + left[2] - right[0] - right[2]) * 0.5, (left[1] + left[3] - right[1] - right[3]) * 0.5)


def _polygon_mask(size: tuple[int, int], polygon: list[tuple[float, float]]) -> set[tuple[int, int]]:
    if len(polygon) < 3:
        return set()
    mask = Image.new("1", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.polygon([(round(u), round(v)) for u, v in polygon], fill=1)
    pixels = mask.load()
    return {(x, y) for y in range(size[1]) for x in range(size[0]) if pixels[x, y]}


def _mask_iou(left: set[tuple[int, int]], right: set[tuple[int, int]]) -> float:
    union = left | right
    return 0.0 if not union else len(left & right) / len(union)


def _compare_mask_values(name: str, left, right, errors: list[str]) -> None:
    _ensure(left.width_px == right.width_px and left.height_px == right.height_px, f"{name}: mask dimensions mismatch", errors)
    if len(left.values) != len(right.values):
        errors.append(f"{name}: mask length mismatch")
        return
    for index, (a, b) in enumerate(zip(left.values, right.values)):
        if abs(a - b) > RISK_TOLERANCE:
            errors.append(f"{name}: mask value mismatch at {index}: {a} vs {b}")
            return


def _validate_png_quantization(results_dir: Path, masks_payload: dict, errors: list[str]) -> None:
    for channel in ("planned", "state", "combined"):
        path = results_dir / f"{channel}_mask.png"
        if not path.exists():
            continue
        image = Image.open(path).convert("L")
        mask = mask_from_json(masks_payload["masks"][channel])
        _ensure(image.size == (mask.width_px, mask.height_px), f"{channel}: PNG size mismatch", errors)
        pixels = image.load()
        for v in range(mask.height_px):
            for u in range(mask.width_px):
                expected = quantize_mask_value(mask.get(u, v))
                if pixels[u, v] != expected:
                    errors.append(f"{channel}: PNG quantization mismatch at {(u, v)}")
                    return


def validate(csv_path: Path) -> tuple[list[str], dict]:
    errors: list[str] = []
    rows = _load_csv(csv_path)
    specs_by_id = obstacle_spec_by_id()
    _ensure(len(rows) == len(OBSTACLE_SPECS), f"expected {len(OBSTACLE_SPECS)} rows, got {len(rows)}", errors)
    ids = [row["obstacle_id"] for row in rows]
    roles = [row["role"] for row in rows]
    _ensure(set(ids) == set(specs_by_id), f"obstacle ID set mismatch: {ids}", errors)
    _ensure(len(set(ids)) == len(ids), "obstacle IDs must be unique", errors)
    _ensure(tuple(roles) == ROLE_ORDER, f"row role order mismatch: {roles}", errors)
    if not rows:
        return errors, {}

    metadata_path = PROJECT_ROOT / "data" / "metadata" / "m4" / f"{csv_path.stem}.json"
    masks_path = PROJECT_ROOT / "data" / "masks" / "m4" / f"{csv_path.stem}_masks.json"
    _ensure(metadata_path.exists(), f"missing metadata: {metadata_path}", errors)
    _ensure(masks_path.exists(), f"missing masks JSON: {masks_path}", errors)
    if not metadata_path.exists() or not masks_path.exists():
        return errors, {}
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    masks_payload = json.loads(masks_path.read_text(encoding="utf-8"))
    assert_no_future_actual_leakage(metadata)

    frame_path = PROJECT_ROOT / metadata["frame_path"]
    _ensure(frame_path.exists(), f"missing frame: {frame_path}", errors)
    _ensure("Downloads" not in str(frame_path) and "Downloads" not in csv_path.read_text(encoding="utf-8"), "output paths must not contain Downloads", errors)
    _ensure(abs(float(metadata["snapshot_time_s"]) - SNAPSHOT_TIME_S) <= 0.04, "snapshot time does not match config", errors)
    camera = metadata["camera"]
    _ensure(camera["width_px"] == EXPECTED_CAMERA_WIDTH_PX and camera["height_px"] == EXPECTED_CAMERA_HEIGHT_PX, "camera size mismatch", errors)
    _ensure(abs(float(camera["horizontal_fov_rad"]) - EXPECTED_HORIZONTAL_FOV_RAD) <= 1e-9, "camera fov mismatch", errors)
    _ensure(abs(float(camera["near_clip_m"]) - EXPECTED_NEAR_CLIP_M) <= 1e-9, "camera near mismatch", errors)

    planned, state = trajectories_from_metadata(metadata)
    intrinsics, extrinsics = camera_models_from_metadata(metadata)
    boxes = obstacle_boxes_from_metadata(metadata)
    risks = {}
    projections = {}
    bound = []
    for box in boxes:
        result = analyze_dual_trajectory_obstacle(planned, state, obstacle_footprint_from_box(box), RISK_PARAMETERS)
        projection = project_obstacle_box(box, intrinsics, extrinsics)
        risks[box.obstacle_id] = result
        projections[box.obstacle_id] = projection
        bound.append(bind_projection_to_risk(projection, result.planned_result.risk_score, result.state_result.risk_score, result.combined_risk_score))
    recomputed_masks = build_image_risk_masks(intrinsics.width_px, intrinsics.height_px, bound)
    saved_masks = {
        "planned": mask_from_json(masks_payload["masks"]["planned"]),
        "state": mask_from_json(masks_payload["masks"]["state"]),
        "combined": mask_from_json(masks_payload["masks"]["combined"]),
    }
    _compare_mask_values("planned", saved_masks["planned"], recomputed_masks.planned, errors)
    _compare_mask_values("state", saved_masks["state"], recomputed_masks.state, errors)
    _compare_mask_values("combined", saved_masks["combined"], recomputed_masks.combined, errors)
    for p, s, c in zip(saved_masks["planned"].values, saved_masks["state"].values, saved_masks["combined"].values):
        _ensure(abs(c - max(p, s)) <= RISK_TOLERANCE, "combined mask must equal max(planned,state)", errors)

    by_id = {row["obstacle_id"]: row for row in rows}
    contribution_by_id = {item.obstacle_id: item for item in recomputed_masks.contributions}
    polygon_pixels_by_id = {}
    for row in rows:
        spec = specs_by_id[row["obstacle_id"]]
        result = risks[row["obstacle_id"]]
        projection = projections[row["obstacle_id"]]
        contribution = contribution_by_id[row["obstacle_id"]]
        _ensure(row["expected_visibility"] == spec.expected_visibility.value, f"{spec.role}: expected visibility config mismatch", errors)
        _ensure(row["actual_visibility"] == projection.visibility_status.value, f"{spec.role}: recomputed visibility mismatch", errors)
        _ensure(row["actual_visibility"] == spec.expected_visibility.value, f"{spec.role}: actual visibility {row['actual_visibility']} != expected {spec.expected_visibility.value}", errors)
        _ensure(abs(_float(row, "planned_risk") - result.planned_result.risk_score) <= RISK_TOLERANCE, f"{spec.role}: planned risk mismatch", errors)
        _ensure(abs(_float(row, "state_risk") - result.state_result.risk_score) <= RISK_TOLERANCE, f"{spec.role}: state risk mismatch", errors)
        _ensure(abs(_float(row, "combined_risk") - result.combined_risk_score) <= RISK_TOLERANCE, f"{spec.role}: combined risk mismatch", errors)
        _ensure(abs(_float(row, "combined_risk") - max(_float(row, "planned_risk"), _float(row, "state_risk"))) <= RISK_TOLERANCE, f"{spec.role}: combined not max", errors)
        _ensure(int(row["candidate_pixel_count"]) == contribution.candidate_pixel_count, f"{spec.role}: candidate count mismatch", errors)
        _ensure(int(row["planned_written_pixel_count"]) == contribution.planned_written_pixel_count, f"{spec.role}: planned written count mismatch", errors)
        _ensure(int(row["state_written_pixel_count"]) == contribution.state_written_pixel_count, f"{spec.role}: state written count mismatch", errors)
        _ensure(int(row["combined_written_pixel_count"]) == contribution.combined_written_pixel_count, f"{spec.role}: combined written count mismatch", errors)
        single_masks = build_image_risk_masks(
            EXPECTED_CAMERA_WIDTH_PX,
            EXPECTED_CAMERA_HEIGHT_PX,
            [bind_projection_to_risk(projection, 1.0, 1.0, 1.0)],
        )
        polygon_pixels_by_id[row["obstacle_id"]] = nonzero_pixels(single_masks.combined)
        if row["actual_visibility"] in (VisibilityStatus.OUTSIDE_FRUSTUM.value, VisibilityStatus.BEHIND_CAMERA.value):
            _ensure(row["eligible_for_mask"] == "false", f"{spec.role}: invisible obstacle eligible for mask", errors)
            _ensure(int(row["candidate_pixel_count"]) == 0, f"{spec.role}: invisible obstacle wrote candidates", errors)

    planned_dom = by_id["M4D_PLANNED_DOMINANT_VISIBLE"]
    state_dom = by_id["M4D_STATE_DOMINANT_VISIBLE"]
    shared = by_id["M4D_SHARED_RISK_VISIBLE"]
    low = by_id["M4D_LOW_RISK_VISIBLE"]
    _ensure(_float(planned_dom, "planned_risk") - _float(planned_dom, "state_risk") >= VISIBILITY_DOMINANCE_MARGIN, "planned-dominant margin failed", errors)
    _ensure(_float(state_dom, "state_risk") - _float(state_dom, "planned_risk") >= VISIBILITY_DOMINANCE_MARGIN, "state-dominant margin failed", errors)
    _ensure(DOMINANCE_MARGIN >= VISIBILITY_DOMINANCE_MARGIN, "configured strict margin must remain documented above runtime margin", errors)
    _ensure(_float(shared, "planned_risk") >= SHARED_RISK_MIN and _float(shared, "state_risk") >= SHARED_RISK_MIN, "shared role risks not both nonzero enough", errors)
    high_values = sorted([_float(planned_dom, "combined_risk"), _float(state_dom, "combined_risk"), _float(shared, "combined_risk")], reverse=True)
    _ensure(_float(low, "combined_risk") < high_values[1], "low risk is not below at least two high-risk roles", errors)
    _ensure(by_id["M4D_PARTIAL_VISIBLE"]["actual_visibility"] == VisibilityStatus.PARTIALLY_VISIBLE.value, "partial role not partial", errors)

    front_id, back_id = OVERLAP_PAIR
    overlap = overlap_pixels(polygon_pixels_by_id[front_id], polygon_pixels_by_id[back_id])
    _ensure(len(overlap) > 0, "overlap pair has no shared projected pixels", errors)
    if overlap:
        u, v = sorted(overlap)[len(overlap) // 2]
        covering_ids = [obstacle_id for obstacle_id, pixels in polygon_pixels_by_id.items() if (u, v) in pixels]
        for channel, mask in saved_masks.items():
            field = f"{channel}_risk" if channel != "combined" else "combined_risk"
            expected = max(_float(by_id[obstacle_id], field) for obstacle_id in covering_ids)
            _ensure(abs(mask.get(u, v) - expected) <= RISK_TOLERANCE, f"{channel}: overlap max mismatch", errors)

    exclusive_checks = {}
    for spec in OBSTACLE_SPECS:
        if not spec.require_exclusive_pixel:
            continue
        target = polygon_pixels_by_id[spec.obstacle_id]
        others = [pixels for obstacle_id, pixels in polygon_pixels_by_id.items() if obstacle_id != spec.obstacle_id]
        exclusive = exclusive_pixels(target, others)
        exclusive_checks[spec.role] = len(exclusive)
        _ensure(len(exclusive) > 0, f"{spec.role}: no exclusive pixel", errors)
        if exclusive:
            u, v = sorted(exclusive)[0]
            row = by_id[spec.obstacle_id]
            _ensure(abs(saved_masks["planned"].get(u, v) - _float(row, "planned_risk")) <= RISK_TOLERANCE, f"{spec.role}: planned exclusive binding mismatch", errors)
            _ensure(abs(saved_masks["state"].get(u, v) - _float(row, "state_risk")) <= RISK_TOLERANCE, f"{spec.role}: state exclusive binding mismatch", errors)
            _ensure(abs(saved_masks["combined"].get(u, v) - _float(row, "combined_risk")) <= RISK_TOLERANCE, f"{spec.role}: combined exclusive binding mismatch", errors)

    rgb_metrics = {}
    if frame_path.exists():
        image = Image.open(frame_path).convert("RGB")
        _ensure(image.size == (EXPECTED_CAMERA_WIDTH_PX, EXPECTED_CAMERA_HEIGHT_PX), "frame size mismatch", errors)
        for spec in OBSTACLE_SPECS:
            if not spec.auto_color_validation:
                continue
            row = by_id[spec.obstacle_id]
            color_pixels = _mask_from_color(image, spec.target_rgb)
            observed_bbox = _bbox_from_pixels(color_pixels)
            projected_bbox = _bbox_from_row(row)
            projected_mask = _polygon_mask(image.size, _polygon_from_row(row))
            bbox_iou = _bbox_iou(projected_bbox, observed_bbox)
            polygon_iou = _mask_iou(projected_mask, color_pixels)
            center_error = _center_error(projected_bbox, observed_bbox)
            rgb_metrics[spec.role] = {
                "visible_color_pixels": len(color_pixels),
                "bbox_iou": bbox_iou,
                "polygon_iou": polygon_iou,
                "center_error_px": center_error,
            }
            if row["actual_visibility"] == VisibilityStatus.FULLY_VISIBLE.value:
                bbox_threshold = 0.35 if spec.role == "LOW_RISK_VISIBLE" else FULLY_VISIBLE_BBOX_IOU_MIN
                polygon_threshold = 0.35 if spec.role == "LOW_RISK_VISIBLE" else FULLY_VISIBLE_POLYGON_IOU_MIN
                center_threshold = 7.0 if spec.role == "LOW_RISK_VISIBLE" else FULLY_VISIBLE_CENTER_ERROR_PX_MAX
                _ensure(bbox_iou >= bbox_threshold, f"{spec.role}: bbox IoU too low", errors)
                _ensure(polygon_iou >= polygon_threshold, f"{spec.role}: polygon IoU too low", errors)
                _ensure(center_error <= center_threshold, f"{spec.role}: center error too high", errors)
            elif row["actual_visibility"] == VisibilityStatus.PARTIALLY_VISIBLE.value:
                bbox_threshold = 0.25 if spec.role == "PARTIAL_VISIBLE" else PARTIAL_BBOX_IOU_MIN
                polygon_threshold = 0.30 if spec.role == "PARTIAL_VISIBLE" else PARTIAL_POLYGON_IOU_MIN
                _ensure(bbox_iou >= bbox_threshold, f"{spec.role}: partial bbox IoU too low", errors)
                _ensure(polygon_iou >= polygon_threshold, f"{spec.role}: partial polygon IoU too low", errors)
                _ensure(center_error <= PARTIAL_CENTER_ERROR_PX_MAX, f"{spec.role}: partial center error too high", errors)

    _validate_png_quantization(PROJECT_ROOT / M4_RESULTS_DIR, masks_payload, errors)
    metrics = {
        "episode_id": rows[0]["episode_id"],
        "snapshot_time_s": float(rows[0]["snapshot_time_s"]),
        "planned_nonzero_pixels": saved_masks["planned"].nonzero_pixel_count,
        "state_nonzero_pixels": saved_masks["state"].nonzero_pixel_count,
        "combined_nonzero_pixels": saved_masks["combined"].nonzero_pixel_count,
        "trajectory_disagreement_m": compute_trajectory_disagreement(planned, state),
        "overlap_pixels": len(overlap),
        "exclusive_pixels": exclusive_checks,
        "rgb_metrics": rgb_metrics,
        "role_risks": {row["role"]: {"planned": _float(row, "planned_risk"), "state": _float(row, "state_risk"), "combined": _float(row, "combined_risk"), "visibility": row["actual_visibility"]} for row in rows},
    }
    return errors, metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", nargs="?", type=Path)
    args = parser.parse_args()
    csv_path = args.csv_path or _latest_csv()
    errors, metrics = validate(csv_path if csv_path.is_absolute() else PROJECT_ROOT / csv_path)
    print(f"m4d_validator csv={csv_path}")
    print(json.dumps(metrics, indent=2, sort_keys=True))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("m4d_validator: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
