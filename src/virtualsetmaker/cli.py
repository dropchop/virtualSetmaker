"""Command-line entry point for virtualSetmaker.

    vsm build  <scene.hcw>                  # parse .hcw -> Scene_unreal.py beside it
    vsm emit   <scene.json>                 # emit straight from an IR JSON file
    vsm parse  <scene.hcw>  [-o scene.json] # parse .hcw -> IR JSON (inspect)
    vsm probe  <scene.hcw>                  # confirm the file is a Shot Designer scene
    vsm props                               # list the prop blockout library
    vsm gui                                 # open the graphical exporter

Use ``-o`` to pick an output path; tunables (lens, wall size, ...) come from
flags or the ``defaults`` section of ``~/.virtualsetmaker.json``.
"""

from __future__ import annotations

import argparse
import os
import sys

from .build import build_hcw, build_scene_to, default_output_name
from .emit.blockouts import ALIASES, RECIPES
from .ir import Scene
from .parse import parse_file
from .parse.probe import NotShotDesignerFile, probe
from .settings import Defaults, load_settings, resolve_defaults


def _default_out(inp: str, ext: str) -> str:
    base = inp.rsplit(".", 1)[0]
    return f"{base}.{ext}"


def _default_script_out(inp: str) -> str:
    """`dir/Scene.hcw` -> `dir/Scene_unreal.py` — same convention as the GUI."""
    return os.path.join(os.path.dirname(os.path.abspath(inp)), default_output_name(inp))


def _fail(exc: Exception) -> int:
    print(f"error: {exc}", file=sys.stderr)
    return 1


# argparse dest -> Defaults field, for every tunable flag. Flags default to
# None so "not given" is distinguishable: flag > config defaults > built-in.
_FLAG_FIELDS = {
    "units_per_meter": "units_per_meter",
    "focal_length": "focal_length_mm",
    "camera_height": "camera_height_m",
    "wall_height": "wall_height_cm",
    "wall_thickness": "wall_thickness_cm",
    "frame_rate": "frame_rate",
    "content_path": "ue_content_path",
}


def _options_from_args(args: argparse.Namespace) -> Defaults:
    overrides = {
        field: getattr(args, dest)
        for dest, field in _FLAG_FIELDS.items()
        if getattr(args, dest, None) is not None
    }
    return resolve_defaults(load_settings(), overrides)


def _cmd_probe(args: argparse.Namespace) -> int:
    try:
        result = probe(args.input)
    except NotShotDesignerFile as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print("Shot Designer scene OK")
    print(f"  app version : {result.app_version}")
    print(f"  file version: {result.file_version}")
    for w in result.warnings:
        print(f"warning: {w}", file=sys.stderr)
    return 0


def _cmd_parse(args: argparse.Namespace) -> int:
    opts = _options_from_args(args)
    try:
        scene = parse_file(
            args.input,
            units_per_meter=opts.units_per_meter,
            focal_length_mm=opts.focal_length_mm,
            camera_height_m=opts.camera_height_m,
        )
        out = args.output or _default_out(args.input, "json")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(scene.to_json())
    except (NotShotDesignerFile, OSError) as exc:
        return _fail(exc)
    _report(scene, f"parsed -> {out}")
    return 0


def _cmd_build(args: argparse.Namespace) -> int:
    out = args.output or _default_script_out(args.input)
    try:
        report = build_hcw(args.input, out, options=_options_from_args(args))
    except (NotShotDesignerFile, OSError) as exc:
        return _fail(exc)
    _print_report(report)
    return 0


def _cmd_emit(args: argparse.Namespace) -> int:
    try:
        with open(args.input, "r", encoding="utf-8") as fh:
            scene = Scene.from_json(fh.read())
    except OSError as exc:
        return _fail(exc)
    except (ValueError, KeyError, TypeError) as exc:
        return _fail(
            ValueError(f"{args.input!r} is not a virtualSetmaker IR JSON file ({exc})")
        )
    out = args.output or _default_script_out(args.input)
    try:
        report = build_scene_to(scene, args.input, out, options=_options_from_args(args))
    except OSError as exc:
        return _fail(exc)
    _print_report(report)
    return 0


def _cmd_gui(args: argparse.Namespace) -> int:
    from .gui import main as gui_main

    return gui_main()


def _print_report(report) -> None:
    for w in report.warnings:
        print(f"warning: {w}", file=sys.stderr)
    for kind in report.unmatched_kinds:
        print(
            f"note: no blockout recipe for prop kind {kind!r} (generic cube used) — "
            f"send a .hcw containing it and it can be added",
            file=sys.stderr,
        )
    print(f"built Unreal script -> {report.output_path}")
    print(f"  {report.summary()}")


def _cmd_props(args: argparse.Namespace) -> int:
    print(f"{len(RECIPES)} blockout recipes:")
    for name in sorted(RECIPES):
        parts = RECIPES[name]
        aliases = sorted({needle for needle, target in ALIASES if target == name and needle != name})
        alias_note = f"  (matches: {', '.join(aliases)})" if aliases else ""
        print(f"  {name:<12} {len(parts)} parts{alias_note}")
    print("Unknown prop kinds fall back to a generic 1 m cube.")
    return 0


def _report(scene: Scene, action: str) -> None:
    print(action)
    print(
        f"  {len(scene.actors)} actors, {len(scene.props)} props, "
        f"{len(scene.walls)} walls, {len(scene.lights)} lights, "
        f"{len(scene.cameras)} cameras, {len(scene.shots)} shots"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vsm", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    # Tunable flags default to None: an omitted flag falls back to the config
    # file's "defaults" section (~/.virtualsetmaker.json), then the built-in.
    def add_parse_opts(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--units-per-meter",
            type=float,
            help="Shot Designer units per real-world meter (default 100: 1 unit = 1 cm).",
        )
        p.add_argument(
            "--focal-length",
            type=float,
            help="camera focal length in mm for every camera (default 35).",
        )
        p.add_argument(
            "--camera-height",
            type=float,
            help="camera height in meters (default 1.5; Shot Designer stores none).",
        )

    def add_emit_opts(p: argparse.ArgumentParser) -> None:
        p.add_argument("--wall-height", type=float, help="wall blockout height in cm (default 250).")
        p.add_argument(
            "--wall-thickness", type=float, help="wall blockout thickness in cm (default 10)."
        )
        p.add_argument(
            "--frame-rate", type=float, help="sequence frame rate (default: the scene's own, 24)."
        )
        p.add_argument(
            "--content-path",
            help="UE content path for the level sequence asset (default /Game/VSM).",
        )

    p_probe = sub.add_parser("probe", help="check a .hcw file is a Shot Designer scene")
    p_probe.add_argument("input")
    p_probe.set_defaults(func=_cmd_probe)

    p_parse = sub.add_parser("parse", help="parse .hcw -> IR JSON")
    p_parse.add_argument("input")
    p_parse.add_argument("-o", "--output")
    add_parse_opts(p_parse)
    p_parse.set_defaults(func=_cmd_parse)

    p_build = sub.add_parser("build", help="parse .hcw -> Unreal Python script")
    p_build.add_argument("input")
    p_build.add_argument("-o", "--output")
    add_parse_opts(p_build)
    add_emit_opts(p_build)
    p_build.set_defaults(func=_cmd_build)

    p_emit = sub.add_parser("emit", help="emit Unreal Python script from IR JSON")
    p_emit.add_argument("input")
    p_emit.add_argument("-o", "--output")
    add_emit_opts(p_emit)
    p_emit.set_defaults(func=_cmd_emit)

    p_props = sub.add_parser("props", help="list the prop blockout library")
    p_props.set_defaults(func=_cmd_props)

    p_gui = sub.add_parser("gui", help="open the graphical exporter")
    p_gui.set_defaults(func=_cmd_gui)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
