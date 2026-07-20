"""A tiny format guard for Shot Designer ``.hcw`` files.

The format turned out to be plain XML (root ``<ShotDesignerDocument>``), so the
elaborate binary sniffing the early plan imagined is unnecessary. All that's left
is a friendly check that we were actually handed a Shot Designer scene, with a
clear message for future file versions.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

MAGIC = "Hollywood Camera Work Shot Designer Scene"
SUPPORTED_FILE_VERSIONS = {"1"}


class NotShotDesignerFile(ValueError):
    """Raised when a file is not a recognizable Shot Designer scene."""


@dataclass
class ProbeResult:
    app_version: str
    file_version: str
    magic: str
    warnings: list[str] = field(default_factory=list)


def probe(path: str) -> ProbeResult:
    """Confirm ``path`` is a Shot Designer scene and return its preamble.

    Raises :class:`NotShotDesignerFile` with an actionable message otherwise.
    """
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:  # not XML at all
        raise NotShotDesignerFile(
            f"{path!r} is not valid XML; expected a Shot Designer .hcw scene ({exc})."
        ) from exc
    return probe_root(root, path)


def probe_root(root: ET.Element, path: str) -> ProbeResult:
    """Validate an already-parsed document root (``path`` is for messages only)."""
    if root.tag != "ShotDesignerDocument":
        raise NotShotDesignerFile(
            f"{path!r} has root <{root.tag}>, expected <ShotDesignerDocument>."
        )

    magic = root.findtext("DocumentPreamble/magic", default="")
    if magic != MAGIC:
        raise NotShotDesignerFile(
            f"{path!r} is missing the Shot Designer magic string (found {magic!r})."
        )

    file_version = root.findtext("DocumentPreamble/fileVersion", default="")
    app_version = root.findtext("DocumentPreamble/appVersion", default="")
    warnings: list[str] = []
    if file_version not in SUPPORTED_FILE_VERSIONS:
        # A newer file version may still parse; warn rather than hard-fail.
        warnings.append(
            f"file version {file_version!r} is not the tested "
            f"{sorted(SUPPORTED_FILE_VERSIONS)}; parsing will be attempted but "
            f"newer Shot Designer features may be missing from the result"
        )

    return ProbeResult(
        app_version=app_version, file_version=file_version, magic=magic, warnings=warnings
    )
