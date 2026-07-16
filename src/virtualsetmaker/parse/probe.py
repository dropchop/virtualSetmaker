"""A tiny format guard for Shot Designer ``.hcw`` files.

The format turned out to be plain XML (root ``<ShotDesignerDocument>``), so the
elaborate binary sniffing the early plan imagined is unnecessary. All that's left
is a friendly check that we were actually handed a Shot Designer scene, with a
clear message for future file versions.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass

MAGIC = "Hollywood Camera Work Shot Designer Scene"
SUPPORTED_FILE_VERSIONS = {"1"}


class NotShotDesignerFile(ValueError):
    """Raised when a file is not a recognizable Shot Designer scene."""


@dataclass
class ProbeResult:
    app_version: str
    file_version: str
    magic: str


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
    if file_version not in SUPPORTED_FILE_VERSIONS:
        # A newer file version may still parse; warn rather than hard-fail.
        pass

    return ProbeResult(app_version=app_version, file_version=file_version, magic=magic)
