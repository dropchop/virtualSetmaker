import math

from virtualsetmaker.emit.blockouts import GENERIC, RECIPES, match_kind, recipe_for
from virtualsetmaker.emit.unreal_python import _bake_parts


def test_exact_keys_match():
    assert match_kind("SOFA") == "SOFA"
    assert match_kind("DOOROPEN") == "DOOROPEN"


def test_substring_aliases_match_variants():
    assert match_kind("COUCHMODERN") == "SOFA"
    assert match_kind("TABLESMALL") == "TABLE"
    assert match_kind("ARMCHAIRLEATHER") == "ARMCHAIR"  # not CHAIR
    assert match_kind("CARPETRED") == "RUG"  # not CAR
    assert match_kind("SPORTSCAR") == "CAR"


def test_ordering_hazards():
    assert match_kind("BUSH") == "BUSH"  # not BUS -> MINIBUS
    assert match_kind("MINIBUS") == "MINIBUS"
    assert match_kind("MONITORVILLAGE") == "MONITORVILLAGE"  # not MONITOR
    assert match_kind("MONITOR") == "MONITOR"
    assert match_kind("TRUCKTRAILER") == "TRUCKTRAILER"  # not SEMITRUCK
    assert match_kind("CUPBOARD") == "WARDROBE"  # not CUP
    assert match_kind("SHOTGUN") == "RIFLE"  # not GUN
    assert match_kind("JETFIGHTER") == "FIGHTERJET"
    assert match_kind("SMALLPLANE") == "PLANESMALL"
    assert match_kind("TREE") == "TREE"  # own recipe, no longer PLANT


def test_all_alias_targets_have_recipes():
    from virtualsetmaker.emit.blockouts import ALIASES

    for _needle, target in ALIASES:
        assert target in RECIPES, target


def test_no_duplicate_alias_rows():
    from virtualsetmaker.emit.blockouts import ALIASES

    assert len(ALIASES) == len(set(ALIASES))


# The full Shot Designer object palette (from the app's palette screenshots,
# 2026-07). Keys are predicted in both word orders since Shot Designer condenses
# display names unpredictably (Large Fresnel -> FRESNELLARGE, Open Door ->
# DOOROPEN). Every candidate must resolve to SOME recipe — no generic fallback.
PALETTE_KEY_CANDIDATES = [
    "IMAGEPROP", "TABLESQUARE", "SQUARETABLE", "TABLEOVAL", "OVALTABLE",
    "TABLEROUND", "ROUNDTABLE", "CHAIR", "SOFA", "PAPER", "CELLPHONE",
    "LAPTOP", "KEYBOARD", "MONITOR", "PLATE", "CUP", "DOG", "GUN", "RIFLE",
    "BUSH", "TREE", "CAR", "MINIBUS", "SEMITRUCK", "TRUCKSEMI", "TRUCKTRAILER",
    "MOTORCYCLE", "TANK", "PLANESMALL", "SMALLPLANE", "FIGHTERJET",
    "JETFIGHTER", "COMMERCIALJET", "JETCOMMERCIAL", "STRAIGHTARROW",
    "ARROWSTRAIGHT", "CURVEDARROW", "ARROWCURVED", "CRANE", "BOOMMICROPHONE",
    "BOOMMIC", "MONITORVILLAGE", "EQUIPMENT",
    "WINDOW", "DOOROPEN", "DOORCLOSED", "DOOR", "DOORDOUBLEOPEN",
    "DOUBLEOPENDOOR", "DOORDOUBLECLOSED", "DOUBLECLOSEDDOOR",
    "MEDIUMOPENING", "OPENINGMEDIUM", "PRISONBARS",
]


def test_entire_shot_designer_palette_is_covered():
    for key in PALETTE_KEY_CANDIDATES:
        assert match_kind(key) is not None, f"palette key {key} fell through to generic"


def test_boom_microphone_is_not_a_cellphone():
    # MICROPHONE contains "PHONE" — ordering must route it to the boom rig.
    assert match_kind("BOOMMICROPHONE") == "BOOM"
    assert match_kind("MICROPHONE") == "MICROPHONE"


def test_unknown_kind_falls_back_to_generic():
    name, parts = recipe_for("FLUXCAPACITOR")
    assert name is None
    assert parts == GENERIC


def test_all_recipes_have_positive_dimensions():
    for name, parts in RECIPES.items():
        assert parts, name
        for part in parts:
            assert all(s > 0 for s in part["size"]), (name, part)
            assert part["offset"][2] >= 0, (name, part)  # nothing below the floor


def test_bake_rotates_offsets_about_prop_origin():
    parts = [{"shape": "cube", "offset": [100.0, 0.0, 10.0], "size": [50, 50, 20], "rot": [0, 0, 0]}]
    baked = _bake_parts(parts, (0.0, 0.0), 90.0, (1.0, 1.0))
    # +X offset rotated 90 deg about Z lands on +Y.
    assert math.isclose(baked[0]["loc"][0], 0.0, abs_tol=1e-9)
    assert math.isclose(baked[0]["loc"][1], 100.0, abs_tol=1e-9)
    assert baked[0]["loc"][2] == 10.0
    assert baked[0]["rot"][1] == 90.0


def test_bake_applies_footprint_scale_but_not_height():
    parts = [{"shape": "cube", "offset": [10.0, 20.0, 30.0], "size": [100, 100, 100], "rot": [0, 0, 0]}]
    baked = _bake_parts(parts, (0.0, 0.0), 0.0, (0.5, 2.0))
    assert baked[0]["loc"] == [5.0, 40.0, 30.0]
    assert baked[0]["scale"] == [0.5, 2.0, 1.0]  # z untouched
