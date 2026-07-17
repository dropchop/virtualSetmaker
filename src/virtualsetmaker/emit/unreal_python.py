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

from ..coords import ir_to_ue_location, ir_to_ue_rotation, ir_to_ue_yaw, M_TO_CM
from ..ir import Camera, Scene
from .blockouts import fixture_for, recipe_for

WALL_HEIGHT_CM = 250.0
WALL_THICKNESS_CM = 10.0
LIGHT_PITCH_DEG = -25.0
LIGHT_SUN_HEIGHT_CM = 800.0
LIGHT_SUN_PITCH_DEG = -50.0

# Shot Designer lighting palette -> Unreal light class, by substring (checked
# in order). Fresnels/ellipsoidals/PARs and anything unrecognized read best as
# spotlights; flat sources as rect lights; omnidirectional lanterns as points.
_LIGHT_CLASS_RULES = [
    ("SUN", "directional"),
    ("SILK", "rect"),
    ("SOFTBOX", "rect"),
    ("SOFT", "rect"),
    ("BOUNCE", "rect"),
    ("PANEL", "rect"),
    ("FLO", "rect"),
    ("LED", "rect"),
    ("FRAME", "rect"),
    ("CHINABALL", "point"),
    ("CHINA", "point"),
    ("BALLOON", "point"),
    ("PRACTICAL", "point"),
    ("LANTERN", "point"),
    ("BULB", "point"),
    ("STICK", "point"),  # "Light On A Stick" — handheld omni lamp
]


def _light_class(kind: str) -> str:
    key = (kind or "").upper()
    for needle, cls in _LIGHT_CLASS_RULES:
        if needle in key:
            return cls
    return "spot"

# Skeletal meshes tried in order for actors; falls back to a capsule if none load.
MANNEQUIN_CANDIDATES = [
    "/Game/Characters/Mannequins/Meshes/SKM_Manny.SKM_Manny",
    "/Game/Characters/Mannequins/Meshes/SKM_Quinn.SKM_Quinn",
    "/Game/Characters/Mannequin_UE4/Meshes/SK_Mannequin.SK_Mannequin",
]
CUBE_MESH = "/Engine/BasicShapes/Cube.Cube"
CYLINDER_MESH = "/Engine/BasicShapes/Cylinder.Cylinder"
SPHERE_MESH = "/Engine/BasicShapes/Sphere.Sphere"


def _scene_payload(scene: Scene) -> dict:
    """Pre-convert every object into Unreal-space numbers for embedding."""
    m2cm = scene.units_per_meter  # IR meters -> UE cm (1 SD unit = 1 cm => 100)

    actors = []
    for a in scene.actors:
        x, y, z = ir_to_ue_location(a.location, m2cm)
        actors.append(
            {
                "loc": [x, y, 0.0],
                "yaw": ir_to_ue_yaw(a.yaw_deg),
                "label": a.name or a.id,
                "height_cm": a.height_m * 100.0,
                "color": a.color,
            }
        )

    props = []
    for p in scene.props:
        x, y, _z = ir_to_ue_location(p.location, m2cm)
        yaw = ir_to_ue_yaw(p.yaw_deg)
        matched, parts = recipe_for(p.kind)
        props.append(
            {
                "label": p.name,
                "kind": p.kind,
                "matched": matched,
                "parts": _bake_parts(parts, (x, y), yaw, (p.scale.x, p.scale.y)),
            }
        )

    wall_segments = []
    for w in scene.walls:
        pts = [ir_to_ue_location(pt, m2cm) for pt in w.points]
        pairs = list(zip(pts, pts[1:]))
        if w.closed_loop and len(pts) > 2:
            pairs.append((pts[-1], pts[0]))
        for (ax, ay, _az), (bx, by, _bz) in pairs:
            length = math.hypot(bx - ax, by - ay)
            if length < 1e-3:
                continue
            wall_segments.append(
                {
                    "loc": [(ax + bx) / 2.0, (ay + by) / 2.0, WALL_HEIGHT_CM / 2.0],
                    "yaw": math.degrees(math.atan2(by - ay, bx - ax)),
                    "length": length,
                    "label": f"Wall_{w.id[:8]}",
                }
            )

    lights = []
    for lt in scene.lights:
        x, y, _z = ir_to_ue_location(lt.location, m2cm)
        yaw = ir_to_ue_yaw(lt.yaw_deg)
        cls = _light_class(lt.kind)
        fixture = fixture_for(lt.kind)

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
        "fps": scene.frame_rate,
        "duration": scene.duration_s,
        "actors": actors,
        "props": props,
        "wall_segments": wall_segments,
        "lights": lights,
        "cameras": cameras,
        "shots": shots,
    }


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


def _load_first(paths):
    for p in paths:
        asset = unreal.EditorAssetLibrary.load_asset(p)
        if asset:
            return asset
    return None


_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def _spawn_object(mesh, loc, rot):
    return _actor_sub.spawn_actor_from_object(mesh, _v(loc), _r(rot))


def _spawn_class(cls, loc, rot):
    return _actor_sub.spawn_actor_from_class(cls, _v(loc), _r(rot))


def _secs_to_frame(seq, t):
    tick = seq.get_tick_resolution()
    return unreal.FrameNumber(int(round(t * tick.numerator / tick.denominator)))


def build_scene():
    meshes = {
        "cube": unreal.EditorAssetLibrary.load_asset(CUBE_MESH),
        "cylinder": unreal.EditorAssetLibrary.load_asset(CYLINDER_MESH),
        "sphere": unreal.EditorAssetLibrary.load_asset(SPHERE_MESH),
    }
    cube = meshes["cube"]
    cylinder = meshes["cylinder"]
    mannequin = _load_first(MANNEQUIN_CANDIDATES)

    # --- actors ---------------------------------------------------------
    for a in SCENE["actors"]:
        if mannequin is not None:
            actor = _spawn_object(mannequin, a["loc"], [0.0, a["yaw"], 0.0])
        elif cylinder is not None:
            h = a["height_cm"]
            loc = [a["loc"][0], a["loc"][1], h / 2.0]
            actor = _spawn_object(cylinder, loc, [0.0, a["yaw"], 0.0])
            actor.set_actor_scale3d(unreal.Vector(0.4, 0.4, h / 100.0))
        else:
            continue
        actor.set_actor_label("Actor_" + a["label"])
        actor.set_folder_path("VSM/Actors")

    # --- props (multi-part blockouts) ------------------------------------
    keep_world = unreal.AttachmentRule.KEEP_WORLD
    for p in SCENE["props"]:
        parent = None
        for i, part in enumerate(p["parts"]):
            mesh = meshes.get(part["shape"]) or cube
            if mesh is None:
                continue
            actor = _spawn_object(mesh, part["loc"], part["rot"])
            actor.set_actor_scale3d(_v(part["scale"]))
            if parent is None:
                parent = actor
                actor.set_actor_label("Prop_" + p["label"])
            else:
                actor.set_actor_label("Prop_%s_part%d" % (p["label"], i))
                actor.attach_to_actor(parent, "", keep_world, keep_world, keep_world, False)
            actor.set_folder_path("VSM/Props")

    # --- walls (blockout) -------------------------------------------
    if cube is not None:
        for w in SCENE["wall_segments"]:
            actor = _spawn_object(cube, w["loc"], [0.0, w["yaw"], 0.0])
            actor.set_actor_scale3d(
                unreal.Vector(w["length"] / 100.0, WALL_THICKNESS_CM / 100.0, WALL_HEIGHT_CM / 100.0)
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
            actor = _spawn_object(mesh, part["loc"], part["rot"])
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
                light_classes.get(lt["cls"], unreal.SpotLight), lt["light_loc"], lt["light_rot"]
            )
            light.set_actor_label("Light_" + lt["label"])
            light.set_folder_path("VSM/Lights")
            if rig is not None:
                light.attach_to_actor(rig, "", keep_world, keep_world, keep_world, False)

    # --- level sequence + cameras --------------------------------------
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    seq = tools.create_asset(
        "SEQ_" + SCENE["name"], "/Game/VSM", unreal.LevelSequence, unreal.LevelSequenceFactoryNew()
    )
    seq.set_display_rate(unreal.FrameRate(int(SCENE["fps"]), 1))
    seq.set_playback_end_seconds(float(SCENE["duration"]))

    # UE 5.6+ moved spawnable creation to the Level Sequence Editor Subsystem,
    # which only operates on the sequence currently open in Sequencer.
    ls_sub = unreal.get_editor_subsystem(unreal.LevelSequenceEditorSubsystem)
    unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)

    bindings = []
    for cam in SCENE["cameras"]:
        k0 = cam["keys"][0]
        actor = _spawn_class(unreal.CineCameraActor, k0["loc"], k0["rot"])
        actor.set_actor_label(cam["label"])
        comp = actor.get_cine_camera_component()
        # Set focal length BEFORE binding: spawnables snapshot a template here.
        comp.set_editor_property("current_focal_length", float(cam["focal0"]))
        binding = ls_sub.add_spawnable_from_instance(seq, actor)
        bindings.append(binding)

        track = binding.add_track(unreal.MovieScene3DTransformTrack)
        section = track.add_section()
        section.set_start_frame_seconds(cam["keys"][0]["t"])
        section.set_end_frame_seconds(max(cam["keys"][-1]["t"], float(SCENE["duration"])))
        chans = section.get_all_channels()  # locX,locY,locZ, rotX(roll),rotY(pitch),rotZ(yaw), sclX,Y,Z
        for kf in cam["keys"]:
            f = _secs_to_frame(seq, kf["t"])
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
                fchan.add_key(_secs_to_frame(seq, kf["t"]), float(kf["focal"]))

    # --- camera cut track ----------------------------------------------
    if bindings:
        cut = seq.add_track(unreal.MovieSceneCameraCutTrack)
        for shot in SCENE["shots"]:
            cs = cut.add_section()
            cs.set_start_frame_seconds(shot["start"])
            cs.set_end_frame_seconds(shot["end"])
            cs.set_camera_binding_id(bindings[shot["cam"]].get_binding_id())

    unreal.EditorAssetLibrary.save_loaded_asset(seq)
    unreal.log(
        "virtualSetmaker: built '%s' -- %d actors, %d props, %d wall segments, %d lights, %d cameras"
        % (
            SCENE["name"],
            len(SCENE["actors"]),
            len(SCENE["props"]),
            len(SCENE["wall_segments"]),
            len(SCENE["lights"]),
            len(SCENE["cameras"]),
        )
    )
    return seq


build_scene()
'''


def build_script(scene: Scene) -> str:
    """Return the full Unreal Python script for ``scene`` as a string."""
    payload = json.dumps(_scene_payload(scene), indent=2)
    header = (
        "# Auto-generated by virtualSetmaker. Run INSIDE the Unreal 5.8 editor (works on 5.6+):\n"
        "#   Output Log -> switch 'Cmd' to 'Python', then:  py \"%s.py\"\n"
        "# Requires the 'Python Editor Script Plugin'.\n"
        "import json\n"
        "try:\n"
        "    import unreal\n"
        "except ModuleNotFoundError:  # not inside the Unreal editor\n"
        "    unreal = None\n\n" % scene.name
    )
    constants = (
        "MANNEQUIN_CANDIDATES = %r\n"
        "CUBE_MESH = %r\n"
        "CYLINDER_MESH = %r\n"
        "SPHERE_MESH = %r\n"
        "WALL_THICKNESS_CM = %r\n"
        "WALL_HEIGHT_CM = %r\n\n"
        # JSON is not Python source (false/true/null), so it must be parsed,
        # not pasted in as a literal.
        'SCENE = json.loads(r"""\n%s\n""")\n'
        % (
            MANNEQUIN_CANDIDATES,
            CUBE_MESH,
            CYLINDER_MESH,
            SPHERE_MESH,
            WALL_THICKNESS_CM,
            WALL_HEIGHT_CM,
            payload,
        )
    )
    return header + constants + _RUNTIME


def write_script(scene: Scene, path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(build_script(scene))
