from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

from PIL import Image

from communication.cvc_p3_codec import decode_p3_packet, encode_p3_packet
from communication.cvc_p6_allocator import MirroredHoldingChannel, image_sha256


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "simulator" / "controllers" / "cvc_q2_runner" / "cvc_q2_runner.py"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_sender_modules_have_no_evaluator_or_webots_import() -> None:
    for path in (ROOT / "communication" / "cvc_q2_allocator.py",
                 ROOT / "navigation" / "cvc_q1_local_planner.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        assert not any(module and (module.startswith("evaluation") or module == "controller") for module in modules)


def test_evaluator_truth_is_after_actuation_in_q2_controller() -> None:
    source = CONTROLLER.read_text(encoding="utf-8")
    marker = source.index("# Evaluator-only Webots truth")
    assert source.index("actual_plan =") < source.index("left.setVelocity") < marker
    forbidden = ("self_node.getPosition()", "getContactPoints(True)")
    assert all(token not in source[:marker] for token in forbidden)
    assert all(token in source[marker:] for token in forbidden)


def test_current_hypothetical_decode_and_held_mirror_consistency() -> None:
    image = Image.new("RGB", (160, 120), (121, 44, 19))
    packet = encode_p3_packet(image, 32, .2, "A1", 45, 24000)
    current, metadata = decode_p3_packet(packet.payload)
    channel = MirroredHoldingChannel()
    received, mirror = channel.step(32, packet.payload)
    assert metadata["timestamp_ms"] == 32
    assert image_sha256(current) == image_sha256(received.image) == image_sha256(mirror.image)
    held, held_mirror = channel.step(64, None)
    assert held.held and held.image_age_ms == 32
    assert image_sha256(held.image) == image_sha256(held_mirror.image)


def test_q1_readiness_protected_inputs_are_unchanged() -> None:
    manifest = json.loads((ROOT / "results" / "cvc_q1_support_readiness" / "manifest.json").read_text())
    mapping = {
        "support_grid": ROOT / "config" / "cvc_q1_support_grid.json",
        "planner": ROOT / "config" / "cvc_q1_planner_v2.json",
        "range_calibration": ROOT / "results" / "cvc_q1_range_calibration" / "calibration_results.json",
        "fresh_vision_qualification": ROOT / "results" / "cvc_q1_full_vision_v2" / "qualification.json",
        "support_qualification": ROOT / "results" / "cvc_q1_support_qualification" / "qualification.json",
        "world": ROOT / "simulator" / "worlds" / "cvc_q1_runner.wbt",
        "controller": ROOT / "simulator" / "controllers" / "cvc_q1_runner" / "cvc_q1_runner.py",
        "planner_implementation": ROOT / "navigation" / "cvc_q1_local_planner.py",
        "visual_geometry_implementation": ROOT / "communication" / "cvc_q1_visual_geometry.py",
        "obstacle_memory_implementation": ROOT / "communication" / "cvc_q1_obstacle_memory.py",
    }
    assert {name: sha(path) for name, path in mapping.items()} == manifest["protected_sha256"]
