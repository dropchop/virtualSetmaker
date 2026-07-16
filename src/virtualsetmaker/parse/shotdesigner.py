"""Parse a Shot Designer ``.hcw`` scene into the neutral :class:`~virtualsetmaker.ir.Scene`.

The ``.hcw`` format is plain XML (verified against a real sample). Layout::

    <ShotDesignerDocument>
      <DocumentPreamble> ... </DocumentPreamble>
      <CurrentSnapshot>
        <Canvas>
          <Camera> <x/> <y/> <SubObjects><RotatorCamera><angle/> ...
          <Character> <x/> <y/> <colorName/> <female/> <SubObjects><RotatorCharacter><angle/>
          <GenericProp> <x/> <y/> <objectKey/> <objectScaleX/> <SubObjects><RotatorObject><angle/>
          <GenericSet> ... (parsed as a Prop)
          <Wall> <Points><Point><x/><y/></Point> ...
          <GenericLight> <x/> <y/> <objectKey/> <SubObjects><Rotator.../><angle/>
        </Canvas>
        <TimeSlices> ... </TimeSlices>
      </CurrentSnapshot>
      <DocumentPostScript><numObjects/><numSnapshot/></DocumentPostScript>

Conventions confirmed from the sample:
* positions are Shot Designer units with **+y downward** (screen space);
* rotator ``angle`` is in **radians**;
* at 1 unit = 1 cm, units->meters is a divide by ``units_per_meter``.
"""

from __future__ import annotations

import math
import os
import xml.etree.ElementTree as ET
from typing import Optional

from ..ir import Actor, Camera, CameraKeyframe, Light, Prop, Scene, Shot, Vec3, Wall
from .probe import probe

# Default lens by Shot Designer <cameraStyle>; refined once we see more styles.
_DEFAULT_FOCAL_MM = 35.0
# Shot Designer is a 2D top-down tool: it carries no camera height, so default
# cameras to eye level (meters). Overridden if a future format exposes height.
_DEFAULT_CAMERA_HEIGHT_M = 1.5


def _ftext(el: Optional[ET.Element], tag: str, default: float = 0.0) -> float:
    if el is None:
        return default
    raw = el.findtext(tag)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _rotator_angle_rad(obj: ET.Element) -> float:
    """Return the object's facing angle (radians) from its Rotator sub-object.

    Different object types nest differently named rotators (RotatorCamera,
    RotatorCharacter, RotatorObject, RotatorNoMenu). We take the first child of
    <SubObjects> whose tag starts with "Rotator".
    """
    sub = obj.find("SubObjects")
    if sub is None:
        return 0.0
    for child in sub:
        if child.tag.startswith("Rotator"):
            return _ftext(child, "angle", 0.0)
    return 0.0


def _yaw_deg(obj: ET.Element) -> float:
    return math.degrees(_rotator_angle_rad(obj))


def _uid(obj: ET.Element, fallback: str) -> str:
    return obj.findtext("uniqueID") or fallback


def parse_file(path: str, units_per_meter: float = 100.0) -> Scene:
    """Parse a ``.hcw`` file at ``path`` into a :class:`Scene`."""
    probe(path)  # raises NotShotDesignerFile on anything unexpected
    root = ET.parse(path).getroot()
    scene = _parse_root(root, units_per_meter)
    scene.name = os.path.splitext(os.path.basename(path))[0]
    return scene


def parse_string(text: str, units_per_meter: float = 100.0) -> Scene:
    return _parse_root(ET.fromstring(text), units_per_meter)


def _parse_root(root: ET.Element, units_per_meter: float) -> Scene:
    scene = Scene(units_per_meter=units_per_meter)
    upm = units_per_meter

    def loc(obj: ET.Element, z: float = 0.0) -> Vec3:
        return Vec3(_ftext(obj, "x") / upm, _ftext(obj, "y") / upm, z)

    canvas = root.find("CurrentSnapshot/Canvas")
    if canvas is None:
        return scene

    for i, obj in enumerate(canvas):
        tag = obj.tag
        if tag == "Camera":
            scene.cameras.append(_parse_camera(obj, loc, i))
        elif tag == "Character":
            scene.actors.append(_parse_character(obj, loc, i))
        elif tag in ("GenericProp", "GenericSet"):
            scene.props.append(_parse_prop(obj, loc, i))
        elif tag == "Wall":
            scene.walls.append(_parse_wall(obj, upm, i))
        elif tag == "GenericLight":
            scene.lights.append(_parse_light(obj, loc, i))
        # unknown tags are ignored on purpose

    # This sample is a single static snapshot (numSnapshot == 0). Give every
    # camera one keyframe at t=0 and a shot covering the scene so the emitted
    # Level Sequence is immediately usable. Multi-snapshot camera moves are a
    # later addition (see the plan) once we have an animated sample.
    _add_default_shots(scene)
    return scene


def _parse_camera(obj: ET.Element, loc, idx: int) -> Camera:
    uid = _uid(obj, f"camera_{idx}")
    key = CameraKeyframe(
        time_s=0.0,
        location=loc(obj, z=_DEFAULT_CAMERA_HEIGHT_M),
        yaw_deg=_yaw_deg(obj),
        focal_length_mm=_DEFAULT_FOCAL_MM,
    )
    return Camera(id=uid, name=f"Camera_{idx + 1}", keyframes=[key])


def _parse_character(obj: ET.Element, loc, idx: int) -> Actor:
    uid = _uid(obj, f"character_{idx}")
    female = (obj.findtext("female") or "false").lower() == "true"
    color = obj.findtext("colorName") or ""
    name = uid if not uid.replace("-", "").isalnum() or "character" in uid.lower() else uid
    return Actor(
        id=uid,
        name=name,
        location=loc(obj),
        yaw_deg=_yaw_deg(obj),
        height_m=1.65 if female else 1.8,
        color=color,
    )


def _parse_prop(obj: ET.Element, loc, idx: int) -> Prop:
    uid = _uid(obj, f"prop_{idx}")
    kind = obj.findtext("objectKey") or ""
    sx = _ftext(obj, "objectScaleX", 1.0)
    sy = _ftext(obj, "objectScaleY", 1.0)
    return Prop(
        id=uid,
        name=kind or f"Prop_{idx + 1}",
        kind=kind,
        location=loc(obj),
        yaw_deg=_yaw_deg(obj),
        scale=Vec3(sx, sy, 1.0),
    )


def _parse_wall(obj: ET.Element, upm: float, idx: int) -> Wall:
    uid = _uid(obj, f"wall_{idx}")
    points: list[Vec3] = []
    pts = obj.find("Points")
    if pts is not None:
        for p in pts.findall("Point"):
            points.append(Vec3(_ftext(p, "x") / upm, _ftext(p, "y") / upm, 0.0))
    closed = (obj.findtext("closedLoop") or "false").lower() == "true"
    return Wall(id=uid, points=points, closed_loop=closed)


def _parse_light(obj: ET.Element, loc, idx: int) -> Light:
    uid = _uid(obj, f"light_{idx}")
    kind = obj.findtext("objectKey") or ""
    return Light(id=uid, kind=kind, location=loc(obj), yaw_deg=_yaw_deg(obj))


def _add_default_shots(scene: Scene) -> None:
    if scene.shots or not scene.cameras:
        return
    per = scene.duration_s / len(scene.cameras) if scene.cameras else scene.duration_s
    for i, cam in enumerate(scene.cameras):
        scene.shots.append(
            Shot(
                id=f"shot_{i + 1}",
                name=f"Shot {i + 1}",
                camera_id=cam.id,
                start_s=round(i * per, 4),
                end_s=round((i + 1) * per, 4),
            )
        )
