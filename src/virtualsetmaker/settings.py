"""Shared user settings for the CLI and the GUI.

One JSON file at ``~/.virtualsetmaker.json`` holds both front-end state
(``input_dir``/``output_dir``, written by the GUI) and a ``defaults`` section of
pipeline tunables that both ``vsm`` and the GUI honor. The file is meant to be
hand-editable; unknown keys and bad values are ignored rather than fatal.

Precedence for any tunable: CLI flag > config ``defaults`` section > built-in.
The GUI's historical top-level ``units_per_meter`` key wins over
``defaults.units_per_meter`` so old settings files keep meaning what they did.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, fields
from typing import Any, Optional

SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".virtualsetmaker.json")


@dataclass
class Defaults:
    """Every tunable default in the pipeline, in one place.

    Parse-time knobs shape the IR (Shot Designer carries no camera height or
    lens data, so these fill the gaps); emit-time knobs shape the generated
    Unreal script.
    """

    # -- parse-time --------------------------------------------------------
    units_per_meter: float = 100.0  # Shot Designer units per meter (1 unit = 1 cm)
    focal_length_mm: float = 35.0  # lens for every camera (SD stores none)
    camera_height_m: float = 1.5  # eye-level default (SD is 2D top-down)
    # -- emit-time ---------------------------------------------------------
    wall_height_cm: float = 250.0
    wall_thickness_cm: float = 10.0
    frame_rate: Optional[float] = None  # None = keep the scene's own rate
    ue_content_path: str = "/Game/VSM"  # where the level sequence asset is created
    manny_paths: Optional[list[str]] = None  # None = emitter's built-in candidates
    quinn_paths: Optional[list[str]] = None


def load_settings(path: str = SETTINGS_PATH) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(settings: dict, path: str = SETTINGS_PATH) -> None:
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(settings, fh, indent=2)
    except OSError:
        pass  # persistence is best-effort only


def defaults_from_settings(raw: dict) -> Defaults:
    """Build :class:`Defaults` from a settings dict; never raises on bad data."""
    d = Defaults()
    section = raw.get("defaults")
    if isinstance(section, dict):
        for f in fields(Defaults):
            if f.name not in section:
                continue
            value = section[f.name]
            if f.name in ("manny_paths", "quinn_paths"):
                if isinstance(value, list) and all(isinstance(p, str) for p in value):
                    setattr(d, f.name, list(value))
            elif f.name == "ue_content_path":
                if isinstance(value, str) and value.startswith("/"):
                    d.ue_content_path = value
            else:
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    continue
                if number > 0:
                    setattr(d, f.name, number)
    top_upm = raw.get("units_per_meter")  # legacy GUI key, kept authoritative
    if isinstance(top_upm, (int, float)) and top_upm > 0:
        d.units_per_meter = float(top_upm)
    return d


def resolve_defaults(raw: dict, overrides: dict[str, Any]) -> Defaults:
    """Config-file defaults with non-None per-run overrides applied on top."""
    d = defaults_from_settings(raw)
    for f in fields(Defaults):
        value = overrides.get(f.name)
        if value is not None:
            setattr(d, f.name, value)
    return d
