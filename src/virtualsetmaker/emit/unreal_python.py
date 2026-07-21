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
from .blockouts import (
    MESH_SPECS,
    WALL_OPENINGS,
    fixture_for,
    native_span_for,
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


def _scene_payload(scene: Scene, options: Defaults | None = None) -> dict:
    """Pre-convert every object into Unreal-space numbers for embedding."""
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
        # Real-mesh upgrade: same footprint and height the blockout claims,
        # so a missing Starter Content pack (the runtime falls back to the
        # parts above) changes looks, never layout. Wall inserts are excluded
        # -- their carve pipeline stays pure blockout.
        spec = MESH_SPECS.get(matched or "") if options.use_starter_meshes else None
        if spec is not None and opening is None:
            bx, by = recipe_span(parts)
            tx, ty, tz = bx * sx, by * sy, recipe_height(parts)
            if abs(spec["yaw"]) % 180.0 == 90.0:
                tx, ty = ty, tx  # target extents are in MESH-local axes
            entry["mesh"] = {
                "asset": spec["asset"],
                "loc": [x, y, 0.0],
                "yaw": yaw + spec["yaw"],
                "size": [tx, ty, tz],
            }
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

        lights.append(
            {
                "kind": lt.kind,
                "label": lt.kind or lt.id,
                "cls": cls,
                "parts": _bake_parts(fixture["parts"], (x, y), yaw, (1.0, 1.0)),
                "light_loc": light_loc,
                "light_rot": light_rot,
            }
        )

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


# Attempted at most once per run: a project with no Starter Content would
# otherwise re-walk the engine install for every meshed prop.
_STARTER_INSTALL_TRIED = [False]


def _install_starter_props():
    """Best-effort: copy the Starter Content prop meshes (plus the materials
    and textures they reference) from the engine install into this project.
    UE 5.6 and earlier ship the pack on disk under <root>/Samples/; 5.7+
    prebuilt installs carry NOTHING, so failing here is normal -- the caller
    falls back to blockout parts and we log how to add the pack by hand."""
    import os
    import shutil

    if _STARTER_INSTALL_TRIED[0]:
        return False
    _STARTER_INSTALL_TRIED[0] = True
    try:
        root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.root_dir())
        src = None
        for rel in (
            ("Samples", "StarterContent", "Content", "StarterContent"),
            ("Samples", "StarterContent", "Content"),
        ):
            cand = os.path.join(root, *rel)
            if os.path.isfile(os.path.join(cand, "Props", "SM_Chair.uasset")):
                src = cand
                break
        if src is None:
            unreal.log_warning(
                "VSM: this engine install ships no Starter Content on disk "
                "(normal on UE 5.7+), so props spawn as blockout primitives. "
                "For real prop meshes: Content Drawer -> +Add -> "
                "'Add Feature or Content Pack...' -> Starter Content -> "
                "Add to Project, then re-run this script."
            )
            return False
        dest = os.path.join(
            unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()),
            "StarterContent",  # load-bearing: uassets reference /Game/StarterContent/...
        )
        copied = 0
        # Props includes Props/Materials; the root Materials + Textures trees
        # are what those materials sample -- without them meshes render as
        # checkerboard. Whole folders on purpose: cherry-picking texture
        # files is fragile against material-graph references.
        for sub in ("Props", "Materials", "Textures"):
            top = os.path.join(src, sub)
            if not os.path.isdir(top):
                continue
            for dirpath, _dirnames, filenames in os.walk(top):
                out = os.path.join(dest, sub, os.path.relpath(dirpath, top))
                os.makedirs(out, exist_ok=True)
                for fn in filenames:
                    target = os.path.join(out, fn)
                    if not os.path.exists(target):
                        shutil.copy2(os.path.join(dirpath, fn), target)
                        copied += 1
        unreal.log(
            "VSM: installed Starter Content props into /Game/StarterContent "
            "(%d files copied from %s)" % (copied, src)
        )
        registry = unreal.AssetRegistryHelpers.get_asset_registry()
        registry.scan_paths_synchronous(["/Game/StarterContent"], force_rescan=True)
        return True
    except Exception as exc:
        unreal.log_warning("VSM: Starter Content install failed: %s" % exc)
        return False


def _spawn_prop_mesh(m, what):
    """Spawn a real prop mesh scaled so its bounds match the blockout target.

    Scale comes from the loaded mesh's own bounding box (never hardcoded
    sizes, so re-exported engine assets keep working), with the bbox XY
    center moved onto the prop origin and the bbox bottom onto the floor.
    Returns the actor, or None so the caller falls back to blockout parts."""
    import math as _math

    mesh = unreal.EditorAssetLibrary.load_asset(m["asset"])
    if mesh is None and _install_starter_props():
        mesh = unreal.EditorAssetLibrary.load_asset(m["asset"])
    if mesh is None:
        return None
    try:
        box = mesh.get_bounding_box()
        ext = (box.max.x - box.min.x, box.max.y - box.min.y, box.max.z - box.min.z)
        if min(ext) < 0.1:
            return None
        sx, sy, sz = (m["size"][i] / ext[i] for i in range(3))
        cx = (box.max.x + box.min.x) / 2.0 * sx
        cy = (box.max.y + box.min.y) / 2.0 * sy
        bz = box.min.z * sz
        rad = _math.radians(m["yaw"])
        wx = m["loc"][0] - (cx * _math.cos(rad) - cy * _math.sin(rad))
        wy = m["loc"][1] - (cx * _math.sin(rad) + cy * _math.cos(rad))
        actor = _spawn_object(mesh, [wx, wy, m["loc"][2] - bz], [0.0, m["yaw"], 0.0], what)
        if actor is not None:
            actor.set_actor_scale3d(unreal.Vector(sx, sy, sz))
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
            # rig/fixture placeholder geometry, grouped under its first part
            rig = None
            for i, part in enumerate(lt["parts"]):
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

        track = binding.add_track(unreal.MovieScene3DTransformTrack)
        section = track.add_section()
        section.set_start_frame_seconds(cam["keys"][0]["t"])
        section.set_end_frame_seconds(max(cam["keys"][-1]["t"], float(SCENE["duration"])))
        chans = section.get_all_channels()  # locX,locY,locZ, rotX(roll),rotY(pitch),rotZ(yaw), sclX,Y,Z
        for kf in cam["keys"]:
            f = _secs_to_frame(tick, kf["t"])
            loc, rot = kf["loc"], kf["rot"]  # rot = [pitch, yaw, roll]
            chans[0].add_key(f, loc[0])
            chans[1].add_key(f, loc[1])
            chans[2].add_key(f, loc[2])
            chans[3].add_key(f, rot[2])  # roll
            chans[4].add_key(f, rot[0])  # pitch
            chans[5].add_key(f, rot[1])  # yaw

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
                fchan.add_key(_secs_to_frame(tick, kf["t"]), float(kf["focal"]))

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
            # UE 5.8: MovieSceneBindingProxy no longer exposes get_binding_id();
            # build the binding ID via the sequence helper instead.
            binding_id = unreal.MovieSceneSequenceExtensions.make_binding_id(
                seq, bindings[shot["cam"]]
            )
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


def build_script(scene: Scene, options: Defaults | None = None) -> str:
    """Return the full Unreal Python script for ``scene`` as a string."""
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
        "UE_CONTENT_PATH = %r\n\n"
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
            payload,
        )
    )
    return header + constants + _RUNTIME


def write_script(scene: Scene, path: str, options: Defaults | None = None) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(build_script(scene, options))
