from PIL import Image, ImageDraw
import pytest

from communication.cvc_camera import (assess_control_frame, control_is_image_dependent,
                                      webots_bgra_to_rgb)


def test_webots_bgra_conversion_preserves_rgb_channel_identity():
    # Webots bytes are B,G,R,A for each pixel.
    image = webots_bgra_to_rgb(bytes([3, 2, 1, 255, 30, 20, 10, 255]), 2, 1)
    assert list(image.getdata()) == [(1, 2, 3), (10, 20, 30)]


@pytest.mark.parametrize("raw", [None, b"", bytes(15), bytes(17)])
def test_webots_conversion_rejects_missing_or_malformed_buffers(raw):
    with pytest.raises(ValueError):
        webots_bgra_to_rgb(raw, 2, 2)


def test_acceptance_rejects_black_and_uniform_frames():
    black = assess_control_frame(Image.new("RGB", (160, 120), "black"))
    uniform = assess_control_frame(Image.new("RGB", (160, 120), (80, 80, 80)))
    assert not black.accepted and black.reason == "underexposed_or_black"
    assert not uniform.accepted and uniform.reason == "spatially_uniform"


def test_lit_control_scene_is_usable_and_pixel_counterfactual_changes_control():
    obstacle = Image.new("RGB", (160, 120), (45, 70, 45))
    ImageDraw.Draw(obstacle).rectangle((120, 55, 150, 110), fill=(230, 15, 15))
    clear = Image.new("RGB", (160, 120), (45, 70, 45))
    accepted = assess_control_frame(obstacle)
    assert accepted.accepted and accepted.obstacle.detected
    assert control_is_image_dependent(obstacle, clear)
