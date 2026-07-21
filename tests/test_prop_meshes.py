"""Shipped prop meshes: payload plumbing and the generated script's
import/colorize/fallback runtime text."""

import math
import os

import pytest

from virtualsetmaker.emit import build_script
from virtualsetmaker.emit.blockouts import RECIPES, WALL_OPENINGS, recipe_bbox
from virtualsetmaker.emit.unreal_python import _scene_payload
from virtualsetmaker.geo.props import MODEL_BUILDERS
from virtualsetmaker.parse import parse_file
from virtualsetmaker.settings import Defaults

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


def test_every_recipe_has_a_shipped_model():
    assert set(MODEL_BUILDERS) == set(RECIPES)


def test_wall_inserts_never_get_mesh_payloads():
    # The carve pipeline is verified against blockout spans; meshed door
    # frames inside the carve stay out of scope even though library models
    # exist for them.
    scene = parse_file(TABLE_SAMPLE)
    for p in _scene_payload(scene)["props"]:
        if p["matched"] in WALL_OPENINGS:
            assert "mesh" not in p


def test_payload_mesh_matches_blockout_footprint_and_height():
    scene = parse_file(TABLE_SAMPLE)
    props = {p["matched"]: p for p in _scene_payload(scene)["props"]}
    rd = props["TABLEROUND"]
    # Mesh rides ALONGSIDE the parts (runtime falls back to them), and its
    # fit target equals what the blockout occupies.
    assert rd["parts"]
    assert rd["mesh"]["model"] == "TABLEROUND"
    fx, fy = _footprint(rd)
    assert rd["mesh"]["size"][0] == pytest.approx(fx, abs=0.5)
    assert rd["mesh"]["size"][1] == pytest.approx(fy, abs=0.5)
    lo, hi = recipe_bbox(RECIPES["TABLEROUND"])
    # Heights never scale with objectScale; z target is the recipe's own.
    assert rd["mesh"]["size"][2] == pytest.approx(hi[2] - lo[2])
    assert rd["mesh"]["loc"][2] == pytest.approx(lo[2])
    # src_ext is the authored extent, unscaled -- the axis-swap guard input.
    assert rd["mesh"]["src_ext"] == pytest.approx([hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]])


def test_tabletop_props_sit_at_table_height():
    # PAPER's recipe floats at ~75 cm; the mesh payload must preserve that
    # (bbox-bottom z), not stretch the model from the floor.
    scene = parse_file(TABLE_SAMPLE)
    payload = _scene_payload(scene)
    lo, hi = recipe_bbox(RECIPES["PAPER"])
    assert lo[2] == pytest.approx(75.0)  # sanity: recipe bottom is table height
    for p in payload["props"]:
        if p["matched"] == "PAPER":
            assert p["mesh"]["loc"][2] == pytest.approx(75.0)
            assert p["mesh"]["size"][2] == pytest.approx(hi[2] - lo[2])


def test_use_prop_meshes_off_omits_mesh_payload():
    scene = parse_file(TABLE_SAMPLE)
    payload = _scene_payload(scene, Defaults(use_prop_meshes=False))
    assert all("mesh" not in p for p in payload["props"])
    assert all("mesh" not in lt for lt in payload["lights"])


def test_generated_script_carries_the_mesh_runtime():
    script = build_script(parse_file(TABLE_SAMPLE))
    assert "def _load_or_import_prop_mesh" in script
    assert "def _spawn_prop_mesh" in script
    assert "def _colorize_prop_mesh" in script
    # Synchronous Epic-recommended import path (Interchange under the hood).
    assert "unreal.AssetImportTask()" in script
    assert "import_asset_tasks([task])" in script
    assert "does_asset_exist" in script
    # Fit from the loaded asset's real bounds, never hardcoded sizes.
    assert "get_bounding_box" in script
    # Legacy Y-up assets get corrected in place, not re-imported; anything
    # unrecognizable still falls back to blockout parts.
    assert "legacy Y-up import" in script
    assert "using blockout" in script
    # The Starter Content era is over.
    assert "_install_starter_props" not in script
    assert "StarterContent" not in script


def test_props_dir_fallback_is_baked_when_writing_to_disk(tmp_path):
    from virtualsetmaker.emit import write_script

    out = tmp_path / "scene_unreal.py"
    write_script(parse_file(TABLE_SAMPLE), str(out))
    script = out.read_text()
    assert 'VSM_PROPS_DIRNAME = ' + repr("vsm_props") in script
    assert repr(str(tmp_path / "vsm_props")) in script
