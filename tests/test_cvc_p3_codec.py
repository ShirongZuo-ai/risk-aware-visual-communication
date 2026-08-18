from __future__ import annotations

from PIL import Image, ImageDraw
import pytest

from communication.cvc_p2_perception import detect_red_obstacle
from communication.cvc_p3_codec import P3HoldingReceiver, decode_p3_packet, encode_p3_packet


def fixture() -> Image.Image:
    image = Image.new("RGB", (160, 120), (180, 180, 180))
    ImageDraw.Draw(image).rectangle((64, 42, 96, 91), fill=(230, 8, 8))
    return image


@pytest.mark.parametrize("target", [12000, 18000, 24000])
def test_compact_packet_has_exact_real_wire_cost_and_decodes(target: int) -> None:
    packet = encode_p3_packet(fixture(), 64, 0.2, "A1", 45, target)
    assert len(packet.payload) == target
    assert packet.content_bytes + packet.metadata_bytes + packet.padding_bytes == target
    decoded, metadata = decode_p3_packet(packet.payload)
    assert metadata["policy"] == "A1"
    assert decoded.size == fixture().size
    assert detect_red_obstacle(decoded).detected


def test_receiver_holds_last_decoded_frame_and_rejects_missing_startup() -> None:
    receiver = P3HoldingReceiver()
    with pytest.raises(RuntimeError):
        receiver.step(0, None)
    packet = encode_p3_packet(fixture(), 64, 0.2, "A0", 45, 12000)
    first = receiver.step(64, packet.payload)
    held = receiver.step(96, None)
    assert not first.held and held.held
    assert held.image_age_ms == 32
