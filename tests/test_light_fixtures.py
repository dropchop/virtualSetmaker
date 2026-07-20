from virtualsetmaker.emit.blockouts import LIGHT_FIXTURE_DEFAULT, LIGHT_FIXTURES, fixture_for
from virtualsetmaker.emit.unreal_python import _scene_payload
from virtualsetmaker.ir import Light, Scene, Vec3


def _payload_for(kind):
    scene = Scene(lights=[Light(id="l", kind=kind, location=Vec3(0.0, 0.0, 0.0))])
    return _scene_payload(scene)["lights"][0]


def test_fresnel_gets_stand_and_pitched_spotlight_at_head():
    lt = _payload_for("FRESNELLARGE")
    assert lt["cls"] == "spot"
    assert len(lt["parts"]) == 3  # base, pole, head
    assert lt["light_loc"][2] == 170.0
    assert lt["light_rot"][0] == -25.0


def test_practical_lamp_gets_point_light_inside_shade():
    lt = _payload_for("PRACTICALLIGHT")
    assert lt["cls"] == "point"
    assert lt["light_rot"][0] == 0.0  # omnidirectional: no pitch
    assert len(lt["parts"]) == 3


def test_sun_is_directional_with_no_rig_geo():
    lt = _payload_for("SUN")
    assert lt["cls"] == "directional"
    assert lt["parts"] == []
    assert lt["light_loc"][2] == 800.0


def test_speed_rail_spawns_rig_but_no_light():
    lt = _payload_for("VIRTUALSPEEDRAIL")
    assert lt["light_loc"] is None
    assert len(lt["parts"]) == 3


def test_silk_gets_frame_with_rect_light_on_face():
    lt = _payload_for("SILK")
    assert lt["cls"] == "rect"
    assert lt["light_loc"][2] == 120.0


def test_unknown_kind_falls_back_to_default_stand():
    assert fixture_for("SOMETHINGNEW") is LIGHT_FIXTURE_DEFAULT


def test_every_fixture_declares_a_valid_light_class():
    valid = {"spot", "rect", "point", "directional"}
    for needle, fixture in LIGHT_FIXTURES:
        assert fixture["cls"] in valid, needle
    assert LIGHT_FIXTURE_DEFAULT["cls"] == "spot"


def test_soft_and_frame_kinds_get_rect_lights_with_matching_rigs():
    for kind in ("SOFTLIGHT", "FRAME"):
        lt = _payload_for(kind)
        assert lt["cls"] == "rect", kind
        assert len(lt["parts"]) == 3, kind


def test_lantern_and_bulb_kinds_get_hung_point_lights():
    for kind in ("LANTERN", "LIGHTBULB"):
        lt = _payload_for(kind)
        assert lt["cls"] == "point", kind
        assert lt["light_rot"][0] == 0.0, kind


def test_emit_point_rotates_with_fixture_yaw():
    scene = Scene(lights=[Light(id="l", kind="SOFTBOX", location=Vec3(0.0, 0.0, 0.0), yaw_deg=-90.0)])
    lt = _scene_payload(scene)["lights"][0]
    # Yaw carries over unchanged (identity screen->UE map): the +Y emit offset
    # (0, 45) rotated by -90 deg lands on +X: (x, y) -> (y, -x).
    assert abs(lt["light_loc"][0] - 45.0) < 1e-9
    assert abs(lt["light_loc"][1] - 0.0) < 1e-9
