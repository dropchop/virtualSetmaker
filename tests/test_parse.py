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


def test_probe_warns_on_untested_file_version(tmp_path):
    doc = tmp_path / "future.hcw"
    doc.write_text(
        "<ShotDesignerDocument>"
        "<DocumentPreamble>"
        "<magic>Hollywood Camera Work Shot Designer Scene</magic>"
        "<fileVersion>2</fileVersion><appVersion>9.9</appVersion>"
        "</DocumentPreamble>"
        "<CurrentSnapshot><Canvas/></CurrentSnapshot>"
        "</ShotDesignerDocument>"
    )
    result = probe(str(doc))
    assert len(result.warnings) == 1
    assert "file version '2'" in result.warnings[0]
    # ...and the warning rides along into the parsed scene for the build report.
    scene = parse_file(str(doc))
    assert scene.notes == result.warnings


def test_probe_has_no_warnings_for_supported_version():
    assert probe(SAMPLE).warnings == []
    assert parse_file(SAMPLE).notes == []


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


def test_unknown_canvas_objects_are_recorded_not_silently_dropped():
    xml = """
    <ShotDesignerDocument>
      <CurrentSnapshot>
        <Canvas>
          <ImageProp><uniqueID>ip-1</uniqueID><x>10</x><y>20</y></ImageProp>
          <MysteryThing><uniqueID>m-1</uniqueID></MysteryThing>
          <ImageProp><uniqueID>ip-2</uniqueID><x>30</x><y>40</y></ImageProp>
        </Canvas>
      </CurrentSnapshot>
      <DocumentPostScript><numObjects>3</numObjects><numSnapshot>0</numSnapshot></DocumentPostScript>
    </ShotDesignerDocument>
    """
    from virtualsetmaker.parse.shotdesigner import parse_string

    scene = parse_string(xml)
    assert scene.props == []
    assert sorted(scene.skipped_objects) == ["ImageProp", "ImageProp", "MysteryThing"]


def test_extra_snapshots_are_counted():
    xml = """
    <ShotDesignerDocument>
      <CurrentSnapshot><Canvas/></CurrentSnapshot>
      <DocumentPostScript><numObjects>0</numObjects><numSnapshot>4</numSnapshot></DocumentPostScript>
    </ShotDesignerDocument>
    """
    from virtualsetmaker.parse.shotdesigner import parse_string

    scene = parse_string(xml)
    assert scene.extra_snapshots == 4


def test_sample_has_no_skipped_objects():
    scene = parse_file(SAMPLE)
    assert scene.skipped_objects == []
    assert scene.extra_snapshots == 0


def test_character_female_flag_is_parsed():
    scene = parse_file(SAMPLE)
    by_id = {a.id: a for a in scene.actors}
    assert by_id["firstcharacter"].female is False
    assert by_id["secondcharacter"].female is True


def test_character_color_is_unpacked_to_rgb():
    table_sample = os.path.join(os.path.dirname(SAMPLE), "one_with_table.hcw")
    scene = parse_file(table_sample)
    by_color = {a.color: a for a in scene.actors}
    assert by_color["Red"].color_rgb == [252, 131, 123]  # <color>16548731
    assert by_color["Blue"].color_rgb == [148, 184, 255]  # <color>9746687
