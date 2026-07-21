"""Procedural low-poly prop geometry shipped with virtualSetmaker.

Pure-stdlib mesh kit: :mod:`.mesh` (triangle container + transforms),
:mod:`.primitives` (box/lathe/prism/sphere/torus/tube factories),
:mod:`.materials` (flat previz color palette), :mod:`.obj_writer` (OBJ/MTL
export in the de facto Y-up convention UE's Interchange importer expects),
and :mod:`.props` (one model builder per Shot Designer recipe + light rig).
"""

from .mesh import Mesh
from .materials import MATERIALS
from .obj_writer import write_mtl, write_obj
from .props import FIXTURE_MODELS, MODEL_BUILDERS, build_model

__all__ = [
    "Mesh",
    "MATERIALS",
    "write_obj",
    "write_mtl",
    "MODEL_BUILDERS",
    "FIXTURE_MODELS",
    "build_model",
]
