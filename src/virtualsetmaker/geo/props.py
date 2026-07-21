"""One shipped 3D model per Shot Designer recipe (and per light-rig type).

Two tiers:

* Every recipe gets a **parts-derived** model for free: its audited blockout
  parts converted to real merged geometry (chamfered boxes, 16-segment
  cylinders) with per-part flat materials from :data:`PART_MATS`.
* Recipes where real curves or silhouettes matter get a **custom builder**
  (lathed toilet bowl, car side-profile body, lobed trees, tapered
  fuselages, ...) registered in :data:`_CUSTOM`.

Contract: ``build_model(name)`` returns a mesh whose bbox equals the
recipe's :func:`~virtualsetmaker.emit.blockouts.recipe_bbox` **exactly**
(authored close, then snapped with ``fit_to``; a >15% authoring error on any
axis raises instead of being silently stretched). That keeps every piece of
existing calibration — SD_NATIVE, frozen wall-insert spans, the runtime
bounds-fit — valid without modification.
"""

from __future__ import annotations

from functools import lru_cache

from ..emit.blockouts import (
    LIGHT_FIXTURE_DEFAULT,
    LIGHT_FIXTURES,
    RECIPES,
    recipe_bbox,
)
from .materials import MATERIALS
from .mesh import Mesh
from .primitives import box, cone, cylinder, lathe, prism, torus, tube, uv_sphere


def mesh_from_parts(parts, mats="plastic_light", chamfer: float = 2.0) -> Mesh:
    """Convert blockout parts to one merged mesh with per-part materials.

    ``mats`` is a single material for all parts or a list aligned with the
    parts (last entry repeats). Cubes get a small chamfer so they read as
    built objects rather than BSP.
    """
    if isinstance(mats, str):
        mats = [mats]
    out = Mesh()
    for i, part in enumerate(parts):
        mat = mats[i] if i < len(mats) else mats[-1]
        sx, sy, sz = part["size"]
        if part["shape"] == "cube":
            c = min(chamfer, sx / 6.0, sy / 6.0, sz / 6.0)
            piece = box((sx, sy, sz), chamfer=c, mat=mat)
        elif part["shape"] == "cylinder":
            piece = cylinder(sx / 2.0, sy / 2.0, sz, center=(0, 0, -sz / 2.0), mat=mat)
        else:
            piece = uv_sphere((sx, sy, sz), mat=mat)
        pitch, yaw, roll = part["rot"]
        if pitch or yaw or roll:
            piece.rotate(pitch=pitch, yaw=yaw, roll=roll)
        out.add(piece.translate(*part["offset"]))
    return out


# Per-part materials for parts-derived models, aligned with each recipe's
# parts list (single string = every part; last list entry repeats).
PART_MATS: dict[str, list | str] = {
    "SOFA": ["fabric", "fabric", "fabric", "fabric"],
    "ARMCHAIR": "fabric_warm",
    "CHAIR": ["wood", "wood", "wood_dark", "wood_dark", "wood_dark", "wood_dark"],
    "STOOL": ["leather", "metal", "metal"],
    "BENCH": "wood",
    "TABLE": ["wood", "wood_dark"],
    "TABLEROUND": "wood",
    "TABLESQUARE": ["wood", "wood_dark"],
    "TABLEOVAL": "wood",
    "COFFEETABLE": ["wood_dark", "metal"],
    "DESK": ["wood", "wood_dark", "wood_dark"],
    "BED": ["wood_dark", "mattress", "wood"],
    "BEDSINGLE": ["wood_dark", "mattress", "wood"],
    "DOOR": ["wood_dark", "wood_dark", "wood_dark", "wood"],
    "DOOROPEN": ["wood_dark", "wood_dark", "wood_dark", "wood"],
    "DOORDOUBLECLOSED": ["wood_dark", "wood_dark", "wood_dark", "wood", "wood"],
    "DOORDOUBLEOPEN": ["wood_dark", "wood_dark", "wood_dark", "wood", "wood"],
    "OPENING": "wood_dark",
    "PRISONBARS": "metal_dark",
    "IMAGEPROP": "paper",
    "WINDOW": "wood_dark",
    "TV": ["screen", "metal_dark", "metal_dark"],
    "FLOORLAMP": ["metal_dark", "metal_dark", "paper"],
    "PLANT": ["clay", "bark", "foliage"],
    "BOOKCASE": "wood",
    "COUNTER": ["wood_dark", "wood", "porcelain"],
    "DRESSER": ["wood", "wood_dark", "wood_dark", "wood_dark", "wood_dark"],
    "NIGHTSTAND": "wood",
    "WARDROBE": ["wood_dark", "wood", "wood_dark", "wood_dark", "wood"],
    "FRIDGE": ["paint_white", "paint_white", "paint_white", "paint_white"],
    "STOVE": ["paint_white", "metal_dark", "glass", "paint_white"],
    "TOILET": "porcelain",
    "SINK": "porcelain",
    "BATHTUB": "porcelain",
    "RUG": "fabric_warm",
    "CAR": ["paint_blue", "glass", "rubber", "rubber", "rubber", "rubber"],
    "PAPER": "paper",
    "CELLPHONE": "screen",
    "LAPTOP": ["plastic_dark", "screen"],
    "KEYBOARD": "plastic_dark",
    "MONITOR": ["plastic_dark", "plastic_dark", "screen"],
    "PLATE": "porcelain",
    "CUP": "porcelain",
    "GUN": "metal_dark",
    "RIFLE": ["metal_dark"],
    "DOG": ["fabric_warm", "fabric_warm", "fabric_warm", "plastic_dark"],
    "BUSH": "foliage",
    "TREE": ["bark", "foliage"],
    "MINIBUS": ["paint_white", "paint_white", "glass", "rubber"],
    "SEMITRUCK": ["metal_dark", "paint_red", "rubber"],
    "TRUCKTRAILER": ["paint_white", "rubber"],
    "MOTORCYCLE": ["paint_red", "rubber", "rubber", "metal"],
    "TANK": ["paint_olive", "paint_olive", "metal_dark"],
    "PLANESMALL": "paint_white",
    "FIGHTERJET": ["metal", "metal", "metal", "glass"],
    "COMMERCIALJET": ["paint_white", "paint_white", "paint_red", "paint_white", "metal", "metal"],
    "BOOM": ["metal_dark", "metal_dark", "metal_dark", "rubber"],
    "CRANE": ["metal_dark", "metal", "metal", "paint_red"],
    "MICROPHONE": ["metal_dark", "metal_dark", "rubber"],
    "MONITORVILLAGE": ["metal_dark", "metal_dark", "metal", "metal", "metal", "metal",
                       "screen", "screen"],
    "EQUIPMENT": ["plastic_dark", "plastic_dark", "plastic_dark"],
    "ARROW": "paint_yellow",
}


# ---------------------------------------------------------------------------
# Custom builders (real curves / silhouettes where the parts version is crude)
# ---------------------------------------------------------------------------


def _toilet() -> Mesh:
    # Recipe box: 38w x 70d (tank -35..-15, bowl to +35) x 76h.
    m = Mesh()
    # Lathed bowl + pedestal: base radius 12 -> waist 10 -> rim 19 at 40.
    m.add(lathe(
        [(13.0, 0.0), (10.0, 8.0), (10.0, 24.0), (18.0, 36.0), (19.0, 40.0), (17.0, 41.5)],
        seg=16, center=(0.0, 10.0, 0.0), mat="porcelain",
    ))
    m.add(torus(16.0, 3.0, center=(0.0, 10.0, 41.5), squash_z=0.5, mat="porcelain"))
    m.add(box((38, 20, 38), center=(0, -25, 55), chamfer=2.0, mat="porcelain"))   # tank
    m.add(box((36, 18, 4), center=(0, -25, 74), chamfer=1.5, mat="porcelain"))    # tank lid
    # bowl reaches the recipe's front edge
    m.add(uv_sphere((36, 50, 30), center=(0, 10, 28), mat="porcelain"))
    return m


def _sink() -> Mesh:
    m = Mesh()
    m.add(lathe([(14.0, 0.0), (7.5, 10.0), (7.5, 78.0), (12.0, 80.0)],
                seg=16, mat="porcelain"))                                          # pedestal
    m.add(lathe([(12.0, 80.0), (25.0, 88.0), (25.0, 95.0), (22.0, 95.0),
                 (20.0, 89.0), (0.0, 87.0)], seg=16, mat="porcelain"))             # basin
    m.add(tube([(0, -18, 93), (0, -18, 102), (0, -8, 102)], 1.5, mat="metal"))     # faucet
    return m


def _plate() -> Mesh:
    return lathe([(9.0, 0.0), (12.0, 0.5), (13.0, 2.2), (12.5, 3.0), (11.0, 2.4),
                  (9.0, 1.2), (0.0, 1.0)], seg=16, center=(0, 0, 75.0), mat="porcelain")


def _cup() -> Mesh:
    # No handle: the icon's 9 cm footprint has no room for one, and squashing
    # a handled cup into it would deform the body.
    return lathe([(3.0, 0.0), (4.3, 0.5), (4.5, 9.5), (4.2, 10.0), (3.8, 9.4),
                  (3.4, 1.4), (0.0, 1.0)], seg=12, center=(0, 0, 75.0), mat="porcelain")


def _floorlamp() -> Mesh:
    m = Mesh()
    m.add(lathe([(20.0, 0.0), (18.0, 2.0), (4.0, 4.0), (2.0, 6.0)], seg=16, mat="metal_dark"))
    m.add(cylinder(2.0, 2.0, 146.0, center=(0, 0, 6.0), seg=10, mat="metal_dark"))
    m.add(lathe([(12.0, 152.0), (17.5, 154.0), (14.0, 180.0), (10.0, 182.0)],
                seg=16, mat="paper"))                                              # shade
    return m


def _plant() -> Mesh:
    m = Mesh()
    m.add(lathe([(14.0, 0.0), (16.0, 2.0), (20.0, 36.0), (18.0, 40.0), (0.0, 38.0)],
                seg=12, mat="clay"))                                               # pot
    m.add(cylinder(4.0, 4.0, 60.0, center=(0, 0, 40.0), seg=8, mat="bark"))
    m.add(uv_sphere((60, 60, 70), center=(-10, 5, 115), mat="foliage"))
    m.add(uv_sphere((50, 50, 60), center=(18, -8, 135), mat="foliage"))
    m.add(uv_sphere((44, 44, 50), center=(0, 12, 150), mat="foliage"))
    return m


def _bush() -> Mesh:
    m = Mesh()
    m.add(uv_sphere((90, 85, 70), center=(-18, 10, 38), mat="foliage"))
    m.add(uv_sphere((80, 90, 75), center=(20, -12, 45), mat="foliage"))
    m.add(uv_sphere((70, 70, 60), center=(0, 15, 58), mat="foliage"))
    return m


def _tree() -> Mesh:
    m = Mesh()
    m.add(lathe([(20.0, 0.0), (14.0, 60.0), (11.0, 250.0)], seg=10, mat="bark"))
    m.add(uv_sphere((260, 250, 220), center=(-45, 30, 340), mat="foliage"))
    m.add(uv_sphere((230, 240, 200), center=(60, -40, 380), mat="foliage"))
    m.add(uv_sphere((200, 200, 180), center=(0, 20, 430), mat="foliage"))
    return m


def _car() -> Mesh:
    m = Mesh()
    # Side profile (y = length, z = height), convex, extruded across X.
    m.add(prism([(-225, 34), (225, 34), (225, 72), (195, 92.5), (-195, 92.5), (-225, 70)],
                "x", -90, 90, mat="paint_blue"))
    m.add(prism([(-100, 90), (115, 90), (80, 145), (-68, 145)],
                "x", -80, 80, mat="paint_blue"))                                    # cabin
    m.add(box((164, 150, 26), center=(0, 5, 114), mat="glass"))                     # glass band
    for sx in (-1, 1):
        for sy in (-1, 1):
            wheel = cylinder(32.5, 32.5, 20, center=(0, 0, -10), seg=16, mat="rubber")
            wheel.rotate(pitch=90)
            m.add(wheel.translate(sx * 80, sy * 140, 32.5))
    return m


def _bed(width: float) -> Mesh:
    m = Mesh()
    m.add(box((width, 200, 30), center=(0, 0, 17), chamfer=2, mat="wood_dark"))
    m.add(box((width - 10, 190, 22), center=(0, 0, 44), chamfer=5, mat="mattress"))
    m.add(box((width, 10, 90), center=(0, -97.5, 45), chamfer=2, mat="wood"))
    pw = (width - 30) / 2.0
    m.add(box((pw, 35, 12), center=(-(pw / 2 + 5), -72, 58), chamfer=4, mat="pillow"))
    if width > 100:
        m.add(box((pw, 35, 12), center=(pw / 2 + 5, -72, 58), chamfer=4, mat="pillow"))
    return m


def _bookcase() -> Mesh:
    m = mesh_from_parts(RECIPES["BOOKCASE"], "wood")
    # Book rows on shelves 1-4 (not the top): varied paint colors.
    colors = ["paint_red", "paint_blue", "paint_olive", "paint_yellow"]
    for row, z in enumerate((4.0, 48.0, 92.0, 136.0)):
        m.add(box((72, 20, 26), center=(-2, 3, z + 13.5), mat=colors[row % 4]))
    return m


def _stove() -> Mesh:
    m = mesh_from_parts(RECIPES["STOVE"], PART_MATS["STOVE"])
    for bx in (-19, 19):
        for by in (-14, 14):
            m.add(cylinder(11, 11, 1.5, center=(bx, by, 91.0), seg=12, mat="metal_dark"))
    return m


def _fridge() -> Mesh:
    m = mesh_from_parts(RECIPES["FRIDGE"], "paint_white", chamfer=3.0)
    m.add(tube([(-6, 46.5, 80), (-6, 46.5, 160)], 1.5, seg=8, mat="metal"))
    m.add(tube([(6, 46.5, 80), (6, 46.5, 160)], 1.5, seg=8, mat="metal"))
    m.add(tube([(-30, 46.5, 68), (30, 46.5, 68)], 1.5, seg=8, mat="metal"))
    return m


def _sofa() -> Mesh:
    m = mesh_from_parts(RECIPES["SOFA"], ["fabric", "fabric", "fabric", "fabric"], chamfer=4.0)
    for cx in (-42, 0, 42):
        m.add(box((40, 70, 14), center=(cx, 2, 50), chamfer=5, mat="fabric_warm"))
    return m


def _armchair() -> Mesh:
    m = mesh_from_parts(RECIPES["ARMCHAIR"], "fabric_warm", chamfer=4.0)
    m.add(box((50, 68, 12), center=(0, 6, 50), chamfer=5, mat="leather"))
    return m


def _gun() -> Mesh:
    # Pistol silhouette in (y, z), extruded across X; sits at tabletop height.
    m = Mesh()
    m.add(prism([(-9, 7), (9, 7), (9, 12), (-9, 12)], "x", -2, 2, mat="metal_dark"))
    m.add(prism([(-8, 0), (-3, 0), (-1, 7), (-6, 7)], "x", -1.8, 1.8, mat="plastic_dark"))
    return m.translate(0, 0, 76.0 - 6.0)


def _rifle() -> Mesh:
    m = Mesh()
    m.add(prism([(-55, -3), (-20, -3), (-20, 1.5), (-55, -0.5)], "x", -3, 3, mat="wood"))
    m.add(prism([(-22, 0), (40, 0), (40, 3.5), (-22, 3.5)], "x", -2.5, 2.5, mat="metal_dark"))
    m.add(box((2, 12, 1.5), center=(0, 5, 4.25), mat="metal_dark"))  # rear sight rail
    m.add(tube([(0, 40, 1.7), (0, 55, 1.7)], 1.2, seg=8, mat="metal_dark"))
    return m.translate(0, 0, 76.0)


def _arrow() -> Mesh:
    m = Mesh()
    m.add(prism([(-9, -75), (9, -75), (9, 15), (-9, 15)], "z", 0, 2, mat="paint_yellow"))
    m.add(prism([(-15, 15), (15, 15), (0, 75)], "z", 0, 2, mat="paint_yellow"))
    return m


def _fuselage(length: float, radius: float, mat: str) -> Mesh:
    """Tapered fuselage along +Y (nose at +Y), centered on the origin."""
    hl = length / 2.0
    m = lathe(
        [(radius * 0.25, -hl), (radius * 0.7, -hl * 0.75), (radius, -hl * 0.35),
         (radius, hl * 0.45), (radius * 0.6, hl * 0.85), (0.0, hl)],
        seg=14, mat=mat,
    )
    return m.rotate(roll=-90)  # lathe axis Z -> +Y


def _planesmall() -> Mesh:
    m = _fuselage(700, 50, "paint_white").translate(0, 0, 150)
    m.add(box((1000, 150, 12), center=(0, 30, 205), chamfer=2, mat="paint_white"))
    m.add(box((12, 100, 120), center=(0, -320, 215), chamfer=2, mat="paint_red"))
    m.add(box((340, 90, 10), center=(0, -320, 160), chamfer=2, mat="paint_white"))
    return m


def _fighterjet() -> Mesh:
    m = _fuselage(1500, 55, "metal").translate(0, 0, 180)
    m.add(prism([(-450, -450), (-300, 150), (300, 150), (450, -450)], "z", 172, 187,
                mat="metal"))                                                       # delta wing
    m.add(box((15, 220, 160), center=(0, -620, 280), mat="metal"))
    m.add(uv_sphere((70, 200, 50), center=(0, 300, 235), mat="glass"))
    return m


def _commercialjet() -> Mesh:
    m = _fuselage(3500, 200, "paint_white").translate(0, 0, 350)
    m.add(box((3000, 550, 30), center=(0, 0, 330), chamfer=4, mat="paint_white"))
    m.add(box((30, 450, 800), center=(0, -1620, 850), chamfer=4, mat="paint_red"))
    m.add(box((1100, 300, 25), center=(0, -1560, 500), chamfer=4, mat="paint_white"))
    for sx in (-1, 1):
        eng = lathe([(85, 0), (85, 350), (60, 350)], seg=12, mat="metal")
        eng.rotate(roll=-90)
        m.add(eng.translate(sx * 700, -25, 240))
    return m


def _motorcycle() -> Mesh:
    m = mesh_from_parts(RECIPES["MOTORCYCLE"], PART_MATS["MOTORCYCLE"], chamfer=3.0)
    m.add(tube([(0, 62, 100), (0, 72, 55)], 2.0, seg=8, mat="metal"))  # front fork
    return m


_CUSTOM: dict[str, callable] = {
    "TOILET": _toilet,
    "SINK": _sink,
    "PLATE": _plate,
    "CUP": _cup,
    "FLOORLAMP": _floorlamp,
    "PLANT": _plant,
    "BUSH": _bush,
    "TREE": _tree,
    "CAR": _car,
    "BED": lambda: _bed(160.0),
    "BEDSINGLE": lambda: _bed(90.0),
    "BOOKCASE": _bookcase,
    "STOVE": _stove,
    "FRIDGE": _fridge,
    "SOFA": _sofa,
    "ARMCHAIR": _armchair,
    "GUN": _gun,
    "RIFLE": _rifle,
    "ARROW": _arrow,
    "PLANESMALL": _planesmall,
    "FIGHTERJET": _fighterjet,
    "COMMERCIALJET": _commercialjet,
    "MOTORCYCLE": _motorcycle,
}


def _recipe_builder(name: str):
    def build() -> Mesh:
        if name in _CUSTOM:
            return _CUSTOM[name]()
        return mesh_from_parts(RECIPES[name], PART_MATS.get(name, "plastic_light"))

    return build


MODEL_BUILDERS: dict[str, object] = {name: _recipe_builder(name) for name in RECIPES}


# ---------------------------------------------------------------------------
# Light-rig models (parts-derived from the fixtures' own rig geometry)
# ---------------------------------------------------------------------------

_FIXTURE_MATS: dict[str, list | str] = {
    "RIG_DEFAULT": ["metal_dark", "metal_dark", "metal_dark"],
    "RIG_FRAME": ["metal_dark", "metal_dark", "paper"],
    "RIG_SOFTBOX": ["metal_dark", "metal_dark", "plastic_dark"],
    "RIG_SLAB": ["metal_dark", "metal_dark", "plastic_light"],
    "RIG_LED": ["metal_dark", "metal_dark", "plastic_light"],
    "RIG_HUNGBALL": ["metal_dark", "paper"],
    "RIG_BALLOON": ["metal_dark", "paper"],
    "RIG_PRACTICAL": ["metal_dark", "metal_dark", "paper"],
    "RIG_STICK": ["metal_dark", "paper"],
    "RIG_SPEEDRAIL": "metal",
}


def _fixture_parts(model: str) -> list[dict]:
    for _needle, fixture in LIGHT_FIXTURES:
        if fixture.get("model") == model:
            return fixture["parts"]
    if LIGHT_FIXTURE_DEFAULT.get("model") == model:
        return LIGHT_FIXTURE_DEFAULT["parts"]
    raise KeyError(model)


def _fixture_builder(model: str):
    def build() -> Mesh:
        return mesh_from_parts(_fixture_parts(model), _FIXTURE_MATS.get(model, "metal_dark"))

    return build


FIXTURE_MODELS: dict[str, object] = {
    model: _fixture_builder(model)
    for model in sorted(
        {f.get("model") for _n, f in LIGHT_FIXTURES if f.get("model")}
        | ({LIGHT_FIXTURE_DEFAULT.get("model")} - {None})
    )
}


@lru_cache(maxsize=None)
def build_model(name: str) -> Mesh:
    """Build (and cache) the model for a recipe or rig, bbox-snapped to its
    blockout so every downstream calculation can treat them as identical."""
    if name in MODEL_BUILDERS:
        mesh = MODEL_BUILDERS[name]()
        lo, hi = recipe_bbox(RECIPES[name])
    elif name in FIXTURE_MODELS:
        mesh = FIXTURE_MODELS[name]()
        lo, hi = recipe_bbox(_fixture_parts(name))
    else:
        raise KeyError(name)
    (alo, ahi) = mesh.bbox()
    for i in range(3):
        want = hi[i] - lo[i]
        got = ahi[i] - alo[i]
        if want > 1e-6 and abs(got - want) / want > 0.15:
            raise ValueError(
                "%s model authored %.1f cm on axis %d, recipe says %.1f (>15%% off)"
                % (name, got, i, want)
            )
    return mesh.fit_to(lo, hi)


def model_names_for_scene(prop_kinds, light_kinds) -> list[str]:
    """The model files a scene needs: matched non-wall-insert props + rigs."""
    from ..emit.blockouts import WALL_OPENINGS, fixture_for, match_kind

    names = set()
    for kind in prop_kinds:
        matched = match_kind(kind)
        if matched and matched not in WALL_OPENINGS:
            names.add(matched)
    for kind in light_kinds:
        model = fixture_for(kind).get("model")
        if model:
            names.add(model)
    return sorted(names)
