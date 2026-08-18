"""CVC-P2 decoded-pixel perception/controller development checks."""
from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw

from communication.cvc_p2_perception import detect_red_obstacle, visual_wheel_command


def _fixture(boxes: list[tuple[int, int, int, int]]) -> Image.Image:
    image = Image.new("RGB", (160, 120), (210, 210, 210))
    draw = ImageDraw.Draw(image)
    for box in boxes:
        draw.rectangle(box, fill=(210, 20, 20))
    return image


def _jpeg(image: Image.Image, quality: int = 25) -> Image.Image:
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=quality, subsampling=0)
    buffer.seek(0)
    decoded = Image.open(buffer).convert("RGB")
    decoded.load()
    return decoded


def test_component_fixtures_cover_position_scale_fragments_and_absence() -> None:
    left = detect_red_obstacle(_fixture([(12, 45, 35, 82)]))
    center = detect_red_obstacle(_fixture([(68, 45, 91, 82)]))
    right = detect_red_obstacle(_fixture([(124, 45, 147, 82)]))
    small = detect_red_obstacle(_fixture([(72, 54, 87, 73)]))
    large = detect_red_obstacle(_fixture([(54, 34, 105, 91)]))
    fragments = detect_red_obstacle(_fixture([(18, 50, 34, 72), (70, 35, 105, 88), (132, 62, 141, 71)]))
    absent = detect_red_obstacle(_fixture([]))

    assert left.bearing_normalized < -0.4 < center.bearing_normalized + 0.4
    assert abs(center.bearing_normalized) < 0.05
    assert right.bearing_normalized > 0.4
    assert large.proximity > small.proximity > 0.0
    assert fragments.component_count == 3
    assert fragments.bbox_xyxy == (70, 35, 106, 89)
    assert fragments.confidence > 0.9
    assert not absent.detected and absent.bbox_xyxy is None


def test_jpeg_decode_preserves_component_direction_and_scale_order() -> None:
    for quality in (90, 45, 15):
        left = detect_red_obstacle(_jpeg(_fixture([(12, 42, 39, 84)]), quality))
        right = detect_red_obstacle(_jpeg(_fixture([(120, 42, 147, 84)]), quality))
        small = detect_red_obstacle(_jpeg(_fixture([(72, 54, 87, 73)]), quality))
        large = detect_red_obstacle(_jpeg(_fixture([(54, 34, 105, 91)]), quality))
        assert left.detected and right.detected and small.detected and large.detected
        assert left.bearing_normalized < 0.0 < right.bearing_normalized
        assert large.proximity > small.proximity


def test_controller_uses_bearing_for_avoidance_and_proximity_for_braking() -> None:
    left = detect_red_obstacle(_fixture([(5, 30, 55, 100)]))
    right = detect_red_obstacle(_fixture([(104, 30, 154, 100)]))
    near = detect_red_obstacle(_fixture([(25, 10, 134, 105)]))
    left_wheels = visual_wheel_command(left, cruise=3.5)
    right_wheels = visual_wheel_command(right, cruise=3.5)
    near_wheels = visual_wheel_command(near, cruise=3.5)
    assert left_wheels[0] < left_wheels[1]
    assert right_wheels[0] > right_wheels[1]
    assert near_wheels == (0.0, 0.0)


def test_all_components_have_complete_measurements() -> None:
    result = detect_red_obstacle(_fixture([(8, 20, 25, 45), (70, 35, 105, 88), (130, 70, 139, 79)]))
    assert len(result.components) == 3
    assert [component.area for component in result.components] == sorted(
        (component.area for component in result.components), reverse=True
    )
    assert all(component.bbox_xyxy and component.centroid_xy for component in result.components)
    assert all(-1.0 <= component.bearing_normalized <= 1.0 for component in result.components)
