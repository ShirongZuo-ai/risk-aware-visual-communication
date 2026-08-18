import ast
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_controller_has_no_m9_or_hidden_geometry_imports():
    path=ROOT/"simulator/controllers/cvc_p1_runner/cvc_p1_runner.py"
    tree=ast.parse(path.read_text(encoding="utf-8"))
    modules={n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
    assert not any(m and ("m9" in m or "ground_truth" in m) for m in modules)

def test_runner_has_required_development_scenarios():
    source=(ROOT/"scripts/run_cvc_p1_webots.py").read_text(encoding="utf-8")
    for name in ("straight_obstacle","turning_approach","turn_toward_danger","turn_away_danger","safe_pass","near_turn_appearance","command_transition","distractor"):
        assert name in source

def test_world_uses_real_camera():
    source=(ROOT/"simulator/worlds/cvc_p1_runner.wbt").read_text(encoding="utf-8")
    assert "camera_width 160" in source and 'controller "cvc_p1_runner"' in source
