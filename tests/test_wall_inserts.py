"""Wall-insert alignment and carving (doors/windows/openings) + set-piece yaw.

Modeled on the regression scene test_new_01.hcw: a SMALLWINDOW placed by hand
on a wall (empty <snapPath>, so the old snapPath-based detection called it
freestanding and twisted it 90°), and PRISONBARS standing free in the room.
GenericSet icons are authored width-along-X: their rotator angle is the direct
screen rotation, and wall inserts must snap flush onto the nearest parallel
wall segment and carve a real opening out of it.
"""

import math

import pytest

from virtualsetmaker.emit.unreal_python import _closest_parallel_yaw, _scene_payload
from virtualsetmaker.ir import Prop, Scene, Vec3, Wall
from virtualsetmaker.parse.shotdesigner import parse_string

# One horizontal wall along y = -4 m (UE: y = -400 cm), like the test scene's
# top wall. The screen->Unreal map is the identity for locations.
WALL_Y_CM = -400.0


def _scene(props, wall_points=((-5.6, -4.0), (6.0, -4.0)), closed=False):
    wall = Wall(id="w1", points=[Vec3(x, y) for x, y in wall_points], closed_loop=closed)
    return Scene(props=props, walls=[wall])


def _window(x_m=0.2, y_m=-4.0135, yaw=0.0):
    # 1.35 cm off the centerline, exactly like the hand-placed test-scene window.
    return Prop(id="win", name="SMALLWINDOW", kind="SMALLWINDOW",
                location=Vec3(x_m, y_m), yaw_deg=yaw, is_set=True)


def test_set_piece_yaw_is_angle_direct_even_without_snappath():
    # PRISONBARS in open space: no +90 freestanding twist for GenericSet.
    bars = Prop(id="b", name="PRISONBARS", kind="PRISONBARS",
                location=Vec3(1.0, 1.0), yaw_deg=0.0, is_set=True)
    payload = _scene_payload(Scene(props=[bars]))
    top_rail = payload["props"][0]["parts"][0]
    assert top_rail["rot"][1] == pytest.approx(0.0)


def test_freestanding_prop_keeps_the_plus_90_convention():
    sofa = Prop(id="s", name="SOFA", kind="SOFA", location=Vec3(0, 0), yaw_deg=0.0)
    payload = _scene_payload(Scene(props=[sofa]))
    seat = payload["props"][0]["parts"][0]
    assert seat["rot"][1] == pytest.approx(90.0)


def test_window_snaps_flush_onto_the_wall_centerline():
    payload = _scene_payload(_scene([_window()]))
    for part in payload["props"][0]["parts"]:
        assert part["loc"][1] == pytest.approx(WALL_Y_CM, abs=1e-6)
        assert part["rot"][1] % 360.0 == pytest.approx(0.0)


def test_window_carves_sill_lintel_and_side_pieces():
    payload = _scene_payload(_scene([_window()]))
    pieces = payload["wall_segments"]
    assert len(pieces) == 4  # left, sill, lintel, right

    def spans(p):
        return (p["loc"][2] - p["height"] / 2.0, p["loc"][2] + p["height"] / 2.0)

    by_height = sorted(pieces, key=lambda p: p["height"])
    lintel, sill = by_height[0], by_height[1]
    assert spans(lintel) == pytest.approx((220.0, 250.0))
    assert spans(sill) == pytest.approx((0.0, 80.0))
    # WINDOW recipe is 120 cm wide, centered on the prop at x = 20.
    for cut in (lintel, sill):
        assert cut["length"] == pytest.approx(120.0)
        assert cut["loc"][0] == pytest.approx(20.0)
    full = [p for p in pieces if p["height"] == pytest.approx(250.0)]
    assert len(full) == 2
    assert sum(p["length"] for p in full) == pytest.approx(1160.0 - 120.0)


def test_door_opening_has_no_sill():
    door = Prop(id="d", name="DOOROPEN", kind="DOOROPEN",
                location=Vec3(0.0, -4.0), yaw_deg=0.0, is_set=True)
    payload = _scene_payload(_scene([door]))
    pieces = payload["wall_segments"]
    assert len(pieces) == 3  # left, lintel, right
    lintel = min(pieces, key=lambda p: p["height"])
    assert lintel["loc"][2] - lintel["height"] / 2.0 == pytest.approx(220.0)


def test_perpendicular_or_distant_pieces_do_not_carve():
    perpendicular = _window(yaw=90.0)  # a wall insert crossing the wall
    far = _window(y_m=-3.0)  # a meter into the room
    for prop in (perpendicular, far):
        payload = _scene_payload(_scene([prop]))
        assert len(payload["wall_segments"]) == 1
        assert payload["wall_segments"][0]["height"] == pytest.approx(250.0)


def test_alignment_preserves_the_facing_side():
    # A door hung "backwards" (yaw ~180 vs. the segment's 0) must flip with
    # the wall, not be forced onto the segment's own direction.
    assert _closest_parallel_yaw(0.0, 175.0) % 360.0 == pytest.approx(180.0)
    assert _closest_parallel_yaw(0.0, 5.0) % 360.0 == pytest.approx(0.0)
    assert _closest_parallel_yaw(90.0, -85.0) % 360.0 == pytest.approx(270.0)


def test_prisonbars_width_matches_the_icon_but_depth_stays_true():
    bars = Prop(id="b", name="PRISONBARS", kind="PRISONBARS",
                location=Vec3(0, 0), yaw_deg=0.0, is_set=True)
    payload = _scene_payload(Scene(props=[bars]))
    parts = payload["props"][0]["parts"]
    xs = []
    for part in parts:
        half = part["scale"][0] * 100.0 / 2.0
        xs += [part["loc"][0] - half, part["loc"][0] + half]
    assert max(xs) - min(xs) == pytest.approx(155.9, abs=0.1)
    top_rail = parts[0]
    assert top_rail["scale"][1] * 100.0 == pytest.approx(6.0)  # depth unsqueezed


def test_parser_flags_genericset_vs_genericprop():
    doc = (
        "<ShotDesignerDocument>"
        "<DocumentPreamble>"
        "<magic>Hollywood Camera Work Shot Designer Scene</magic>"
        "<fileVersion>1</fileVersion><appVersion>1.80.8</appVersion>"
        "</DocumentPreamble>"
        "<CurrentSnapshot><Canvas>"
        "<GenericSet><uniqueID>set1</uniqueID><x>0</x><y>0</y>"
        "<objectKey>SMALLWINDOW</objectKey><snapPath/>"
        "<SubObjects><RotatorNoMenu><angle>0</angle></RotatorNoMenu></SubObjects>"
        "</GenericSet>"
        "<GenericProp><uniqueID>prop1</uniqueID><x>0</x><y>0</y>"
        "<objectKey>SOFA</objectKey>"
        "<SubObjects><RotatorObject><angle>0</angle></RotatorObject></SubObjects>"
        "</GenericProp>"
        "</Canvas></CurrentSnapshot>"
        "</ShotDesignerDocument>"
    )
    scene = parse_string(doc)
    by_id = {p.id: p for p in scene.props}
    assert by_id["set1"].is_set is True
    assert by_id["set1"].wall_snapped is False  # empty snapPath stays informational
    assert by_id["prop1"].is_set is False
