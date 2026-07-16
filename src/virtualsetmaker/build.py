"""The shared build core used by both the CLI and the GUI.

One function does the whole job — parse a Shot Designer ``.hcw``, validate,
emit the Unreal script — and returns a :class:`BuildReport` the caller renders
however it likes (stderr notes for the CLI, log pane for the GUI).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .emit import write_script
from .emit.blockouts import match_kind
from .ir import Scene
from .parse import parse_file


@dataclass
class BuildReport:
    input_path: str
    output_path: str
    actors: int = 0
    props: int = 0
    walls: int = 0
    lights: int = 0
    cameras: int = 0
    shots: int = 0
    warnings: list[str] = field(default_factory=list)
    unmatched_kinds: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"{self.actors} actors, {self.props} props, {self.walls} walls, "
            f"{self.lights} lights, {self.cameras} cameras, {self.shots} shots"
        )


def default_output_name(input_path: str) -> str:
    """`Scene.hcw` -> `Scene_unreal.py`."""
    base = os.path.splitext(os.path.basename(input_path))[0]
    return f"{base}_unreal.py"


def report_for(scene: Scene, input_path: str, output_path: str) -> BuildReport:
    return BuildReport(
        input_path=input_path,
        output_path=output_path,
        actors=len(scene.actors),
        props=len(scene.props),
        walls=len(scene.walls),
        lights=len(scene.lights),
        cameras=len(scene.cameras),
        shots=len(scene.shots),
        warnings=scene.validate(),
        unmatched_kinds=sorted(
            {p.kind for p in scene.props if p.kind and match_kind(p.kind) is None}
        ),
    )


def build_hcw(input_path: str, output_path: str, units_per_meter: float = 100.0) -> BuildReport:
    """Parse ``input_path`` and write the Unreal script to ``output_path``.

    Raises on unreadable/invalid input (NotShotDesignerFile, OSError); callers
    present the error. A returned report means the script was written.
    """
    scene = parse_file(input_path, units_per_meter=units_per_meter)
    report = report_for(scene, input_path, output_path)
    write_script(scene, output_path)
    return report


def build_scene_to(scene: Scene, input_path: str, output_path: str) -> BuildReport:
    """Same as :func:`build_hcw` but for an already-parsed/loaded Scene (IR JSON)."""
    report = report_for(scene, input_path, output_path)
    write_script(scene, output_path)
    return report
