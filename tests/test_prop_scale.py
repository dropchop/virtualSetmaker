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


def test_tables_emit_at_icon_size_not_doll_house_size():
    props = _payload_props()
    # objectScale ~0.567 * native 160 => ~90 cm (was 51/68 cm before
    # calibration). The tabletop is parts[0]; assert its emitted size directly
    # (the AABB footprint would over-read the slightly-rotated square table).
    for name, stored_scale in (("TABLESQUARE", 0.5672760691533394), ("TABLEROUND", 0.5660213270955472)):
        top = props[name]["parts"][0]
        expected = stored_scale * native_span_for(name)[0]
        assert top["scale"][0] * 100.0 == pytest.approx(expected, abs=0.5), name
        assert top["scale"][1] * 100.0 == pytest.approx(expected, abs=0.5), name
        assert 85.0 < top["scale"][0] * 100.0 < 95.0, name
        # ...and the whole footprint is in the right neighborhood too.
        w, d = _footprint(props[name])
        assert w == pytest.approx(expected, abs=2.0), name
        assert d == pytest.approx(expected, abs=2.0), name


def test_uncalibrated_recipes_keep_historical_sizing():
    # No SD_NATIVE entry -> factor 1: DOOROPEN at objectScale 0.7 spans 70 cm
    # (pinned by test_prop_placement); spot-check via the other sample here.
    assert native_span_for("DOOROPEN") is None
    assert native_span_for("SOFA") is None
    assert native_span_for(None) is None
