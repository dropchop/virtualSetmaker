"""Shot Designer icon-size calibration (SD_NATIVE): emitted footprint must be
objectScale * native span, and uncalibrated recipes must keep the historical
recipe * objectScale behavior."""

import math
import os

import pytest

from virtualsetmaker.emit.blockouts import RECIPES, native_span_for, recipe_span
from virtualsetmaker.emit.unreal_python import _scene_payload
from virtualsetmaker.parse import parse_file

TABLE_SAMPLE = os.path.join(os.path.dirname(__file__), "..", "samples", "one_with_table.hcw")
pytestmark = pytest.mark.skipif(
    not os.path.exists(TABLE_SAMPLE), reason="table sample .hcw not present"
)


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
    return max(xs) - min(xs), max(ys) - min(ys)


def _payload_props():
    scene = parse_file(TABLE_SAMPLE)
    return {p["matched"]: p for p in _scene_payload(scene)["props"]}


def test_recipe_span_matches_table_top():
    assert recipe_span(RECIPES["TABLESQUARE"]) == (90.0, 90.0)


def test_recipe_span_honors_part_rotation():
    # The TANK barrel is a cylinder rolled 90 deg to lie along +Y at offset
    # y=260: its 380 length must extend the Y span past the 680 cm hull.
    _sx, sy = recipe_span(RECIPES["TANK"])
    assert sy == pytest.approx(790.0)  # hull rear -340 .. barrel tip 260+190


def test_tables_emit_at_measured_icon_size():
    props = _payload_props()
    # Natives measured from the app's own FXG art. The "Square Table" icon is
    # actually rectangular (219.5 x 119.5): stored scale ~0.567 emits a
    # ~124.5 x 67.8 cm table. The round table icon is 120.6 across -> ~68.3.
    sq = props["TABLESQUARE"]["parts"][0]
    s = 0.5672760691533394
    assert sq["scale"][0] * 100.0 == pytest.approx(s * 219.5, abs=0.5)
    assert sq["scale"][1] * 100.0 == pytest.approx(s * 119.5, abs=0.5)
    rd = props["TABLEROUND"]["parts"][0]
    r = 0.5660213270955472
    assert rd["scale"][0] * 100.0 == pytest.approx(r * 120.6, abs=0.5)
    assert rd["scale"][1] * 100.0 == pytest.approx(r * 120.6, abs=0.5)


def test_wall_snapped_sets_have_no_native_entry():
    # Doors/windows are wall-snapped: their art includes wall stubs, and the
    # opening-based behavior is verified — they must stay uncalibrated.
    assert native_span_for("DOOROPEN") is None
    assert native_span_for("WINDOW") is None
    assert native_span_for(None) is None


def test_sofa_native_matches_the_measured_scene():
    # Sofa native comes from the app art (154.8 x 78.9) — within a stroke
    # width of the recipe (180 was our guess for width; depth 80 vs 78.9),
    # and of the 79.4 cm depth measured in Sceneforclaude.
    assert native_span_for("SOFA") == (154.8, 78.9)
