from virtualsetmaker.coords import ir_to_ue_location, ir_to_ue_rotation, ir_to_ue_yaw
from virtualsetmaker.ir import Vec3


def test_meters_to_centimeters_scale():
    x, y, z = ir_to_ue_location(Vec3(1.0, 0.0, 2.0))
    assert x == 100.0
    assert z == 200.0


def test_y_axis_is_flipped():
    # Shot Designer screen-space +y (down) maps to Unreal -Y.
    _x, y, _z = ir_to_ue_location(Vec3(0.0, 3.0, 0.0))
    assert y == -300.0


def test_yaw_sign_flips_to_match_y_flip():
    assert ir_to_ue_yaw(90.0) == -90.0


def test_rotation_tuple_order_is_pitch_yaw_roll():
    pitch, yaw, roll = ir_to_ue_rotation(10.0, 20.0, 30.0)
    assert pitch == 10.0
    assert yaw == -20.0
    assert roll == 30.0


def test_custom_units_per_meter():
    # If 1 unit = 1 inch, caller passes 39.37 units/m -> different scale factor.
    x, _y, _z = ir_to_ue_location(Vec3(2.0, 0.0, 0.0), m_to_cm=39.37)
    assert abs(x - 78.74) < 1e-6
