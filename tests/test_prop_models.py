"""The model library contract: every recipe and light rig has a shipped
model whose bbox equals its blockout's, within budget, with valid materials."""

import pytest

from virtualsetmaker.emit.blockouts import (
    LIGHT_FIXTURE_DEFAULT,
    LIGHT_FIXTURES,
    RECIPES,
    recipe_bbox,
)
from virtualsetmaker.geo.materials import MATERIALS
from virtualsetmaker.geo.props import (
    FIXTURE_MODELS,
    MODEL_BUILDERS,
    _fixture_parts,
    build_model,
    model_names_for_scene,
)

ALL_MODELS = sorted(MODEL_BUILDERS) + sorted(FIXTURE_MODELS)


def test_full_coverage():
    assert set(MODEL_BUILDERS) == set(RECIPES)
    fixture_models = {f.get("model") for _n, f in LIGHT_FIXTURES if f.get("model")}
    fixture_models.add(LIGHT_FIXTURE_DEFAULT["model"])
    assert set(FIXTURE_MODELS) == fixture_models


@pytest.mark.parametrize("name", ALL_MODELS)
def test_model_bbox_matches_recipe_bbox(name):
    mesh = build_model(name)
    parts = RECIPES[name] if name in RECIPES else _fixture_parts(name)
    lo, hi = recipe_bbox(parts)
    alo, ahi = mesh.bbox()
    for i in range(3):
        assert alo[i] == pytest.approx(lo[i], abs=0.05), (name, "lo", i)
        assert ahi[i] == pytest.approx(hi[i], abs=0.05), (name, "hi", i)


@pytest.mark.parametrize("name", ALL_MODELS)
def test_model_is_valid_geometry(name):
    mesh = build_model(name)
    assert mesh.tri_count() <= 2000, (name, mesh.tri_count())
    assert mesh.signed_volume() > 0, name
    assert all(mat in MATERIALS for mat in mesh.face_mats), name
    # no degenerate faces (repeated vertex indices)
    assert all(len({a, b, c}) == 3 for a, b, c in mesh.faces), name


def test_scene_model_selection_skips_wall_inserts_and_unknowns():
    names = model_names_for_scene(
        ["SOFA", "DOOROPEN", "WINDOW", "FLUXCAPACITOR", "ROUNDTABLE"],
        ["SUN", "FRESNEL650", "KINOFLO"],
    )
    assert "SOFA" in names and "TABLEROUND" in names
    assert "DOOROPEN" not in names and "WINDOW" not in names  # frozen carve path
    assert not any(n == "FLUXCAPACITOR" for n in names)
    assert "RIG_DEFAULT" in names and "RIG_SLAB" in names
    assert not any(n == "SUN" for n in names)  # sun has no rig model
