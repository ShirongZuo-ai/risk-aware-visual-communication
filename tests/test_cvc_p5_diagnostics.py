from __future__ import annotations

from PIL import Image, ImageDraw

from communication.cvc_p2_perception import detect_red_obstacle
from communication.cvc_p5_diagnostics import control_sensitivity, perception_novelty, visual_novelty


def frame(box: tuple[int, int, int, int]) -> Image.Image:
    image = Image.new("RGB", (160, 120), (180, 180, 180))
    ImageDraw.Draw(image).rectangle(box, fill=(230, 8, 8))
    return image


def test_identical_decoded_images_have_zero_novelty() -> None:
    image = frame((65, 45, 95, 85))
    visual = visual_novelty(image, image)
    obstacle = detect_red_obstacle(image)
    perception = perception_novelty(obstacle, obstacle)
    control = control_sensitivity(obstacle, obstacle, 5.0)
    assert visual.pixel_mae == visual.pixel_rmse == visual.structural_difference == 0.0
    assert visual.changed_pixel_fraction == 0.0
    assert perception.combined_l2 == 0.0
    assert control.control_l2 == 0.0


def test_moved_component_changes_visual_perception_and_control_continuously() -> None:
    held, current = frame((35, 45, 65, 85)), frame((95, 45, 125, 85))
    visual = visual_novelty(held, current)
    old, new = detect_red_obstacle(held), detect_red_obstacle(current)
    perception = perception_novelty(old, new)
    control = control_sensitivity(old, new, 5.0)
    assert visual.pixel_mae > 0 and visual.structural_difference > 0
    assert perception.delta_bearing > 0 and perception.combined_l2 > 0
    assert control.control_l2 > 0 and control.steering_delta > 0
