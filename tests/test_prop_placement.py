"""Placement/size accuracy of props, calibrated against the real sample scene.

Ground truth (verified by hand from samples/Sceneforclaude.hcw geometry):
* the SOFA is a freestanding prop backed flush against the rear wall (UE
  Y=+240), length running parallel to it, facing the characters/camera;
* the DOOROPEN is a GenericSet snapped INTO the left wall (UE X=-320,
  snapPath references the wall), opening 70 cm = 100 cm recipe x 0.7
  objectScale, with the open panel swinging into the room.

These pin the two prop-orientation conventions (freestanding angle = back
direction; wall-snapped angle = wall direction) and the mirrored local frame.
"""

import math
import os

import pytest

from virtualsetmaker.emit.unreal_python import _bake_parts, _scene_payload
from virtualsetmaker.parse import parse_file

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "samples", "Sceneforclaude.hcw")
pytestmark = pytest.mark.skipif(not os.path.exists(SAMPLE), reason="sample .hcw not present")

BACK_WALL_Y = 240.0
LEFT_WALL_X = -320.0


def _payload_props():
    scene = parse_file(SAMPLE)
    payload = _scene_payload(scene)
    return {p["label"]: p for p in payload["props"]}


def _footprint(prop):
    xs, ys = [], []
    for part in prop["parts"]:
        cx, cy, _cz = part["loc"]
        sx, sy = part["scale"][0] * 100.0, part["scale"][1] * 100.0
        yaw = math.radians(part["rot"][1])
        ex = abs(sx / 2 * math.cos(yaw)) + abs(sy / 2 * math.sin(yaw))
        ey = abs(sx / 2 * math.sin(yaw)) + abs(sy / 2 * math.cos(yaw))
        xs += [cx - ex, cx + ex]
        ys += [cy - ey, cy + ey]
    return min(xs), max(xs), min(ys), max(ys)


def test_door_is_wall_snapped_and_sofa_is_not():
    scene = parse_file(SAMPLE)
    by_kind = {p.kind: p for p in scene.props}
    assert by_kind["DOOROPEN"].wall_snapped is True
    assert by_kind["SOFA"].wall_snapped is False


def test_sofa_backs_flush_against_the_rear_wall():
    sofa = _payload_props()["SOFA"]
    x0, x1, y0, y1 = _footprint(sofa)
    # Back edge flush at the wall (the 0.3 cm is the scene's own placement
    # precision), length along X, entirely inside the room.
    assert y1 == pytest.approx(BACK_WALL_Y, abs=1.0)
    assert x1 - x0 == pytest.approx(180.0, abs=1.0)  # arm-to-arm width
    assert y1 - y0 == pytest.approx(80.0, abs=1.0)  # seat depth
    assert y0 > 100.0  # nothing pokes through or beyond the wall


def test_sofa_backrest_is_on_the_wall_side():
    sofa = _payload_props()["SOFA"]
    backrest = sofa["parts"][3]  # recipe order: seat, arm, arm, backrest
    seat = sofa["parts"][0]
    assert backrest["loc"][1] > seat["loc"][1]  # toward +Y = toward the wall


def test_door_frame_sits_in_the_left_wall():
    door = _payload_props()["DOOROPEN"]
    jambs = door["parts"][0:2]
    for jamb in jambs:
        assert jamb["loc"][0] == pytest.approx(LEFT_WALL_X, abs=0.1)
    # Opening = 100 cm recipe spacing x 0.7 objectScale.
    spread = abs(jambs[0]["loc"][1] - jambs[1]["loc"][1])
    assert spread == pytest.approx(70.0, abs=0.1)


def test_door_panel_swings_into_the_room():
    door = _payload_props()["DOOROPEN"]
    panel = door["parts"][3]
    assert panel["loc"][0] > LEFT_WALL_X  # inside the room, not through the wall


def test_bake_mirror_flips_local_y_offsets_and_part_yaw():
    parts = [
        {"shape": "cube", "offset": [0.0, 30.0, 10.0], "size": [50, 50, 20], "rot": [0, 15, 5]}
    ]
    plain = _bake_parts(parts, (0.0, 0.0), 0.0, (1.0, 1.0))
    mirrored = _bake_parts(parts, (0.0, 0.0), 0.0, (1.0, 1.0), mirror_y=True)
    assert plain[0]["loc"][1] == 30.0
    assert mirrored[0]["loc"][1] == -30.0
    assert plain[0]["rot"] == [0, 15, 5]
    assert mirrored[0]["rot"] == [0, -15, -5]
