import json
import os

from virtualsetmaker.emit import build_script
from virtualsetmaker.parse.shotdesigner import parse_file

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "samples")
STATIC = os.path.join(SAMPLES, "Sceneforclaude.hcw")
MOVING = os.path.join(SAMPLES, "Camera_move_only.hcw")


def _payload(path, **parse_kw):
    script = build_script(parse_file(path, **parse_kw))
    return json.loads(script.split('SCENE = json.loads(r"""', 1)[1].split('"""', 1)[0])


def test_units_per_meter_scales_positions_not_camera_height():
    # 1 SD unit = 2 cm at 50 units/m, so positions double versus 100 units/m,
    # but the camera height is a real-world 1.5 m whatever the unit is.
    base = _payload(STATIC, units_per_meter=100.0)
    half = _payload(STATIC, units_per_meter=50.0)
    bk = base["cameras"][0]["keys"][0]["loc"]
    hk = half["cameras"][0]["keys"][0]["loc"]
    assert bk[0] != 0 and bk[1] != 0
    assert abs(hk[0] - 2 * bk[0]) < 1e-6
    assert abs(hk[1] - 2 * bk[1]) < 1e-6
    assert bk[2] == 150.0
    assert hk[2] == 150.0
    bx, _, _ = base["actors"][0]["loc"]
    hx, _, _ = half["actors"][0]["loc"]
    assert bx != 0 and abs(hx - 2 * bx) < 1e-6


def test_moving_camera_uses_configured_focal_length():
    cam = _payload(MOVING, focal_length_mm=85.0)["cameras"][0]
    assert len(cam["keys"]) > 1
    assert cam["focal0"] == 85.0
    assert [k["focal"] for k in cam["keys"]] == [85.0] * len(cam["keys"])
    assert cam["focal_animated"] is False
