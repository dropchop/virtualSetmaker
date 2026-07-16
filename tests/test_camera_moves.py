import math
import os

import pytest

from virtualsetmaker.parse import parse_file

HERE = os.path.dirname(__file__)
STRAIGHT = os.path.join(HERE, "..", "samples", "Camera_move_only.hcw")
CURVE = os.path.join(HERE, "..", "samples", "Camera_move_curve.hcw")

pytestmark = pytest.mark.skipif(
    not (os.path.exists(STRAIGHT) and os.path.exists(CURVE)),
    reason="camera-move samples not present",
)


def test_stop_marks_merge_into_one_camera():
    scene = parse_file(STRAIGHT)
    assert len(scene.cameras) == 1
    assert scene.cameras[0].is_animated


def test_straight_move_keys_start_and_end_only():
    cam = parse_file(STRAIGHT).cameras[0]
    assert len(cam.keyframes) == 2
    k0, k1 = cam.keyframes
    assert k0.time_s == 0.0
    assert k1.time_s > 0.0
    assert (k0.location.x, k0.location.y) == pytest.approx((-0.074, 1.431))
    assert (k1.location.x, k1.location.y) == pytest.approx((-0.088, -0.7985))


def test_look_direction_is_maintained():
    cam = parse_file(STRAIGHT).cameras[0]
    yaws = [k.yaw_deg for k in cam.keyframes]
    assert yaws[0] == pytest.approx(yaws[1])
    assert yaws[0] == pytest.approx(math.degrees(3.1315729488307933))


def test_move_duration_from_path_length_and_speed():
    cam = parse_file(STRAIGHT).cameras[0]
    length_m = math.hypot(-0.088 - -0.074, -0.7985 - 1.431)
    assert cam.keyframes[-1].time_s == pytest.approx(length_m / 0.75, abs=0.01)


def test_curved_move_keys_include_the_bow():
    cam = parse_file(CURVE).cameras[0]
    assert len(cam.keyframes) == 3
    mid = cam.keyframes[1]
    assert (mid.location.x, mid.location.y) == pytest.approx((2.077, 0.4885))
    # intermediate yaw is interpolated between identical stop headings
    assert mid.yaw_deg == pytest.approx(cam.keyframes[0].yaw_deg)


def test_curve_mid_key_timed_by_arc_length():
    cam = parse_file(CURVE).cameras[0]
    k = cam.keyframes
    d1 = math.hypot(2.077 - 0.7575, 0.4885 - 1.669)
    d2 = math.hypot(0.7435 - 2.077, -0.5405 - 0.4885)
    assert k[1].time_s / k[2].time_s == pytest.approx(d1 / (d1 + d2), abs=0.01)


def test_scene_duration_covers_the_move():
    scene = parse_file(STRAIGHT)
    assert scene.duration_s >= scene.cameras[0].keyframes[-1].time_s
    assert scene.validate() == []
