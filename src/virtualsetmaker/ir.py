"""Intermediate representation (IR) for a virtual scene.

This is the neutral hand-off between the Shot Designer parser and the Unreal
emitter. Neither end depends on the other: the parser fills an IR ``Scene``, the
emitter consumes one. The IR is plain, JSON-serializable dataclasses.

Conventions
-----------
* Units are **meters**. (Shot Designer positions, at 1 unit = 1 cm, are divided
  by 100 on the way in.)
* Positions are stored in Shot Designer's screen-space orientation (X right,
  Y down). The single screen->Unreal axis/handedness flip lives in
  :mod:`virtualsetmaker.coords`, so it happens exactly once.
* Angles are **degrees** (Shot Designer stores radians; the parser converts).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class Vec3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Vec3":
        return Vec3(float(d.get("x", 0.0)), float(d.get("y", 0.0)), float(d.get("z", 0.0)))


@dataclass
class Actor:
    """A blocking mark for a character (``<Character>``)."""

    id: str
    name: str
    location: Vec3
    yaw_deg: float = 0.0
    height_m: float = 1.8
    color: str = ""
    female: bool = False  # Shot Designer <female> flag (Type B characters)
    color_rgb: Optional[list[int]] = None  # [r, g, b] 0-255 from the numeric <color>

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Actor":
        rgb = d.get("color_rgb")
        return Actor(
            id=d["id"],
            name=d.get("name", d["id"]),
            location=Vec3.from_dict(d["location"]),
            yaw_deg=float(d.get("yaw_deg", 0.0)),
            height_m=float(d.get("height_m", 1.8)),
            color=d.get("color", ""),
            female=bool(d.get("female", False)),
            color_rgb=None if rgb is None else [int(c) for c in rgb],
        )


@dataclass
class Prop:
    """A set piece / furniture item (``<GenericProp>`` or ``<GenericSet>``).

    ``is_set`` marks ``<GenericSet>`` elements (doors, windows, prison bars,
    stairs...). Their icon art is authored width-along-X, so their ``yaw_deg``
    is the direct screen rotation; ``<GenericProp>`` furniture icons face +Y
    and use the freestanding angle+90 convention in the emitter.

    ``wall_snapped`` records a non-empty ``<snapPath>`` (Shot Designer glued
    the piece to a wall). It is informational only: real files carry stale
    snap fields after a piece is detached and moved, so the emitter aligns
    wall inserts to walls geometrically instead of trusting it.
    """

    id: str
    name: str
    kind: str  # from Shot Designer <objectKey>, e.g. SOFA, DOOROPEN
    location: Vec3
    yaw_deg: float = 0.0
    scale: Vec3 = field(default_factory=lambda: Vec3(1.0, 1.0, 1.0))
    color: str = ""
    wall_snapped: bool = False
    is_set: bool = False

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Prop":
        return Prop(
            id=d["id"],
            name=d.get("name", d["id"]),
            kind=d.get("kind", ""),
            location=Vec3.from_dict(d["location"]),
            yaw_deg=float(d.get("yaw_deg", 0.0)),
            scale=Vec3.from_dict(d.get("scale", {"x": 1, "y": 1, "z": 1})),
            color=d.get("color", ""),
            wall_snapped=bool(d.get("wall_snapped", False)),
            is_set=bool(d.get("is_set", False)),
        )


@dataclass
class Wall:
    """A wall / room outline polyline (``<Wall>``)."""

    id: str
    points: list[Vec3] = field(default_factory=list)
    closed_loop: bool = False

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Wall":
        return Wall(
            id=d["id"],
            points=[Vec3.from_dict(p) for p in d.get("points", [])],
            closed_loop=bool(d.get("closed_loop", False)),
        )


@dataclass
class Light:
    """A lighting instrument (``<GenericLight>``)."""

    id: str
    kind: str  # from <objectKey>, e.g. FRESNELLARGE, SILK
    location: Vec3
    yaw_deg: float = 0.0

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Light":
        return Light(
            id=d["id"],
            kind=d.get("kind", ""),
            location=Vec3.from_dict(d["location"]),
            yaw_deg=float(d.get("yaw_deg", 0.0)),
        )


@dataclass
class CameraKeyframe:
    """One sampled camera state. A camera with >1 keyframe is an animated move."""

    time_s: float
    location: Vec3
    yaw_deg: float = 0.0
    pitch_deg: float = 0.0
    roll_deg: float = 0.0
    focal_length_mm: float = 35.0
    focus_distance_m: Optional[float] = None

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "CameraKeyframe":
        fd = d.get("focus_distance_m")
        return CameraKeyframe(
            time_s=float(d.get("time_s", 0.0)),
            location=Vec3.from_dict(d["location"]),
            yaw_deg=float(d.get("yaw_deg", 0.0)),
            pitch_deg=float(d.get("pitch_deg", 0.0)),
            roll_deg=float(d.get("roll_deg", 0.0)),
            focal_length_mm=float(d.get("focal_length_mm", 35.0)),
            focus_distance_m=None if fd is None else float(fd),
        )


@dataclass
class Camera:
    id: str
    name: str
    keyframes: list[CameraKeyframe] = field(default_factory=list)
    sensor_width_mm: float = 36.0
    sensor_height_mm: float = 24.0

    @property
    def is_animated(self) -> bool:
        return len(self.keyframes) > 1

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Camera":
        return Camera(
            id=d["id"],
            name=d.get("name", d["id"]),
            keyframes=[CameraKeyframe.from_dict(k) for k in d.get("keyframes", [])],
            sensor_width_mm=float(d.get("sensor_width_mm", 36.0)),
            sensor_height_mm=float(d.get("sensor_height_mm", 24.0)),
        )


@dataclass
class Shot:
    """An entry in the camera-cut track: which camera is live over [start, end]."""

    id: str
    name: str
    camera_id: str
    start_s: float = 0.0
    end_s: float = 0.0

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Shot":
        return Shot(
            id=d["id"],
            name=d.get("name", d["id"]),
            camera_id=d["camera_id"],
            start_s=float(d.get("start_s", 0.0)),
            end_s=float(d.get("end_s", 0.0)),
        )


@dataclass
class Scene:
    name: str = "Untitled"
    frame_rate: float = 24.0
    duration_s: float = 5.0
    units_per_meter: float = 100.0  # Shot Designer default: 1 unit == 1 cm
    actors: list[Actor] = field(default_factory=list)
    props: list[Prop] = field(default_factory=list)
    walls: list[Wall] = field(default_factory=list)
    lights: list[Light] = field(default_factory=list)
    cameras: list[Camera] = field(default_factory=list)
    shots: list[Shot] = field(default_factory=list)
    # Parse diagnostics: canvas object tags the parser did not recognize (one
    # entry per skipped object), and how many snapshots beyond the current one
    # the source document carries (only the current snapshot is converted).
    skipped_objects: list[str] = field(default_factory=list)
    extra_snapshots: int = 0
    # Free-form parse warnings (e.g. an untested file version) surfaced verbatim
    # in the build report.
    notes: list[str] = field(default_factory=list)

    # -- serialization -----------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Scene":
        return Scene(
            name=d.get("name", "Untitled"),
            frame_rate=float(d.get("frame_rate", 24.0)),
            duration_s=float(d.get("duration_s", 5.0)),
            units_per_meter=float(d.get("units_per_meter", 100.0)),
            actors=[Actor.from_dict(x) for x in d.get("actors", [])],
            props=[Prop.from_dict(x) for x in d.get("props", [])],
            walls=[Wall.from_dict(x) for x in d.get("walls", [])],
            lights=[Light.from_dict(x) for x in d.get("lights", [])],
            cameras=[Camera.from_dict(x) for x in d.get("cameras", [])],
            shots=[Shot.from_dict(x) for x in d.get("shots", [])],
            skipped_objects=[str(x) for x in d.get("skipped_objects", [])],
            extra_snapshots=int(d.get("extra_snapshots", 0)),
            notes=[str(x) for x in d.get("notes", [])],
        )

    @staticmethod
    def from_json(text: str) -> "Scene":
        return Scene.from_dict(json.loads(text))

    # -- validation --------------------------------------------------------
    def validate(self) -> list[str]:
        """Return a list of human-readable problems (empty == valid)."""
        errors: list[str] = []

        ids: list[str] = []
        for group in (self.actors, self.props, self.walls, self.lights, self.cameras):
            ids.extend(obj.id for obj in group)
        seen: set[str] = set()
        for oid in ids:
            if oid in seen:
                errors.append(f"duplicate object id: {oid!r}")
            seen.add(oid)

        camera_ids = {c.id for c in self.cameras}
        for shot in self.shots:
            if shot.camera_id not in camera_ids:
                errors.append(f"shot {shot.id!r} references unknown camera {shot.camera_id!r}")
            if shot.end_s < shot.start_s:
                errors.append(f"shot {shot.id!r} ends before it starts")

        for cam in self.cameras:
            times = [k.time_s for k in cam.keyframes]
            if times != sorted(times):
                errors.append(f"camera {cam.id!r} keyframes are not time-ordered")
            for t in times:
                if t < 0 or t > self.duration_s + 1e-6:
                    errors.append(f"camera {cam.id!r} keyframe time {t} outside [0, {self.duration_s}]")

        return errors
