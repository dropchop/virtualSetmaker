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
# Shot Designer stores no clock, just a 1..5 speed index per time slice.
# Dolly speed used to time camera moves: meters/second = index * this factor
# (speed 3 -> 0.75 m/s, a comfortable dolly pace).
_DOLLY_MPS_PER_SPEED = 0.25
_MIN_MOVE_DURATION_S = 1.0


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

    raw_cameras: list[dict] = []
    tracks: list[dict] = []
    for i, obj in enumerate(canvas):
        tag = obj.tag
        if tag == "Camera":
            raw_cameras.append(_parse_raw_camera(obj, loc, i))
        elif tag == "Track":
            tracks.append(_parse_track(obj, upm))
        elif tag == "Character":
            scene.actors.append(_parse_character(obj, loc, i))
        elif tag in ("GenericProp", "GenericSet"):
            scene.props.append(_parse_prop(obj, loc, i))
        elif tag == "Wall":
            scene.walls.append(_parse_wall(obj, upm, i))
        elif tag == "GenericLight":
            scene.lights.append(_parse_light(obj, loc, i))
        else:
            # Unknown object types are skipped, but never silently: they are
            # recorded so the build report can tell the user what was dropped
            # (e.g. palette items stored under tags we have not seen yet).
            scene.skipped_objects.append(tag)

    scene.extra_snapshots = int(_ftext(root.find("DocumentPostScript"), "numSnapshot", 0.0))

    camera_speed = _ftext(root.find("CurrentSnapshot/TimeSlices/TimeNumber"), "cameraSpeed", 3.0)
    scene.cameras = _assemble_cameras(raw_cameras, tracks, camera_speed)

    move_end = max(
        (kf.time_s for cam in scene.cameras for kf in cam.keyframes), default=0.0
    )
    scene.duration_s = max(scene.duration_s, move_end)

    _add_default_shots(scene)
    return scene


def _parse_raw_camera(obj: ET.Element, loc, idx: int) -> dict:
    return {
        "uid": _uid(obj, f"camera_{idx}"),
        "location": loc(obj, z=_DEFAULT_CAMERA_HEIGHT_M),
        "yaw_deg": _yaw_deg(obj),
        # stop-mark number: 1-based order of this position within a camera move
        "stop": int(_ftext(obj, "stopMarks", 0.0)),
    }


def _parse_track(obj: ET.Element, upm: float) -> dict:
    """A ``<Track>`` is a dolly path linking two stop marks by uniqueID."""
    points: list[Vec3] = []
    pts = obj.find("Points")
    if pts is not None:
        for p in pts.findall("Point"):
            points.append(
                Vec3(_ftext(p, "x") / upm, _ftext(p, "y") / upm, _DEFAULT_CAMERA_HEIGHT_M)
            )
    return {
        "from": obj.findtext("fromConstraints") or "",
        "to": obj.findtext("toConstraints") or "",
        "points": points,
        "hard_line": (obj.findtext("hardLine") or "false").lower() == "true",
    }


def _assemble_cameras(raw_cameras: list[dict], tracks: list[dict], camera_speed: float) -> list[Camera]:
    """Merge stop-mark cameras joined by camera tracks into moving cameras.

    A Shot Designer camera move is stored as N ``<Camera>`` elements (one per
    stop mark) plus ``<Track>`` elements whose from/to constraints name the
    stop uniqueIDs. Each connected chain becomes ONE IR camera whose keyframes
    are: the first stop, any intermediate track points (these carry the curve
    of a non-hardLine path), and the final stop. Rotation is keyed from the
    stop cameras themselves, so the look direction is maintained (and, when
    the stops disagree, interpolated by Unreal between the endpoint keys).

    Timing: Shot Designer stores no clock, only a speed index — keyframe times
    come from cumulative distance along the path at ``camera_speed *
    _DOLLY_MPS_PER_SPEED`` m/s.
    """
    by_uid = {c["uid"]: c for c in raw_cameras}

    # Only tracks that join two cameras are camera moves (actor walk paths use
    # the same element but reference Character ids).
    cam_tracks = [t for t in tracks if t["from"] in by_uid and t["to"] in by_uid]

    # Union stop cameras into chains.
    group: dict[str, str] = {c["uid"]: c["uid"] for c in raw_cameras}

    def find(uid: str) -> str:
        while group[uid] != uid:
            group[uid] = group[group[uid]]
            uid = group[uid]
        return uid

    for t in cam_tracks:
        group[find(t["from"])] = find(t["to"])

    chains: dict[str, list[dict]] = {}
    for c in raw_cameras:
        chains.setdefault(find(c["uid"]), []).append(c)

    speed_mps = max(camera_speed, 1.0) * _DOLLY_MPS_PER_SPEED
    cameras: list[Camera] = []
    for idx, members in enumerate(chains.values()):
        members.sort(key=lambda c: (c["stop"] or 0))
        name = f"Camera_{idx + 1}"
        if len(members) == 1:
            c = members[0]
            cameras.append(
                Camera(
                    id=c["uid"],
                    name=name,
                    keyframes=[
                        CameraKeyframe(
                            time_s=0.0,
                            location=c["location"],
                            yaw_deg=c["yaw_deg"],
                            focal_length_mm=_DEFAULT_FOCAL_MM,
                        )
                    ],
                )
            )
            continue

        track_by_pair = {}
        for t in cam_tracks:
            track_by_pair[(t["from"], t["to"])] = t

        # Walk consecutive stops, splicing in each track's intermediate points
        # (they carry the bow of a curved path; endpoints duplicate the stops).
        positions: list[Vec3] = [members[0]["location"]]
        yaws: list[float] = [members[0]["yaw_deg"]]
        for a, b in zip(members, members[1:]):
            t = track_by_pair.get((a["uid"], b["uid"]))
            reverse = False
            if t is None:
                t = track_by_pair.get((b["uid"], a["uid"]))
                reverse = t is not None
            mids: list[Vec3] = []
            if t is not None and len(t["points"]) > 2:
                mids = t["points"][1:-1]
                if reverse:
                    mids = list(reversed(mids))
            for m in mids:
                positions.append(m)
                yaws.append(None)  # interpolated below
            positions.append(b["location"])
            yaws.append(b["yaw_deg"])

        times = _times_by_arc_length(positions, speed_mps)
        _fill_interpolated_yaws(yaws, times)

        keyframes = [
            CameraKeyframe(
                time_s=t,
                location=p,
                yaw_deg=y,
                focal_length_mm=_DEFAULT_FOCAL_MM,
            )
            for p, y, t in zip(positions, yaws, times)
        ]
        cameras.append(Camera(id=members[0]["uid"], name=name, keyframes=keyframes))
    return cameras


def _times_by_arc_length(positions: list[Vec3], speed_mps: float) -> list[float]:
    dists = [0.0]
    for a, b in zip(positions, positions[1:]):
        dists.append(dists[-1] + math.hypot(b.x - a.x, b.y - a.y))
    total = dists[-1]
    duration = max(total / speed_mps if speed_mps > 0 else 0.0, _MIN_MOVE_DURATION_S)
    if total <= 0:
        return [round(i * duration / max(len(positions) - 1, 1), 4) for i in range(len(positions))]
    return [round(d / total * duration, 4) for d in dists]


def _fill_interpolated_yaws(yaws: list, times: list[float]) -> None:
    """Replace None entries (intermediate track points) with yaw interpolated
    between the surrounding stop marks, proportional to time, via the shortest
    angular difference — this is what keeps the camera looking the same way
    when both stops share a heading."""
    known = [i for i, y in enumerate(yaws) if y is not None]
    for lo, hi in zip(known, known[1:]):
        y0, y1 = yaws[lo], yaws[hi]
        delta = (y1 - y0 + 180.0) % 360.0 - 180.0
        span = times[hi] - times[lo]
        for i in range(lo + 1, hi):
            f = (times[i] - times[lo]) / span if span > 0 else 0.0
            yaws[i] = y0 + delta * f


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
        female=female,
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
        # A non-empty <snapPath> names the wall this set piece is glued to
        # (doors/windows). Its angle is then the wall's direction, not a user
        # rotation — the emitter treats the two cases differently.
        wall_snapped=bool((obj.findtext("snapPath") or "").strip()),
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
