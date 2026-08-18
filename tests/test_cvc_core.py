import unittest
from PIL import Image, ImageDraw

from communication.cvc_perception import detect_red_obstacle, visual_wheel_command
from communication.cvc_protocol import (AllocationDecision, CausalBudgetPolicy, HoldingReceiver,
                                         SenderObservation, decode_packet, encode_packet)


def scene(x0=65):
    image = Image.new("RGB", (160, 120), (40, 80, 40))
    ImageDraw.Draw(image).rectangle((x0, 55, x0 + 25, 110), fill=(230, 20, 20))
    return image


class CvcCoreTests(unittest.TestCase):
    def test_complete_wire_packet_is_exactly_padded_and_deterministic(self):
        obs = SenderObservation(320, scene(), 0.7)
        decision = AllocationDecision("A1", True, (60,) * 48, 50000)
        one, two = encode_packet(obs, decision), encode_packet(obs, decision)
        self.assertEqual(one.payload, two.payload)
        self.assertEqual(one.wire_bytes, 50000)
        self.assertEqual(one.content_bytes + one.metadata_bytes + one.padding_bytes, 50000)
        image, metadata = decode_packet(one.payload)
        self.assertEqual(image.size, (160, 120))
        self.assertEqual(metadata["policy"], "A1")

    def test_receiver_holds_only_last_decoded_frame_and_tracks_age(self):
        packet = encode_packet(SenderObservation(100, scene(), .2), AllocationDecision("U0", True, (42,) * 48, 50000))
        receiver = HoldingReceiver()
        fresh = receiver.step(100, packet.payload)
        held = receiver.step(164, None)
        self.assertFalse(fresh.held); self.assertTrue(held.held)
        self.assertEqual((fresh.image_age_ms, held.image_age_ms), (0, 64))
        self.assertEqual((fresh.wire_bytes, held.wire_bytes), (50000, 0))

    def test_policy_has_no_future_debt(self):
        policy = CausalBudgetPolicy("A1", bytes_per_tick=1000)
        first = policy.decide(.9, 2500)
        second = policy.decide(.9, 2500)
        third = policy.decide(.9, 2500)
        self.assertEqual([first.transmit, second.transmit, third.transmit], [False, False, True])
        self.assertGreaterEqual(policy.available_bytes, 0)
        self.assertEqual(policy.spent_bytes, 2500)

    def test_visual_detector_and_control_depend_on_decoded_pixels(self):
        center = detect_red_obstacle(scene(65)); right = detect_red_obstacle(scene(125))
        blank = detect_red_obstacle(Image.new("RGB", (160, 120), "black"))
        self.assertTrue(center.detected); self.assertTrue(right.detected); self.assertFalse(blank.detected)
        self.assertGreater(right.bearing_normalized, center.bearing_normalized)
        self.assertNotEqual(visual_wheel_command(right), visual_wheel_command(blank))

    def test_future_timestamp_and_underbudget_packet_are_rejected(self):
        obs = SenderObservation(200, scene(), .1)
        with self.assertRaises(ValueError):
            encode_packet(obs, AllocationDecision("U0", True, (42,) * 48, 10))
        packet = encode_packet(obs, AllocationDecision("U0", True, (42,) * 48, 50000))
        with self.assertRaises(ValueError):
            HoldingReceiver().step(199, packet.payload)


if __name__ == "__main__":
    unittest.main()
