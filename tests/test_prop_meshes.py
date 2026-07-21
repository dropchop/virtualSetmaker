"""Real-mesh prop upgrades (UE Starter Content): the MESH_SPECS table, the
payload plumbing that rides alongside blockout parts, and the generated
script's install/fit runtime text."""

import math
import os

import pytest

from virtualsetmaker.emit import build_script
from virtualsetmaker.emit.blockouts import (
    MESH_SPECS,
    RECIPES,
    WALL_OPENINGS,
    recipe_height,
)
from virtualsetmaker.emit.unreal_python import _scene_payload
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


def test_mesh_specs_are_well_formed():
    for name, spec in MESH_SPECS.items():
        assert name in RECIPES, name
        # ObjectPath form under the pack's fixed mount point.
        assert spec["asset"].startswith("/Game/StarterContent/Props/SM_"), name
        assert "." in spec["asset"].rsplit("/", 1)[1], name
        # Restricted so the emitter's footprint-axis pre-swap stays exact.
        assert spec["yaw"] in (0.0, 90.0, 180.0, -90.0), name


def test_wall_inserts_never_get_meshes():
    # The carve pipeline is verified against blockout spans; a meshed door
    # frame inside the carve is explicitly out of scope (v1 decision).
    for name in WALL_OPENINGS:
        assert name not in MESH_SPECS, name


def test_payload_mesh_matches_blockout_footprint_and_height():
    scene = parse_file(TABLE_SAMPLE)
    props = {p["matched"]: p for p in _scene_payload(scene)["props"]}
    rd = props["TABLEROUND"]
    # Mesh rides ALONGSIDE the parts (runtime falls back to them), and its
    # fit target equals what the blockout would have occupied.
    assert rd["parts"]
    assert rd["mesh"]["asset"].endswith("SM_TableRound.SM_TableRound")
    fx, fy = _footprint(rd)
    assert rd["mesh"]["size"][0] == pytest.approx(fx, abs=0.5)
    assert rd["mesh"]["size"][1] == pytest.approx(fy, abs=0.5)
    # Heights never scale with objectScale: target is the recipe's own top.
    assert rd["mesh"]["size"][2] == pytest.approx(recipe_height(RECIPES["TABLEROUND"]))
    assert rd["mesh"]["loc"][2] == 0.0


def test_use_starter_meshes_off_omits_mesh_payload():
    scene = parse_file(TABLE_SAMPLE)
    payload = _scene_payload(scene, Defaults(use_starter_meshes=False))
    assert all("mesh" not in p for p in payload["props"])


def test_generated_script_carries_the_mesh_runtime():
    script = build_script(parse_file(TABLE_SAMPLE))
    assert "def _install_starter_props" in script
    assert "def _spawn_prop_mesh" in script
    # Fit from the loaded asset's real bounds, never hardcoded sizes.
    assert "get_bounding_box" in script
    # Auto-install: engine Samples tree, skip-existing copy, registry rescan,
    # and the UE 5.7+ "nothing ships on disk" guidance.
    assert '"Samples", "StarterContent"' in script
    assert "if not os.path.exists(target):" in script
    assert 'scan_paths_synchronous(["/Game/StarterContent"]' in script
    assert "normal on UE 5.7+" in script
