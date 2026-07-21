"""The shared build core used by both the CLI and the GUI.

One function does the whole job — parse a Shot Designer ``.hcw``, validate,
emit the Unreal script — and returns a :class:`BuildReport` the caller renders
however it likes (stderr notes for the CLI, log pane for the GUI).
"""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass, field, replace

from .emit import write_script
from .emit.blockouts import match_kind
from .geo import build_model, write_mtl, write_obj
from .geo.props import model_names_for_scene
from .ir import Scene
from .parse import parse_file
from .settings import Defaults


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
    prop_models: int = 0  # shipped OBJ models written to vsm_props/
    warnings: list[str] = field(default_factory=list)
    unmatched_kinds: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"{self.actors} actors, {self.props} props, {self.walls} walls, "
            f"{self.lights} lights, {self.cameras} cameras, {self.shots} shots"
            + (f", {self.prop_models} prop models" if self.prop_models else "")
        )


def _write_prop_models(scene: Scene, output_path: str) -> int:
    """Write the scene's shipped prop meshes to ``vsm_props/`` beside the
    generated script (deterministic output — always overwritten). Returns
    the number of model files written."""
    names = model_names_for_scene(
        (p.kind for p in scene.props), (lt.kind for lt in scene.lights)
    )
    if not names:
        return 0
    props_dir = os.path.join(os.path.dirname(os.path.abspath(output_path)), "vsm_props")
    os.makedirs(props_dir, exist_ok=True)
    write_mtl(os.path.join(props_dir, "vsm_props.mtl"))
    for name in names:
        write_obj(
            build_model(name),
            os.path.join(props_dir, f"SM_VSM_{name}.obj"),
            object_name=f"VSM_{name}",
        )
    return len(names)


def default_output_name(input_path: str) -> str:
    """`Scene.hcw` -> `Scene_unreal.py`."""
    base = os.path.splitext(os.path.basename(input_path))[0]
    return f"{base}_unreal.py"


def report_for(scene: Scene, input_path: str, output_path: str) -> BuildReport:
    warnings = list(scene.notes) + scene.validate()
    if scene.skipped_objects:
        counts = Counter(scene.skipped_objects)
        for tag, n in sorted(counts.items()):
            warnings.append(
                f"skipped {n} <{tag}> object(s): this Shot Designer object type is not "
                f"supported yet, so nothing was generated for it"
            )
    if scene.extra_snapshots:
        warnings.append(
            f"the document has {scene.extra_snapshots} snapshot(s) beyond the current one; "
            f"only the current snapshot is converted — objects that exist only in other "
            f"snapshots will not appear"
        )
    return BuildReport(
        input_path=input_path,
        output_path=output_path,
        actors=len(scene.actors),
        props=len(scene.props),
        walls=len(scene.walls),
        lights=len(scene.lights),
        cameras=len(scene.cameras),
        shots=len(scene.shots),
        warnings=warnings,
        unmatched_kinds=sorted(
            {p.kind for p in scene.props if p.kind and match_kind(p.kind) is None}
        ),
    )


def build_hcw(
    input_path: str,
    output_path: str,
    units_per_meter: float | None = None,
    options: Defaults | None = None,
) -> BuildReport:
    """Parse ``input_path`` and write the Unreal script to ``output_path``.

    ``options`` carries every pipeline tunable; an explicit ``units_per_meter``
    (the historical keyword) overrides it. Raises on unreadable/invalid input
    (NotShotDesignerFile, OSError); callers present the error. A returned
    report means the script was written.
    """
    opts = options or Defaults()
    if units_per_meter is not None:
        opts = replace(opts, units_per_meter=float(units_per_meter))
    scene = parse_file(
        input_path,
        units_per_meter=opts.units_per_meter,
        focal_length_mm=opts.focal_length_mm,
        camera_height_m=opts.camera_height_m,
    )
    report = report_for(scene, input_path, output_path)
    write_script(scene, output_path, opts)
    if opts.use_prop_meshes:
        report.prop_models = _write_prop_models(scene, output_path)
    return report


def build_scene_to(
    scene: Scene, input_path: str, output_path: str, options: Defaults | None = None
) -> BuildReport:
    """Same as :func:`build_hcw` but for an already-parsed/loaded Scene (IR JSON)."""
    report = report_for(scene, input_path, output_path)
    write_script(scene, output_path, options)
    if (options or Defaults()).use_prop_meshes:
        report.prop_models = _write_prop_models(scene, output_path)
    return report
