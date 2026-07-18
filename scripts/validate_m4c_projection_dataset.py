"""Validate the Milestone 4C Webots projection dataset against the RGB frame."""

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
from perception.camera_projection import polygons_bounding_boxes_overlap  # noqa: E402
from simulator.m4c_config import (  # noqa: E402
    COLOR_DISTANCE_THRESHOLD,
    EXPECTED_CAMERA_HEIGHT_PX,
    EXPECTED_CAMERA_WIDTH_PX,
    FULLY_VISIBLE_BBOX_IOU_MIN,
    FULLY_VISIBLE_CENTER_ERROR_PX_MAX,
    FULLY_VISIBLE_POLYGON_IOU_MIN,
    FULLY_VISIBLE_SIZE_REL_ERROR_MAX,
    M4_LOG_DIR,
    MIN_ABSENT_COLOR_PIXELS,
    OBSTACLE_SPECS,
    PARTIAL_BBOX_IOU_MIN,
    PARTIAL_CENTER_ERROR_PX_MAX,
    PARTIAL_POLYGON_IOU_MIN,
    PARTIAL_SIZE_REL_ERROR_MAX,
    obstacle_spec_by_role,
)


def _latest_csv() -> Path:
    candidates = sorted((PROJECT_ROOT / M4_LOG_DIR).glob("projection_validation_episode_*.csv"))
    if not candidates:
        raise FileNotFoundError("No M4C projection CSV found")
    return candidates[-1]


def _load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _parse_polygon(value: str) -> list[tuple[float, float]]:
    if not value:
        return []
    return [(float(item[0]), float(item[1])) for item in json.loads(value)]


def _float(row: dict[str, str], field: str) -> float:
    return float(row[field])


def _bbox(row: dict[str, str]) -> tuple[float, float, float, float] | None:
    if not row["bbox_min_u"]:
        return None
    return (_float(row, "bbox_min_u"), _float(row, "bbox_min_v"), _float(row, "bbox_max_u"), _float(row, "bbox_max_v"))


def _mask_from_color(image: Image.Image, target: tuple[int, int, int], threshold: float) -> list[tuple[int, int]]:
    pixels = image.convert("RGB").load()
    width, height = image.size
    threshold_sq = threshold * threshold
    matches: list[tuple[int, int]] = []
    for y in range(height):
        for x in range(width):
            red, green, blue = pixels[x, y]
            distance_sq = (red - target[0]) ** 2 + (green - target[1]) ** 2 + (blue - target[2]) ** 2
            if distance_sq <= threshold_sq:
                matches.append((x, y))
    return matches


def _bbox_from_points(points: list[tuple[int, int]]) -> tuple[float, float, float, float] | None:
    if not points:
        return None
    return (float(min(x for x, _y in points)), float(min(y for _x, y in points)), float(max(x for x, _y in points)), float(max(y for _x, y in points)))


def _bbox_iou(left: tuple[float, float, float, float] | None, right: tuple[float, float, float, float] | None) -> float:
    if left is None or right is None:
        return 0.0
    l_min_u, l_min_v, l_max_u, l_max_v = left
    r_min_u, r_min_v, r_max_u, r_max_v = right
    inter_min_u = max(l_min_u, r_min_u)
    inter_min_v = max(l_min_v, r_min_v)
    inter_max_u = min(l_max_u, r_max_u)
    inter_max_v = min(l_max_v, r_max_v)
    if inter_max_u < inter_min_u or inter_max_v < inter_min_v:
        return 0.0
    intersection = (inter_max_u - inter_min_u + 1.0) * (inter_max_v - inter_min_v + 1.0)
    left_area = (l_max_u - l_min_u + 1.0) * (l_max_v - l_min_v + 1.0)
    right_area = (r_max_u - r_min_u + 1.0) * (r_max_v - r_min_v + 1.0)
    return intersection / (left_area + right_area - intersection)


def _center(bbox: tuple[float, float, float, float] | None) -> tuple[float, float] | None:
    if bbox is None:
        return None
    return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)


def _center_error(left: tuple[float, float, float, float] | None, right: tuple[float, float, float, float] | None) -> float:
    left_center = _center(left)
    right_center = _center(right)
    if left_center is None or right_center is None:
        return math.inf
    return math.hypot(left_center[0] - right_center[0], left_center[1] - right_center[1])


def _size_rel_errors(projected: tuple[float, float, float, float] | None, observed: tuple[float, float, float, float] | None) -> tuple[float, float]:
    if projected is None or observed is None:
        return (math.inf, math.inf)
    p_width = max(1e-9, projected[2] - projected[0] + 1.0)
    p_height = max(1e-9, projected[3] - projected[1] + 1.0)
    o_width = observed[2] - observed[0] + 1.0
    o_height = observed[3] - observed[1] + 1.0
    return (abs(p_width - o_width) / p_width, abs(p_height - o_height) / p_height)


def _polygon_mask(size: tuple[int, int], polygon: list[tuple[float, float]]) -> Image.Image:
    mask = Image.new("1", size, 0)
    if len(polygon) >= 3:
        draw = ImageDraw.Draw(mask)
        draw.polygon([(round(u), round(v)) for u, v in polygon], fill=1)
    return mask


def _points_mask(size: tuple[int, int], points: list[tuple[int, int]]) -> Image.Image:
    mask = Image.new("1", size, 0)
    if points:
        pix = mask.load()
        for x, y in points:
            pix[x, y] = 1
    return mask


def _mask_iou(left: Image.Image, right: Image.Image) -> float:
    left_pixels = left.load()
    right_pixels = right.load()
    width, height = left.size
    intersection = 0
    union = 0
    for y in range(height):
        for x in range(width):
            l_value = bool(left_pixels[x, y])
            r_value = bool(right_pixels[x, y])
            if l_value and r_value:
                intersection += 1
            if l_value or r_value:
                union += 1
    if union == 0:
        return 0.0
    return intersection / union


def _ensure(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate(csv_path: Path) -> tuple[list[str], dict[str, dict[str, float | int | str]]]:
    rows = _load_rows(csv_path)
    errors: list[str] = []
    metrics: dict[str, dict[str, float | int | str]] = {}
    specs = obstacle_spec_by_role()

    _ensure(len(rows) == len(OBSTACLE_SPECS), f"expected {len(OBSTACLE_SPECS)} rows, got {len(rows)}", errors)
    roles = [row.get("role", "") for row in rows]
    _ensure(set(roles) == set(specs), f"roles mismatch: {roles}", errors)
    _ensure(len(set(roles)) == len(roles), "roles are not unique", errors)

    if not rows:
        return errors, metrics
    frame_path = PROJECT_ROOT / rows[0]["frame_path"]
    _ensure("Downloads" not in str(frame_path), f"frame path contains Downloads: {frame_path}", errors)
    _ensure(frame_path.exists(), f"missing frame: {frame_path}", errors)
    if not frame_path.exists():
        return errors, metrics
    image = Image.open(frame_path).convert("RGB")
    _ensure(image.size == (EXPECTED_CAMERA_WIDTH_PX, EXPECTED_CAMERA_HEIGHT_PX), f"unexpected image size: {image.size}", errors)

    by_role = {row["role"]: row for row in rows}
    projected_by_role = {}
    for row in rows:
        role = row["role"]
        spec = specs[role]
        projected_bbox = _bbox(row)
        clipped_polygon = _parse_polygon(row["clipped_polygon"])
        status = row["actual_visibility"]
        projected_by_role[role] = projected_bbox

        _ensure(row["expected_visibility"] == spec.expected_visibility.value, f"{role}: expected_visibility does not match config", errors)
        _ensure(status == spec.expected_visibility.value, f"{role}: expected {spec.expected_visibility.value}, got {status}", errors)
        _ensure(int(row["camera_width_px"]) == EXPECTED_CAMERA_WIDTH_PX, f"{role}: bad camera width", errors)
        _ensure(int(row["camera_height_px"]) == EXPECTED_CAMERA_HEIGHT_PX, f"{role}: bad camera height", errors)
        _ensure(0.0 <= float(row["truncation_fraction"]) <= 1.0, f"{role}: truncation outside [0,1]", errors)
        for field in ("minimum_depth_m", "maximum_depth_m", "projected_area_px"):
            if row[field]:
                _ensure(math.isfinite(float(row[field])), f"{role}: {field} is not finite", errors)
        if clipped_polygon:
            for u, v in clipped_polygon:
                _ensure(0.0 <= u <= EXPECTED_CAMERA_WIDTH_PX - 1 and 0.0 <= v <= EXPECTED_CAMERA_HEIGHT_PX - 1, f"{role}: clipped point outside image", errors)
            if projected_bbox is not None:
                for u, v in clipped_polygon:
                    _ensure(projected_bbox[0] - 1e-6 <= u <= projected_bbox[2] + 1e-6, f"{role}: bbox misses clipped u", errors)
                    _ensure(projected_bbox[1] - 1e-6 <= v <= projected_bbox[3] + 1e-6, f"{role}: bbox misses clipped v", errors)

        color_points = _mask_from_color(image, spec.target_rgb, COLOR_DISTANCE_THRESHOLD)
        observed_bbox = _bbox_from_points(color_points)
        projected_mask = _polygon_mask(image.size, clipped_polygon)
        observed_mask = _points_mask(image.size, color_points)
        bbox_iou = _bbox_iou(projected_bbox, observed_bbox)
        polygon_iou = _mask_iou(projected_mask, observed_mask)
        center_error = _center_error(projected_bbox, observed_bbox)
        width_rel, height_rel = _size_rel_errors(projected_bbox, observed_bbox)
        metrics[role] = {
            "visibility": status,
            "visible_color_pixels": len(color_points),
            "bbox_iou": bbox_iou,
            "polygon_iou": polygon_iou,
            "center_error_px": center_error,
            "width_relative_error": width_rel,
            "height_relative_error": height_rel,
        }

        if spec.auto_color_validation and status in (VisibilityStatus.FULLY_VISIBLE.value, VisibilityStatus.PARTIALLY_VISIBLE.value):
            _ensure(observed_bbox is not None, f"{role}: no observed color bbox", errors)
            if status == VisibilityStatus.FULLY_VISIBLE.value:
                _ensure(bbox_iou >= FULLY_VISIBLE_BBOX_IOU_MIN, f"{role}: bbox IoU {bbox_iou:.3f} below threshold", errors)
                _ensure(polygon_iou >= FULLY_VISIBLE_POLYGON_IOU_MIN, f"{role}: polygon IoU {polygon_iou:.3f} below threshold", errors)
                _ensure(center_error <= FULLY_VISIBLE_CENTER_ERROR_PX_MAX, f"{role}: center error {center_error:.3f}px too high", errors)
                _ensure(width_rel <= FULLY_VISIBLE_SIZE_REL_ERROR_MAX, f"{role}: width relative error {width_rel:.3f} too high", errors)
                _ensure(height_rel <= FULLY_VISIBLE_SIZE_REL_ERROR_MAX, f"{role}: height relative error {height_rel:.3f} too high", errors)
            else:
                _ensure(bbox_iou >= PARTIAL_BBOX_IOU_MIN, f"{role}: partial bbox IoU {bbox_iou:.3f} below threshold", errors)
                _ensure(polygon_iou >= PARTIAL_POLYGON_IOU_MIN, f"{role}: partial polygon IoU {polygon_iou:.3f} below threshold", errors)
                _ensure(center_error <= PARTIAL_CENTER_ERROR_PX_MAX, f"{role}: partial center error {center_error:.3f}px too high", errors)
                _ensure(width_rel <= PARTIAL_SIZE_REL_ERROR_MAX, f"{role}: partial width error {width_rel:.3f} too high", errors)
                _ensure(height_rel <= PARTIAL_SIZE_REL_ERROR_MAX, f"{role}: partial height error {height_rel:.3f} too high", errors)
                _ensure(float(row["truncation_fraction"]) > 0.0, f"{role}: partial truncation is not positive", errors)
        if status in (VisibilityStatus.OUTSIDE_FRUSTUM.value, VisibilityStatus.BEHIND_CAMERA.value):
            _ensure(not clipped_polygon, f"{role}: invisible role has clipped polygon", errors)
            _ensure(len(color_points) <= MIN_ABSENT_COLOR_PIXELS, f"{role}: invisible color appears in frame ({len(color_points)} px)", errors)

    cx = float(rows[0]["cx_px"])
    center_bbox = _bbox(by_role["CENTER_VISIBLE"])
    left_bbox = _bbox(by_role["LEFT_VISIBLE"])
    right_bbox = _bbox(by_role["RIGHT_VISIBLE"])
    _ensure(center_bbox is not None and abs(_center(center_bbox)[0] - cx) <= 8.0, "CENTER_VISIBLE is not near principal u", errors)
    _ensure(left_bbox is not None and _center(left_bbox)[0] < cx, "LEFT_VISIBLE center is not left of principal point", errors)
    _ensure(right_bbox is not None and _center(right_bbox)[0] > cx, "RIGHT_VISIBLE center is not right of principal point", errors)
    _ensure(_bbox(by_role["NEAR_PLANE_INTERSECTION"]) is not None, "NEAR_PLANE_INTERSECTION has no valid projection", errors)
    _ensure(
        _bbox_iou(projected_by_role.get("DEPTH_OVERLAP_FRONT"), projected_by_role.get("DEPTH_OVERLAP_BACK")) > 0.0,
        "DEPTH_OVERLAP projected bboxes do not overlap",
        errors,
    )
    return errors, metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", nargs="?", type=Path, default=None)
    args = parser.parse_args()
    csv_path = args.csv_path or _latest_csv()
    errors, metrics = validate(csv_path)
    print(f"m4c_validator csv={csv_path}")
    print(json.dumps(metrics, indent=2, sort_keys=True))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("m4c_validator: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
