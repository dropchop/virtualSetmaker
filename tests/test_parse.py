import math
import os

import pytest

from virtualsetmaker.parse import parse_file
from virtualsetmaker.parse.probe import NotShotDesignerFile, probe

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "samples", "Sceneforclaude.hcw")
pytestmark = pytest.mark.skipif(not os.path.exists(SAMPLE), reason="sample .hcw not present")


def test_probe_accepts_the_sample():
    result = probe(SAMPLE)
    assert result.magic == "Hollywood Camera Work Shot Designer Scene"
    assert result.app_version == "1.80.8"


def test_probe_rejects_non_shotdesigner(tmp_path):
    bad = tmp_path / "nope.hcw"
    bad.write_text("<Something/>")
    with pytest.raises(NotShotDesignerFile):
        probe(str(bad))


def test_parse_counts_match_sample():
    scene = parse_file(SAMPLE)
    assert len(scene.cameras) == 1
    assert len(scene.actors) == 2
    assert len(scene.props) == 2  # 1 GenericProp (sofa) + 1 GenericSet (door)
    assert len(scene.walls) == 1
    assert len(scene.lights) == 2


def test_units_are_converted_to_meters():
    scene = parse_file(SAMPLE)
    # first character sits at Shot Designer x = -75 (units) -> -0.75 m at 1 unit = 1 cm.
    hero = next(a for a in scene.actors if a.id == "firstcharacter")
    assert hero.location.x == pytest.approx(-0.75)
    assert hero.location.y == pytest.approx(0.0)


def test_angles_are_converted_to_degrees():
    scene = parse_file(SAMPLE)
    # secondcharacter angle is -pi rad -> -180 deg.
    guest = next(a for a in scene.actors if a.id == "secondcharacter")
    assert guest.yaw_deg == pytest.approx(-180.0)
    # camera angle is -pi/2 rad -> -90 deg.
    assert scene.cameras[0].keyframes[0].yaw_deg == pytest.approx(-90.0)


def test_prop_kinds_come_from_object_key():
    scene = parse_file(SAMPLE)
    kinds = {p.kind for p in scene.props}
    assert "SOFA" in kinds
    assert "DOOROPEN" in kinds


def test_wall_has_four_points():
    scene = parse_file(SAMPLE)
    assert len(scene.walls[0].points) == 4


def test_parsed_sample_is_valid():
    scene = parse_file(SAMPLE)
    assert scene.validate() == []
