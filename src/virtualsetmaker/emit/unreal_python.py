"""Emit an Unreal Engine 5.8 Python script from an IR :class:`~virtualsetmaker.ir.Scene`.

The emitted API surface also runs on UE 5.6/5.7 (spawnables go through the
LevelSequenceEditorSubsystem, which exists since the 5.6 deprecation).

The generator does all coordinate math up front (via :mod:`virtualsetmaker.coords`)
and embeds plain numbers in the output, so the emitted script is data-driven and
easy to read. It uses only the official built-in ``unreal`` module -- no
deprecated ``EditorLevelLibrary`` and no third-party Sequencer plugin.

Run the emitted script inside the editor's Output Log (switch the dropdown from
``Cmd`` to ``Python``), or with ``py "scene.py"``. Requires the *Python Editor
Script Plugin*.
"""

from __future__ import annotations

import json
import math

from .. import __version__
from ..coords import ir_to_ue_location, ir_to_ue_rotation, ir_to_ue_yaw, M_TO_CM
from ..ir import Camera, Scene
from ..settings import Defaults
# NOTE: geo.props imports emit.blockouts, so the geo imports here must be
# lazy (inside the functions that use them) to avoid a package-init cycle.
from .blockouts import (
    WALL_OPENINGS,
    fixture_for,
    native_span_for,
    recipe_bbox,
    recipe_for,
    recipe_height,
    recipe_span,
)

WALL_HEIGHT_CM = 250.0
WALL_THICKNESS_CM = 10.0
# Wall-insert snapping (doors/windows/openings onto the nearest wall segment):
# a piece counts as "in" a wall when its origin is within this distance of a
# segment's centerline and its yaw is parallel to the segment within this
# angle. Generous enough for hand-placed pieces (the test scene's window sits
# 1.35 cm off its wall), tight enough not to grab furniture near a wall.
WALL_SNAP_DIST_CM = 20.0
WALL_SNAP_ANGLE_DEG = 15.0
LIGHT_PITCH_DEG = -25.0
LIGHT_SUN_HEIGHT_CM = 800.0
LIGHT_SUN_PITCH_DEG = -50.0

# Skeletal meshes tried in order for actors. Manny for Shot Designer Type A
# characters, Quinn for Type B (<female>). These live in project content (the
# Third Person template pack), not engine content -- projects made from other
# templates (e.g. Film/Video "virtual production") ship no skeletal meshes at
# all. When nothing is found, the emitted script copies the mannequin assets
# from the engine install's Templates/ folder into the project and rescans;
# only if that also fails do actors fall back to tinted cylinders.
MANNY_CANDIDATES = [
    "/Game/Characters/Mannequins/Meshes/SKM_Manny.SKM_Manny",
    "/Game/ThirdPerson/Characters/Mannequins/Meshes/SKM_Manny.SKM_Manny",
    "/Game/Characters/Mannequin_UE4/Meshes/SK_Mannequin.SK_Mannequin",
    "/Game/Mannequin/Character/Mesh/SK_Mannequin.SK_Mannequin",
]
QUINN_CANDIDATES = [
    "/Game/Characters/Mannequins/Meshes/SKM_Quinn.SKM_Quinn",
    "/Game/ThirdPerson/Characters/Mannequins/Meshes/SKM_Quinn.SKM_Quinn",
]
# When none of the candidate paths load, the emitted script falls back to an
# Asset Registry sweep for any /Game skeletal mesh with one of these names
# (preference order) -- projects keep the mannequins under arbitrary folders.
MANNY_NAMES = ["SKM_Manny", "SKM_Manny_Simple", "SK_Mannequin"]
QUINN_NAMES = ["SKM_Quinn", "SKM_Quinn_Simple"]
# UE mannequin meshes are authored facing +Y: a raw SkeletalMeshActor at yaw 0
# looks down +Y, so facing direction phi needs a spawn yaw of phi - 90.
MANNEQUIN_YAW_OFFSET = -90.0
CUBE_MESH = "/Engine/BasicShapes/Cube.Cube"
CYLINDER_MESH = "/Engine/BasicShapes/Cylinder.Cylinder"
SPHERE_MESH = "/Engine/BasicShapes/Sphere.Sphere"
BASIC_SHAPE_MATERIAL = "/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"

# Fallback palette for hand-authored IR that carries only a colorName. Real
# .hcw files store a packed <color> int, which always wins. This is Shot
# Designer 1.80.8's exact character palette (decompiled Document.as).
COLOR_NAME_RGB = {
    "Red": (252, 131, 123),  # 16548731
    "Blue": (148, 184, 255),  # 9746687
    "Green": (118, 250, 138),  # 7797386
    "Cyan": (124, 255, 224),  # 8191968
    "Pink": (230, 155, 240),  # 15113200
    "Yellow": (255, 255, 134),  # 16777094
    "Gray": (187, 187, 187),  # 12303291
    "Extra": (255, 255, 255),  # 16777215
}


def _mesh_entry(
    model: str,
    parts: list[dict],
    x: float,
    y: float,
    yaw: float,
    sx: float,
    sy: float,
) -> dict:
    """Payload block for a shipped prop mesh.

    ``loc`` is the world XY of the *scaled, yawed recipe-bbox center* with z
    at the bbox bottom -- so the runtime's center/bottom placement lands the
    mesh exactly where the blockout stands, including off-center recipes
    (DOG's head, CRANE's jib) and tabletop props (PAPER floats at 75 cm).
    ``src_ext`` is the authored model extent (== recipe bbox extent by the
    geo/props contract): the runtime compares it against the imported
    asset's real bounds to catch an axis-rotating importer.
    """
    lo, hi = recipe_bbox(parts)
    cx = (lo[0] + hi[0]) / 2.0 * sx
    cy = (lo[1] + hi[1]) / 2.0 * sy
    rad = math.radians(yaw)
    return {
        "model": model,
        "loc": [
            x + cx * math.cos(rad) - cy * math.sin(rad),
            y + cx * math.sin(rad) + cy * math.cos(rad),
            lo[2],
        ],
        "yaw": yaw,
        "size": [(hi[0] - lo[0]) * sx, (hi[1] - lo[1]) * sy, hi[2] - lo[2]],
        "src_ext": [hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]],
    }


def _scene_payload(scene: Scene, options: Defaults | None = None) -> dict:
    """Pre-convert every object into Unreal-space numbers for embedding."""
    from ..geo.props import FIXTURE_MODELS, MODEL_BUILDERS

    options = options or Defaults()
    m2cm = scene.units_per_meter  # IR meters -> UE cm (1 SD unit = 1 cm => 100)

    actors = []
    for a in scene.actors:
        x, y, z = ir_to_ue_location(a.location, m2cm)
        rgb = a.color_rgb or COLOR_NAME_RGB.get(a.color)
        actors.append(
            {
                "loc": [x, y, 0.0],
                "yaw": ir_to_ue_yaw(a.yaw_deg),
                "label": a.name or a.id,
                "height_cm": a.height_m * 100.0,
                "color": a.color,
                "female": a.female,
                # Linear 0-1 for unreal.LinearColor; null = leave untinted.
                "rgb": None if rgb is None else [round(c / 255.0, 4) for c in rgb],
            }
        )

    # Wall centerlines come first: wall inserts (doors/windows/openings) snap
    # onto them and record the openings to carve, so the segments must exist
    # before props are baked. Cubes are emitted from these after the prop pass.
    raw_segments = []
    for w in scene.walls:
        pts = [ir_to_ue_location(pt, m2cm) for pt in w.points]
        pairs = list(zip(pts, pts[1:]))
        if w.closed_loop and len(pts) > 2:
            pairs.append((pts[-1], pts[0]))
        for (ax, ay, _az), (bx, by, _bz) in pairs:
            length = math.hypot(bx - ax, by - ay)
            if length < 1e-3:
                continue
            raw_segments.append(
                {
                    "a": (ax, ay),
                    "b": (bx, by),
                    "yaw": math.degrees(math.atan2(by - ay, bx - ax)),
                    "length": length,
                    "label": f"Wall_{w.id[:8]}",
                    "openings": [],  # (t0, t1, z0, z1) cuts along the segment
                }
            )

    props = []
    for p in scene.props:
        x, y, _z = ir_to_ue_location(p.location, m2cm)
        # Prop angle semantics, calibrated against a real scene (a sofa placed
        # flush against a wall + a door snapped into one):
        # * freestanding props (<GenericProp>, RotatorObject): the stored angle
        #   points at the prop's BACK — the recipe front (+Y local) faces
        #   angle+180, so the recipe frame's screen rotation is angle+90;
        # * set pieces (<GenericSet>, RotatorNoMenu: doors/windows/bars): the
        #   icon art is authored width-along-X and the angle is the direct
        #   screen rotation. (Not keyed on <snapPath> — pieces placed by hand
        #   never get one, and detached pieces keep stale snap fields.)
        screen_yaw = p.yaw_deg if p.is_set else p.yaw_deg + 90.0
        yaw = ir_to_ue_yaw(screen_yaw)
        matched, parts = recipe_for(p.kind)
        # objectScale is relative to the icon's native art size, not to our
        # recipe. When the native span is known, rescale so the emitted world
        # footprint equals objectScale * native (the icon's on-canvas span).
        # A None axis keeps the raw objectScale (true-to-life depths).
        sx, sy = p.scale.x, p.scale.y
        native = native_span_for(matched)
        if native is not None:
            bx, by = recipe_span(parts)
            if native[0] is not None and bx > 1e-6:
                sx *= native[0] / bx
            if native[1] is not None and by > 1e-6:
                sy *= native[1] / by
        # Wall inserts: snap flush onto the nearest parallel wall segment and
        # carve the opening out of it, so frames sit in a real hole instead of
        # clipping a solid wall at whatever angle the piece was dropped at.
        opening = WALL_OPENINGS.get(matched or "")
        if opening is not None:
            hit = _nearest_wall_segment(raw_segments, x, y, yaw)
            if hit is not None:
                seg, t = hit
                sax, say = seg["a"]
                ux, uy = _segment_dir(seg)
                x, y = sax + ux * t, say + uy * t
                yaw = _closest_parallel_yaw(seg["yaw"], yaw)
                half_w = recipe_span(parts)[0] * sx / 2.0
                seg["openings"].append((t - half_w, t + half_w, opening[0], opening[1]))
        entry = {
            "label": p.name,
            "kind": p.kind,
            "matched": matched,
            "parts": _bake_parts(parts, (x, y), yaw, (sx, sy)),
        }
        # Shipped-mesh upgrade: the model's bbox equals the recipe's bbox
        # (contract in geo/props.py), so fitting it to the same scaled box
        # the blockout occupies changes looks, never layout. Wall inserts
        # are excluded -- their carve pipeline stays pure blockout.
        if options.use_prop_meshes and matched in MODEL_BUILDERS and opening is None:
            entry["mesh"] = _mesh_entry(matched, parts, x, y, yaw, sx, sy)
        props.append(entry)

    wall_segments = []
    for seg in raw_segments:
        wall_segments.extend(_segment_pieces(seg, options.wall_height_cm))

    lights = []
    for lt in scene.lights:
        x, y, _z = ir_to_ue_location(lt.location, m2cm)
        yaw = ir_to_ue_yaw(lt.yaw_deg)
        fixture = fixture_for(lt.kind)
        cls = fixture["cls"]

        if cls == "directional":
            # The sun ignores position; park it high, steeply pitched, no rig.
            light_loc = [x, y, LIGHT_SUN_HEIGHT_CM]
            light_rot = [LIGHT_SUN_PITCH_DEG, yaw, 0.0]
        elif fixture["emit"] is None:
            light_loc = None  # rigging only (e.g. speed rail)
            light_rot = None
        else:
            ex, ey, ez = fixture["emit"]
            rad = math.radians(yaw)
            light_loc = [
                x + ex * math.cos(rad) - ey * math.sin(rad),
                y + ex * math.sin(rad) + ey * math.cos(rad),
                ez,
            ]
            # Point lights are omnidirectional; directed classes aim down-beam.
            light_rot = [0.0 if cls == "point" else LIGHT_PITCH_DEG, yaw, 0.0]

        light_entry = {
            "kind": lt.kind,
            "label": lt.kind or lt.id,
            "cls": cls,
            "parts": _bake_parts(fixture["parts"], (x, y), yaw, (1.0, 1.0)),
            "light_loc": light_loc,
            "light_rot": light_rot,
        }
        # Rig mesh upgrade (emit point math above is untouched by design).
        model = fixture.get("model")
        if options.use_prop_meshes and model in FIXTURE_MODELS and fixture["parts"]:
            light_entry["mesh"] = _mesh_entry(model, fixture["parts"], x, y, yaw, 1.0, 1.0)
        lights.append(light_entry)

    cameras = []
    for c in scene.cameras:
        cameras.append(_camera_payload(c, m2cm))

    shots = []
    cam_index = {c.id: i for i, c in enumerate(scene.cameras)}
    for s in scene.shots:
        shots.append(
            {
                "cam": cam_index.get(s.camera_id, 0),
                "start": s.start_s,
                "end": s.end_s,
                "name": s.name,
            }
        )

    return {
        "name": scene.name,
        "fps": options.frame_rate or scene.frame_rate,
        "duration": scene.duration_s,
        "actors": actors,
        "props": props,
        "wall_segments": wall_segments,
        "lights": lights,
        "cameras": cameras,
        "shots": shots,
    }


def _segment_dir(seg: dict) -> tuple[float, float]:
    """Unit direction vector of a raw wall segment."""
    (ax, ay), (bx, by) = seg["a"], seg["b"]
    length = seg["length"]
    return (bx - ax) / length, (by - ay) / length


def _nearest_wall_segment(segments: list[dict], x: float, y: float, yaw_deg: float):
    """Find the wall segment a wall insert sits in: ``(segment, t)`` or None.

    ``t`` is the distance along the segment (from its start) of the insert's
    projection. A segment qualifies when the point projects within it, lies
    within ``WALL_SNAP_DIST_CM`` of the centerline, and the insert's yaw is
    parallel to the segment within ``WALL_SNAP_ANGLE_DEG``; the closest
    qualifying centerline wins.
    """
    best = None
    best_d = WALL_SNAP_DIST_CM
    for seg in segments:
        ax, ay = seg["a"]
        ux, uy = _segment_dir(seg)
        t = (x - ax) * ux + (y - ay) * uy
        if t < 0.0 or t > seg["length"]:
            continue
        d = abs((y - ay) * ux - (x - ax) * uy)
        if d > best_d:
            continue
        delta = abs(yaw_deg - seg["yaw"]) % 180.0
        if min(delta, 180.0 - delta) > WALL_SNAP_ANGLE_DEG:
            continue
        best, best_d = (seg, t), d
    return best


def _closest_parallel_yaw(seg_yaw: float, yaw_deg: float) -> float:
    """Yaw exactly parallel to the segment, on the side the insert already
    faces (so a door's swing direction survives the alignment)."""
    d = (seg_yaw - yaw_deg + 180.0) % 360.0 - 180.0
    if abs(d) <= 90.0:
        return yaw_deg + d
    return yaw_deg + d - math.copysign(180.0, d)


def _segment_pieces(seg: dict, wall_height_cm: float) -> list[dict]:
    """Split one wall segment into spawnable cubes around its openings.

    No openings -> one full cube (the historical behavior). Each opening
    removes a (t0, t1) x (z0, z1) rectangle from the segment's elevation:
    full-height pieces remain between openings, a lintel above each opening,
    and a sill below (windows). Slivers under 1 cm are dropped.
    """
    length = seg["length"]
    (ax, ay), _ = seg["a"], seg["b"]
    ux, uy = _segment_dir(seg)
    pieces: list[dict] = []

    def emit(t0: float, t1: float, z0: float, z1: float) -> None:
        if t1 - t0 < 1.0 or z1 - z0 < 1.0:
            return
        tm = (t0 + t1) / 2.0
        pieces.append(
            {
                "loc": [ax + ux * tm, ay + uy * tm, (z0 + z1) / 2.0],
                "yaw": seg["yaw"],
                "length": t1 - t0,
                "height": z1 - z0,
                "label": seg["label"],
            }
        )

    # Clamp cuts to the segment, then merge overlaps into one cut covering
    # the union footprint and the union z-range (openings rarely overlap, but
    # a double door dropped over a window must not emit overlapping cubes).
    cuts: list[list[float]] = []
    for t0, t1, z0, z1 in sorted(seg["openings"]):
        t0, t1 = max(0.0, t0), min(length, t1)
        if t1 <= t0:
            continue
        if cuts and t0 <= cuts[-1][1]:
            last = cuts[-1]
            last[1] = max(last[1], t1)
            last[2] = min(last[2], z0)
            last[3] = max(last[3], z1)
        else:
            cuts.append([t0, t1, z0, z1])

    cursor = 0.0
    for t0, t1, z0, z1 in cuts:
        emit(cursor, t0, 0.0, wall_height_cm)
        emit(t0, t1, 0.0, z0)  # sill below a window opening
        emit(t0, t1, z1, wall_height_cm)  # lintel above the opening
        cursor = t1
    emit(cursor, length, 0.0, wall_height_cm)

    if len(pieces) > 1:
        for i, piece in enumerate(pieces):
            piece["label"] = f"{piece['label']}_{i}"
    return pieces


def _bake_parts(
    parts: list[dict],
    origin_xy: tuple[float, float],
    yaw_deg: float,
    footprint_scale: tuple[float, float],
) -> list[dict]:
    """Convert recipe parts (prop-local cm) to world-space spawn transforms.

    The prop's yaw rotates each part offset about the prop origin, and Shot
    Designer's objectScaleX/Y stretches the footprint (heights stay true to
    life). Yaw composition is exact under UE's rotator order
    (``Rz(yaw)·Ry(pitch)·Rx(roll)``): adding the prop yaw to a part's own yaw is
    the same as rotating the finished part about Z.

    Recipes are authored in Shot Designer screen orientation (+Y toward the
    prop's front); since the screen->Unreal map is chirality-preserving (see
    :mod:`virtualsetmaker.coords`), the local frame carries over unchanged.
    """
    ox, oy = origin_xy
    sx, sy = footprint_scale
    rad = math.radians(yaw_deg)
    cos_y, sin_y = math.cos(rad), math.sin(rad)

    baked = []
    for part in parts:
        px, py, pz = part["offset"]
        px, py = px * sx, py * sy
        wx = ox + px * cos_y - py * sin_y
        wy = oy + px * sin_y + py * cos_y
        pitch, part_yaw, roll = part["rot"]
        size = part["size"]
        baked.append(
            {
                "shape": part["shape"],
                "loc": [wx, wy, pz],
                "rot": [pitch, yaw_deg + part_yaw, roll],
                "scale": [size[0] * sx / 100.0, size[1] * sy / 100.0, size[2] / 100.0],
            }
        )
    return baked


def _camera_payload(c: Camera, m2cm: float) -> dict:
    keys = []
    focals = set()
    for kf in c.keyframes:
        x, y, z = ir_to_ue_location(kf.location, m2cm)
        pitch, yaw, roll = ir_to_ue_rotation(kf.pitch_deg, kf.yaw_deg, kf.roll_deg)
        keys.append({"t": kf.time_s, "loc": [x, y, z], "rot": [pitch, yaw, roll], "focal": kf.focal_length_mm})
        focals.add(round(kf.focal_length_mm, 3))
    return {
        "label": c.name or c.id,
        "keys": keys,
        "focal0": c.keyframes[0].focal_length_mm if c.keyframes else 35.0,
        "focal_animated": len(focals) > 1,
        "sensor": [c.sensor_width_mm, c.sensor_height_mm],
    }


# --- the runtime half of the emitted script (pure text, no f-strings) --------

_RUNTIME = r'''
if unreal is None:
    raise SystemExit(
        "This script must be run inside the Unreal editor "
        "(Output Log: switch Cmd -> Python, or: py \"scene.py\")."
    )


def _v(t):
    return unreal.Vector(float(t[0]), float(t[1]), float(t[2]))


def _r(t):
    # t is [pitch, yaw, roll]. The Python Rotator ctor is (roll, pitch, yaw) --
    # NOT the C++ FRotator order -- so pass keywords to be order-proof.
    return unreal.Rotator(roll=float(t[2]), pitch=float(t[0]), yaw=float(t[1]))


def _find_mannequin(candidates, names):
    """Load a mannequin mesh: explicit paths first, then an Asset Registry
    sweep for any /Game skeletal mesh with a known name (preference order) --
    projects keep the Third Person pack under arbitrary folders."""
    for p in candidates:
        asset = unreal.EditorAssetLibrary.load_asset(p)
        if asset:
            unreal.log("VSM: using mannequin %s" % p)
            return asset
    try:
        registry = unreal.AssetRegistryHelpers.get_asset_registry()
        # UE 5.8: ClassPaths is not editor-settable on an ARFilter instance
        # (set_editor_property raises "cannot be edited on instances"). Pass it
        # to the constructor instead.
        arf = unreal.ARFilter(
            class_paths=[unreal.TopLevelAssetPath("/Script/Engine", "SkeletalMesh")],
            package_paths=["/Game"],
            recursive_paths=True,
            recursive_classes=True,
        )
        by_name = {}
        for data in registry.get_assets(arf):
            name = str(data.asset_name)
            if name in names and name not in by_name:
                by_name[name] = data
        for name in names:
            if name in by_name:
                asset = unreal.AssetRegistryHelpers.get_asset(by_name[name])
                if asset is not None:
                    unreal.log(
                        "VSM: using mannequin %s (found via Asset Registry)"
                        % by_name[name].package_name
                    )
                    return asset
    except Exception as exc:
        unreal.log_warning("VSM: Asset Registry mannequin search failed: %s" % exc)
    return None


def _install_mannequin_pack():
    """Copy the UE mannequins from the engine's Third Person template into
    this project. Projects made from the Film/Video ("virtual production") or
    Blank templates ship no skeletal meshes at all, but every engine install
    carries the mannequin assets on disk under <install root>/Templates/.
    Never overwrites existing files. Returns True when the assets are in
    place and the Asset Registry has been rescanned (so a retry can load them)."""
    import os
    import shutil

    try:
        root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.root_dir())
        templates = os.path.join(root, "Templates")
        marker = os.path.join("Mannequins", "Meshes", "SKM_Manny.uasset")
        src = None
        if os.path.isdir(templates):
            for tpl in sorted(os.listdir(templates)):
                cand = os.path.join(templates, tpl, "Content", "Characters")
                if os.path.isfile(os.path.join(cand, marker)):
                    src = cand
                    break
        if src is None:
            unreal.log_warning(
                "VSM: no mannequin content found under %s -- cannot auto-install "
                "Mannys (source-built engine without templates?)" % templates
            )
            return False
        dest = os.path.join(
            unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()),
            "Characters",
        )
        copied = 0
        for dirpath, dirnames, filenames in os.walk(src):
            # Animations and control rigs aren't needed to pose a static
            # blocking mannequin; leave them out to keep the project lean.
            dirnames[:] = [
                d for d in dirnames if d.lower() not in ("animations", "anims", "rigs")
            ]
            out = os.path.join(dest, os.path.relpath(dirpath, src))
            os.makedirs(out, exist_ok=True)
            for fn in filenames:
                target = os.path.join(out, fn)
                if not os.path.exists(target):
                    shutil.copy2(os.path.join(dirpath, fn), target)
                    copied += 1
        unreal.log(
            "VSM: no mannequins in this project -- installed the UE mannequins "
            "into /Game/Characters (%d files copied from %s)" % (copied, src)
        )
        registry = unreal.AssetRegistryHelpers.get_asset_registry()
        registry.scan_paths_synchronous(["/Game/Characters"], force_rescan=True)
        return True
    except Exception as exc:
        unreal.log_warning("VSM: mannequin auto-install failed: %s" % exc)
        return False


def _props_dir():
    """The vsm_props/ folder of shipped OBJ models, written by the converter
    next to this script (with a baked absolute fallback for Output Log
    contexts where __file__ is unreliable)."""
    import os

    try:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), VSM_PROPS_DIRNAME)
        if os.path.isdir(d):
            return d
    except Exception:
        pass
    return VSM_PROPS_DIR_ABS


def _slot_material(slot):
    """Get-or-create MI_VSM_<slot>: a MaterialInstanceConstant parented to
    the engine BasicShapeMaterial with its Color parameter set from the
    embedded palette. Deterministic colors, whether or not the OBJ importer
    honored the .mtl."""
    rgb = VSM_MATERIAL_COLORS.get(slot)
    if rgb is None:
        return None
    folder = UE_CONTENT_PATH + "/Materials"
    full = folder + "/MI_VSM_" + slot
    if unreal.EditorAssetLibrary.does_asset_exist(full):
        return unreal.EditorAssetLibrary.load_asset(full)
    base = unreal.EditorAssetLibrary.load_asset(BASIC_SHAPE_MATERIAL)
    if base is None:
        return None
    factory = unreal.MaterialInstanceConstantFactoryNew()
    parented = False
    try:
        # Removed in UE 5.8; harmless where it still exists (5.6/5.7).
        factory.set_editor_property("initial_parent", base)
        parented = True
    except Exception:
        pass
    mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "MI_VSM_" + slot, folder, unreal.MaterialInstanceConstant, factory
    )
    if mi is not None:
        if not parented:
            unreal.MaterialEditingLibrary.set_material_instance_parent(mi, base)
        unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(
            mi, "Color", unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0)
        )
        unreal.MaterialEditingLibrary.update_material_instance(mi)
        unreal.EditorAssetLibrary.save_loaded_asset(mi)
    return mi


def _colorize_prop_mesh(mesh):
    """Assign the flat VSM material instances by material-slot name."""
    try:
        for i, sm in enumerate(mesh.static_materials):
            slot = str(sm.material_slot_name)
            mi = _slot_material(slot)
            if mi is not None:
                mesh.set_material(i, mi)
        unreal.EditorAssetLibrary.save_loaded_asset(mesh)
    except Exception as exc:
        unreal.log_warning("VSM: could not colorize mesh: %s" % exc)


# One import/load attempt per model per run.
_MESH_MEMO = {}


def _load_or_import_prop_mesh(model):
    """Load /Game .../Meshes/SM_VSM_<model>, importing the shipped OBJ on
    first use (synchronous AssetImportTask -> Interchange). None = caller
    falls back to blockout parts."""
    import os

    if model in _MESH_MEMO:
        return _MESH_MEMO[model]
    mesh = None
    asset_path = UE_CONTENT_PATH + "/Meshes/SM_VSM_" + model
    try:
        if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
            mesh = unreal.EditorAssetLibrary.load_asset(asset_path)
        else:
            obj = os.path.join(_props_dir(), "SM_VSM_%s.obj" % model)
            if not os.path.isfile(obj):
                unreal.log_warning(
                    "VSM: prop model file missing (%s) -- keep the vsm_props folder "
                    "next to this script; using blockout for %s" % (obj, model)
                )
            else:
                task = unreal.AssetImportTask()
                task.set_editor_property("filename", obj)
                task.set_editor_property("destination_path", UE_CONTENT_PATH + "/Meshes")
                task.set_editor_property("automated", True)
                task.set_editor_property("replace_existing", True)
                task.set_editor_property("save", True)
                unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
                mesh = unreal.EditorAssetLibrary.load_asset(asset_path)
                if mesh is not None:
                    unreal.log("VSM: imported prop mesh %s from %s" % (asset_path, obj))
                    _colorize_prop_mesh(mesh)
                else:
                    unreal.log_warning(
                        "VSM: import produced no asset at %s -- using blockout" % asset_path
                    )
    except Exception as exc:
        unreal.log_warning("VSM: import failed for %s: %s -- using blockout" % (model, exc))
        mesh = None
    _MESH_MEMO[model] = mesh
    return mesh


def _spawn_prop_mesh(m, what):
    """Spawn a shipped prop mesh fitted to the blockout's exact box.

    Scale comes from the loaded asset's own bounding box; the bbox center
    goes to m["loc"] XY and the bbox bottom to m["loc"][2].

    The loaded bounds are compared against the authored extents to detect
    how the importer treated the file's axes. UE 5.8's Interchange imports
    OBJ verbatim (matches how current files are written); assets imported
    from the older Y-up files arrive with authored Y/Z swapped and are
    AUTO-CORRECTED here with a roll-90 + mirrored-Z spawn, so re-importing
    is never required. Only bounds matching neither pattern fall back."""
    import math as _math

    mesh = _load_or_import_prop_mesh(m["model"])
    if mesh is None:
        return None
    try:
        box = mesh.get_bounding_box()
        lo = (box.min.x, box.min.y, box.min.z)
        hi = (box.max.x, box.max.y, box.max.z)
        ext = tuple(hi[i] - lo[i] for i in range(3))
        if min(ext) < 0.05:
            return None
        src = m["src_ext"]

        def _rel(a, b):
            return abs(a - b) / max(b, 1e-3)

        direct = max(_rel(ext[i], src[i]) for i in range(3))
        swapped = max(_rel(ext[0], src[0]), _rel(ext[1], src[2]), _rel(ext[2], src[1]))
        # Fit factors per AUTHOR axis (positive; signs live in the spawn).
        f = [m["size"][i] / max(src[i], 1e-3) for i in range(3)]
        if direct <= 0.05 or direct <= swapped:
            if direct > 0.05:
                unreal.log_warning(
                    "VSM: mesh %s bounds differ %.0f%% from authored -- fitting anyway"
                    % (m["model"], direct * 100.0)
                )
            # Loaded local axes == author axes.
            pre_lo = (f[0] * lo[0], f[1] * lo[1], f[2] * lo[2])
            pre_hi = (f[0] * hi[0], f[1] * hi[1], f[2] * hi[2])
            rot = [0.0, m["yaw"], 0.0]
            scale = (f[0], f[1], f[2])
        else:
            # Legacy Y-up file imported verbatim: authored Y/Z arrive
            # swapped. Rz(yaw)*Rx(90)*diag(fx, fz, -fy) maps the loaded
            # local (x, z_a, y_a) back onto the author frame exactly.
            unreal.log(
                "VSM: mesh %s is a legacy Y-up import -- spawning with axis "
                "correction (delete %s/Meshes to re-import cleanly)"
                % (m["model"], UE_CONTENT_PATH)
            )
            pre_lo = (f[0] * lo[0], f[1] * lo[2], f[2] * lo[1])
            pre_hi = (f[0] * hi[0], f[1] * hi[2], f[2] * hi[1])
            rot = [0.0, m["yaw"], 90.0]
            scale = (f[0], f[2], -f[1])
        cx = (pre_lo[0] + pre_hi[0]) / 2.0
        cy = (pre_lo[1] + pre_hi[1]) / 2.0
        bz = min(pre_lo[2], pre_hi[2])
        rad = _math.radians(m["yaw"])
        wx = m["loc"][0] - (cx * _math.cos(rad) - cy * _math.sin(rad))
        wy = m["loc"][1] - (cx * _math.sin(rad) + cy * _math.cos(rad))
        actor = _spawn_object(mesh, [wx, wy, m["loc"][2] - bz], rot, what)
        if actor is not None:
            actor.set_actor_scale3d(unreal.Vector(scale[0], scale[1], scale[2]))
        return actor
    except Exception as exc:
        unreal.log_warning("VSM: mesh fit failed for %s (%s) -- using blockout" % (what, exc))
        return None


_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

# Names of objects whose spawn failed, so the end-of-run summary can list them.
# One bad object must not abort the whole build (an uncaught exception here
# would silently drop everything that spawns after it).
_FAILURES = []


def _spawn(fn, what):
    try:
        actor = fn()
    except Exception as exc:
        actor = None
        unreal.log_error("VSM: exception spawning %s: %s" % (what, exc))
    if actor is None:
        _FAILURES.append(what)
        unreal.log_error("VSM: could not spawn %s" % what)
    return actor


def _spawn_object(mesh, loc, rot, what):
    return _spawn(lambda: _actor_sub.spawn_actor_from_object(mesh, _v(loc), _r(rot)), what)


def _spawn_class(cls, loc, rot, what):
    return _spawn(lambda: _actor_sub.spawn_actor_from_class(cls, _v(loc), _r(rot)), what)


def _secs_to_frame(tick, t):
    return unreal.FrameNumber(int(round(t * tick.numerator / tick.denominator)))


def _key(chan, frame, value):
    # _secs_to_frame gives frames in the sequence's TICK resolution, but
    # add_key defaults time_unit to DISPLAY_RATE -- so without this an animated
    # key at t=2s (tick frame ~48000) is read as ~48000 display frames and lands
    # ~1600s away, off the section, and the move silently vanishes. Say TICK.
    # NOTE: MovieSceneTimeUnit is the UE 5.4+ name of this enum; the pre-5.4
    # Sequence* name was removed entirely, so do not "fix" it back.
    chan.add_key(frame, value, time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION)


def _tint(actor, rgb):
    # Color a capsule-fallback actor with the Shot Designer character color.
    # Dynamic material instances are session-transient -- fine for a blocking
    # aid. Fails soft: a missing material or parameter just logs a warning.
    if rgb is None:
        return
    try:
        smc = actor.get_component_by_class(unreal.StaticMeshComponent)
        base = unreal.EditorAssetLibrary.load_asset(BASIC_SHAPE_MATERIAL)
        if smc is None or base is None:
            return
        mid = smc.create_dynamic_material_instance(0, base)
        if mid:
            mid.set_vector_parameter_value(
                "Color", unreal.LinearColor(float(rgb[0]), float(rgb[1]), float(rgb[2]), 1.0)
            )
    except Exception as exc:
        unreal.log_warning("VSM: could not tint actor: %s" % exc)


def build_scene():
    # First line of every run: pins WHICH generator produced the running
    # script, so a stale re-run is obvious from the Output Log alone.
    unreal.log("VSM: virtualSetmaker v%s script starting" % VSM_VERSION)
    meshes = {
        "cube": unreal.EditorAssetLibrary.load_asset(CUBE_MESH),
        "cylinder": unreal.EditorAssetLibrary.load_asset(CYLINDER_MESH),
        "sphere": unreal.EditorAssetLibrary.load_asset(SPHERE_MESH),
    }
    cube = meshes["cube"]
    cylinder = meshes["cylinder"]
    manny = _find_mannequin(MANNY_CANDIDATES, MANNY_NAMES)
    if manny is None and _install_mannequin_pack():
        manny = _find_mannequin(MANNY_CANDIDATES, MANNY_NAMES)
    quinn = _find_mannequin(QUINN_CANDIDATES, QUINN_NAMES) or manny
    if manny is None:
        unreal.log_error(
            "VSM: no UE Mannequin skeletal mesh found ANYWHERE in this project "
            "(searched %s) and auto-install from the engine templates failed -- "
            "actors will spawn as cylinder placeholders. "
            "To get Mannys/Quinns: Content Drawer -> +Add -> "
            "'Add Feature or Content Pack...' -> Third Person -> Add to Project, "
            "then run this script again." % ", ".join(MANNY_NAMES)
        )
    for shape, mesh in meshes.items():
        if mesh is None:
            unreal.log_error(
                "VSM: engine basic shape %r failed to load -- %s blockout parts cannot spawn"
                % (shape, shape)
            )
    spawned = {
        "actors": 0, "props": 0, "prop_meshes": 0, "prop_parts": 0,
        "walls": 0, "lights": 0, "cameras": 0,
    }

    # One transaction for all the blockout geometry: a single undo entry and
    # one batch of editor notifications instead of one per spawned actor.
    with unreal.ScopedEditorTransaction("virtualSetmaker build"):
        # --- actors ---------------------------------------------------------
        for a in SCENE["actors"]:
            what = "actor '%s'" % a["label"]
            mannequin = quinn if a["female"] else manny
            actor = None
            if mannequin is not None:
                # Mannequin meshes are authored facing +Y; offset the spawn yaw so
                # the Manny looks where the Shot Designer character faces.
                actor = _spawn_object(
                    mannequin, a["loc"], [0.0, a["yaw"] + MANNEQUIN_YAW_OFFSET, 0.0], what
                )
                if actor is not None:
                    unreal.log(
                        "VSM: %s -> mannequin at (%.0f, %.0f, %.0f)"
                        % (what, a["loc"][0], a["loc"][1], a["loc"][2])
                    )
            if actor is None and cylinder is not None:
                # No mannequin, or its spawn failed: a tinted cylinder beats a
                # silently missing character.
                h = a["height_cm"]
                loc = [a["loc"][0], a["loc"][1], h / 2.0]
                actor = _spawn_object(cylinder, loc, [0.0, a["yaw"], 0.0], what)
                if actor is not None:
                    actor.set_actor_scale3d(unreal.Vector(0.4, 0.4, h / 100.0))
                    _tint(actor, a["rgb"])  # mannequins keep their own materials
                    unreal.log(
                        "VSM: %s -> cylinder placeholder at (%.0f, %.0f)"
                        % (what, a["loc"][0], a["loc"][1])
                    )
            if actor is None:
                unreal.log_error("VSM: nothing could spawn for " + what)
                continue
            spawned["actors"] += 1
            actor.set_actor_label("Actor_" + a["label"])
            actor.set_folder_path("VSM/Actors")

        # --- props (multi-part blockouts) ------------------------------------
        keep_world = unreal.AttachmentRule.KEEP_WORLD
        for p in SCENE["props"]:
            if not p["parts"] and "mesh" not in p:
                unreal.log_warning(
                    "VSM: prop '%s' (kind %r) has no blockout parts -- nothing to spawn"
                    % (p["label"], p["kind"])
                )
                continue
            # Real mesh first (Starter Content); blockout parts are the
            # fallback whenever the mesh is unavailable or fails to fit.
            m = p.get("mesh")
            if m is not None:
                actor = _spawn_prop_mesh(m, "prop '%s' mesh" % p["label"])
                if actor is not None:
                    spawned["props"] += 1
                    spawned["prop_meshes"] += 1
                    actor.set_actor_label("Prop_" + p["label"])
                    actor.set_folder_path("VSM/Props")
                    continue
            parent = None
            for i, part in enumerate(p["parts"]):
                mesh = meshes.get(part["shape"]) or cube
                if mesh is None:
                    continue
                actor = _spawn_object(
                    mesh, part["loc"], part["rot"], "prop '%s' part %d" % (p["label"], i)
                )
                if actor is None:
                    continue
                spawned["prop_parts"] += 1
                actor.set_actor_scale3d(_v(part["scale"]))
                if parent is None:
                    parent = actor
                    actor.set_actor_label("Prop_" + p["label"])
                else:
                    actor.set_actor_label("Prop_%s_part%d" % (p["label"], i))
                    actor.attach_to_actor(parent, "", keep_world, keep_world, keep_world, False)
                actor.set_folder_path("VSM/Props")
            if parent is not None:
                spawned["props"] += 1

        # --- walls (blockout) -------------------------------------------
        if cube is not None:
            for w in SCENE["wall_segments"]:
                actor = _spawn_object(cube, w["loc"], [0.0, w["yaw"], 0.0], "wall '%s'" % w["label"])
                if actor is None:
                    continue
                spawned["walls"] += 1
                actor.set_actor_scale3d(
                    unreal.Vector(w["length"] / 100.0, WALL_THICKNESS_CM / 100.0, w["height"] / 100.0)
                )
                actor.set_actor_label(w["label"])
                actor.set_folder_path("VSM/Set")

        # --- lights ---------------------------------------------------------
        light_classes = {
            "spot": unreal.SpotLight,
            "rect": unreal.RectLight,
            "point": unreal.PointLight,
            "directional": unreal.DirectionalLight,
        }
        for lt in SCENE["lights"]:
            # rig geometry: shipped fixture mesh first, blockout parts fallback
            rig = None
            lm = lt.get("mesh")
            if lm is not None:
                rig = _spawn_prop_mesh(lm, "light rig '%s' mesh" % lt["label"])
                if rig is not None:
                    rig.set_actor_label("LightRig_" + lt["label"])
                    rig.set_folder_path("VSM/Lights")
            for i, part in enumerate(lt["parts"] if rig is None else []):
                mesh = meshes.get(part["shape"]) or cube
                if mesh is None:
                    continue
                actor = _spawn_object(
                    mesh, part["loc"], part["rot"], "light rig '%s' part %d" % (lt["label"], i)
                )
                if actor is None:
                    continue
                actor.set_actor_scale3d(_v(part["scale"]))
                if rig is None:
                    rig = actor
                    actor.set_actor_label("LightRig_" + lt["label"])
                else:
                    actor.set_actor_label("LightRig_%s_part%d" % (lt["label"], i))
                    actor.attach_to_actor(rig, "", keep_world, keep_world, keep_world, False)
                actor.set_folder_path("VSM/Lights")

            # the actual light, attached to the rig so they move together
            if lt["light_loc"] is not None:
                light = _spawn_class(
                    light_classes.get(lt["cls"], unreal.SpotLight),
                    lt["light_loc"],
                    lt["light_rot"],
                    "light '%s'" % lt["label"],
                )
                if light is None:
                    continue
                spawned["lights"] += 1
                light.set_actor_label("Light_" + lt["label"])
                light.set_folder_path("VSM/Lights")
                if rig is not None:
                    light.attach_to_actor(rig, "", keep_world, keep_world, keep_world, False)
            elif rig is not None:
                spawned["lights"] += 1  # rigging-only fixture (e.g. speed rail)

    # --- level sequence + cameras --------------------------------------
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    seq = tools.create_asset(
        "SEQ_" + SCENE["name"], UE_CONTENT_PATH, unreal.LevelSequence, unreal.LevelSequenceFactoryNew()
    )
    seq.set_display_rate(unreal.FrameRate(int(SCENE["fps"]), 1))
    seq.set_playback_end_seconds(float(SCENE["duration"]))
    tick = seq.get_tick_resolution()  # fetched once; constant for the sequence

    # UE 5.6+ moved spawnable creation to the Level Sequence Editor Subsystem,
    # which only operates on the sequence currently open in Sequencer.
    ls_sub = unreal.get_editor_subsystem(unreal.LevelSequenceEditorSubsystem)
    unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)

    bindings = []
    for cam in SCENE["cameras"]:
        k0 = cam["keys"][0]
        actor = _spawn_class(
            unreal.CineCameraActor, k0["loc"], k0["rot"], "camera '%s'" % cam["label"]
        )
        if actor is None:
            bindings.append(None)  # keep shot indices aligned
            continue
        spawned["cameras"] += 1
        actor.set_actor_label(cam["label"])
        comp = actor.get_cine_camera_component()
        # Set focal length and filmback BEFORE binding: spawnables snapshot a
        # template here.
        comp.set_editor_property("current_focal_length", float(cam["focal0"]))
        fb = comp.get_editor_property("filmback")
        fb.set_editor_property("sensor_width", float(cam["sensor"][0]))
        fb.set_editor_property("sensor_height", float(cam["sensor"][1]))
        comp.set_editor_property("filmback", fb)
        binding = ls_sub.add_spawnable_from_instance(seq, actor)
        bindings.append(binding)

        # add_spawnable_from_instance runs through the open Sequencer, which
        # honors the editor's "default tracks" preference and may auto-create
        # a transform track holding the spawn pose. Adding a SECOND transform
        # track makes Sequencer blend the two absolute transforms -- a moving
        # camera then travels half the intended distance and ends between its
        # keyed pose and the spawn pose. Reuse the existing track (wiping its
        # sections) so exactly one transform track drives the camera.
        existing = binding.find_tracks_by_exact_type(unreal.MovieScene3DTransformTrack)
        if existing:
            track = existing[0]
            for stale in list(track.get_sections()):
                track.remove_section(stale)
        else:
            track = binding.add_track(unreal.MovieScene3DTransformTrack)
        section = track.add_section()
        section.set_start_frame_seconds(cam["keys"][0]["t"])
        section.set_end_frame_seconds(max(cam["keys"][-1]["t"], float(SCENE["duration"])))
        chans = section.get_all_channels()  # locX,locY,locZ, rotX(roll),rotY(pitch),rotZ(yaw), sclX,Y,Z
        for kf in cam["keys"]:
            f = _secs_to_frame(tick, kf["t"])
            loc, rot = kf["loc"], kf["rot"]  # rot = [pitch, yaw, roll]
            _key(chans[0], f, loc[0])
            _key(chans[1], f, loc[1])
            _key(chans[2], f, loc[2])
            _key(chans[3], f, rot[2])  # roll
            _key(chans[4], f, rot[0])  # pitch
            _key(chans[5], f, rot[1])  # yaw

        if cam["focal_animated"]:
            comp_binding = seq.add_possessable(comp)
            comp_binding.set_parent(binding)
            ftrack = comp_binding.add_track(unreal.MovieSceneFloatTrack)
            ftrack.set_property_name_and_path("CurrentFocalLength", "CurrentFocalLength")
            fsection = ftrack.add_section()
            fsection.set_start_frame_seconds(cam["keys"][0]["t"])
            fsection.set_end_frame_seconds(cam["keys"][-1]["t"])
            fchan = fsection.get_all_channels()[0]
            for kf in cam["keys"]:
                _key(fchan, _secs_to_frame(tick, kf["t"]), float(kf["focal"]))

    # --- camera cut track ----------------------------------------------
    if any(b is not None for b in bindings):
        cut = seq.add_track(unreal.MovieSceneCameraCutTrack)
        for shot in SCENE["shots"]:
            if bindings[shot["cam"]] is None:
                unreal.log_error("VSM: shot '%s' skipped -- its camera failed to spawn" % shot["name"])
                continue
            cs = cut.add_section()
            cs.set_start_frame_seconds(shot["start"])
            cs.set_end_frame_seconds(shot["end"])
            # Binding-ID API moved twice: 5.7 dropped the binding proxy's
            # own method, 5.8 dropped make_binding_id (whose deprecation
            # notice says to migrate to the get_binding_id helper). Probe
            # so one script runs on 5.6-5.8.
            mse = unreal.MovieSceneSequenceExtensions
            if hasattr(mse, "get_binding_id"):
                binding_id = mse.get_binding_id(seq, bindings[shot["cam"]])
            else:
                binding_id = mse.make_binding_id(seq, bindings[shot["cam"]])
            cs.set_camera_binding_id(binding_id)

    unreal.EditorAssetLibrary.save_loaded_asset(seq)
    unreal.log(
        "virtualSetmaker: built '%s' -- spawned %d/%d actors, %d/%d props "
        "(%d real meshes, %d blockout parts), "
        "%d/%d wall segments, %d/%d lights, %d/%d cameras"
        % (
            SCENE["name"],
            spawned["actors"], len(SCENE["actors"]),
            spawned["props"], len(SCENE["props"]),
            spawned["prop_meshes"],
            spawned["prop_parts"],
            spawned["walls"], len(SCENE["wall_segments"]),
            spawned["lights"], len(SCENE["lights"]),
            spawned["cameras"], len(SCENE["cameras"]),
        )
    )
    if not SCENE["props"]:
        unreal.log_warning(
            "virtualSetmaker: this scene data contains NO props. If your Shot Designer "
            "scene does have props, re-export with the latest converter and check its "
            "warnings -- unsupported object types are reported there."
        )
    if _FAILURES:
        unreal.log_warning(
            "virtualSetmaker: %d spawn(s) failed: %s" % (len(_FAILURES), ", ".join(_FAILURES))
        )
    return seq


build_scene()
'''


def build_script(
    scene: Scene, options: Defaults | None = None, props_dir_abs: str = ""
) -> str:
    """Return the full Unreal Python script for ``scene`` as a string.

    ``props_dir_abs`` is the absolute path of the vsm_props/ model folder the
    converter wrote (baked in as the fallback for when the running script's
    ``__file__`` is unreliable); empty means "next to the script only".
    """
    from ..geo.materials import MATERIALS

    options = options or Defaults()
    payload = json.dumps(_scene_payload(scene, options), indent=2)
    header = (
        "# Auto-generated by virtualSetmaker v%s. Run INSIDE the Unreal 5.8 editor (works on 5.6+):\n"
        "#   Output Log -> switch 'Cmd' to 'Python', then:  py \"%s.py\"\n"
        "# Requires the 'Python Editor Script Plugin'.\n"
        "import json\n"
        "try:\n"
        "    import unreal\n"
        "except ModuleNotFoundError:  # not inside the Unreal editor\n"
        "    unreal = None\n\n" % (__version__, scene.name)
    )
    constants = (
        "VSM_VERSION = %r\n"
        "MANNY_CANDIDATES = %r\n"
        "QUINN_CANDIDATES = %r\n"
        "MANNY_NAMES = %r\n"
        "QUINN_NAMES = %r\n"
        "MANNEQUIN_YAW_OFFSET = %r\n"
        "CUBE_MESH = %r\n"
        "CYLINDER_MESH = %r\n"
        "SPHERE_MESH = %r\n"
        "BASIC_SHAPE_MATERIAL = %r\n"
        "WALL_THICKNESS_CM = %r\n"
        "WALL_HEIGHT_CM = %r\n"
        "UE_CONTENT_PATH = %r\n"
        "VSM_PROPS_DIRNAME = %r\n"
        "VSM_PROPS_DIR_ABS = %r\n"
        "VSM_MATERIAL_COLORS = %r\n\n"
        # JSON is not Python source (false/true/null), so it must be parsed,
        # not pasted in as a literal.
        'SCENE = json.loads(r"""\n%s\n""")\n'
        % (
            __version__,
            options.manny_paths or MANNY_CANDIDATES,
            options.quinn_paths or QUINN_CANDIDATES,
            MANNY_NAMES,
            QUINN_NAMES,
            MANNEQUIN_YAW_OFFSET,
            CUBE_MESH,
            CYLINDER_MESH,
            SPHERE_MESH,
            BASIC_SHAPE_MATERIAL,
            options.wall_thickness_cm,
            options.wall_height_cm,
            options.ue_content_path,
            "vsm_props",
            props_dir_abs,
            MATERIALS,
            payload,
        )
    )
    return header + constants + _RUNTIME


def write_script(scene: Scene, path: str, options: Defaults | None = None) -> None:
    import os

    props_dir = os.path.join(os.path.dirname(os.path.abspath(path)), "vsm_props")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(build_script(scene, options, props_dir_abs=props_dir))
