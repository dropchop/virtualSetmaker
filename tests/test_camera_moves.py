import math
import os

import pytest

from virtualsetmaker.parse import parse_file, parse_string

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


def _two_stop_move_hcw(angle_a: float, angle_b: float) -> str:
    """Minimal scene: two stop-mark cameras joined by a straight track."""
    return f"""<ShotDesignerDocument><CurrentSnapshot><Canvas>
      <Camera><uniqueID>CAM-A</uniqueID><x>-75.85</x><y>150.05</y>
        <stopMarks>1</stopMarks>
        <SubObjects><RotatorCamera><angle>{angle_a}</angle></RotatorCamera></SubObjects>
      </Camera>
      <Camera><uniqueID>CAM-B</uniqueID><x>82.55</x><y>153.4</y>
        <stopMarks>2</stopMarks>
        <SubObjects><RotatorCamera><angle>{angle_b}</angle></RotatorCamera></SubObjects>
      </Camera>
      <Track><uniqueID>TRK</uniqueID>
        <fromConstraints>CAM-A</fromConstraints><toConstraints>CAM-B</toConstraints>
        <Points><Point><x>-75.85</x><y>150.05</y></Point>
                <Point><x>82.55</x><y>153.4</y></Point></Points>
      </Track>
    </Canvas><TimeSlices><TimeNumber><cameraSpeed>3</cameraSpeed></TimeNumber>
    </TimeSlices></CurrentSnapshot></ShotDesignerDocument>"""


def test_stop_yaws_unwrap_to_the_shortest_turn():
    # Shot Designer stores absolute angles: start -90deg, end 228.75deg is a
    # -41.25deg turn -- but interpolating the raw numbers (as both Unreal's
    # channels and our mid-point fill do) spins +318.75deg the long way.
    # The end key must be rewritten to the nearest equivalent angle.
    scene = parse_string(_two_stop_move_hcw(-1.5707963267948966, 3.992419209211025))
    (cam,) = scene.cameras
    assert cam.is_animated and len(cam.keyframes) == 2
    y0, y1 = (k.yaw_deg for k in cam.keyframes)
    assert y0 == pytest.approx(-90.0)
    assert y1 == pytest.approx(-131.25, abs=0.01)  # 228.75 - 360
    assert abs(y1 - y0) <= 180.0
    # Same facing as the stored angle, just unwrapped.
    assert (y1 - math.degrees(3.992419209211025)) % 360.0 == pytest.approx(0.0, abs=0.01)


def test_stop_yaws_already_close_are_untouched():
    scene = parse_string(_two_stop_move_hcw(0.5, 0.75))
    y0, y1 = (k.yaw_deg for k in scene.cameras[0].keyframes)
    assert y0 == pytest.approx(math.degrees(0.5))
    assert y1 == pytest.approx(math.degrees(0.75))
