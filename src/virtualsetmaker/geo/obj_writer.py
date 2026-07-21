"""OBJ/MTL export for the shipped prop models.

Axis contract (the load-bearing decision): models are authored Z-up in the
recipe frame; the writer emits the **de facto standard Y-up right-handed
OBJ** (what a Blender default export produces) by mapping every vertex
``(x, y, z) -> (x, z, y)``. That map is a reflection, so each face's vertex
order is reversed to keep OBJ faces CCW-front-facing. UE's importer applies
its usual mirror on import, landing the model back in the recipe frame:
Z-up, 1 unit = 1 cm, front at +Y — mesh yaw offset is always zero.

Flat per-face normals are emitted (faceted previz look, no importer
smoothing surprises) plus dominant-axis planar UVs (silences UE's
missing-UV warnings and feeds lightmap UV generation). Faces are grouped
into ``usemtl`` runs so each material becomes one UE material slot.
"""

from __future__ import annotations

import math
import os

from .materials import MATERIALS
from .mesh import Mesh

MTL_FILENAME = "vsm_props.mtl"


def _obj_vert(v):
    x, y, z = v
    return (x, z, y)  # recipe Z-up -> OBJ Y-up (reflection)


def write_obj(mesh: Mesh, path: str, object_name: str, mtllib: str = MTL_FILENAME) -> None:
    verts = [_obj_vert(v) for v in mesh.verts]
    # Reflection flips orientation: reverse each face to stay CCW-outward.
    faces = [(a, c, b) for (a, b, c) in mesh.faces]

    # Group faces by material, keeping a stable order.
    by_mat: dict[str, list[int]] = {}
    for fi, mat in enumerate(mesh.face_mats):
        by_mat.setdefault(mat, []).append(fi)

    lines = [
        "# virtualSetmaker prop model (auto-generated; cm, Y-up)",
        "mtllib %s" % mtllib,
        "o %s" % object_name,
    ]
    for x, y, z in verts:
        lines.append("v %.4f %.4f %.4f" % (x, y, z))

    normals: list[tuple[float, float, float]] = []
    uvs: list[tuple[float, float]] = []
    face_lines: list[tuple[str, list[str]]] = []
    for mat in sorted(by_mat):
        chunk = []
        for fi in by_mat[mat]:
            a, b, c = faces[fi]
            va, vb, vc = verts[a], verts[b], verts[c]
            e1 = tuple(vb[i] - va[i] for i in range(3))
            e2 = tuple(vc[i] - va[i] for i in range(3))
            n = (
                e1[1] * e2[2] - e1[2] * e2[1],
                e1[2] * e2[0] - e1[0] * e2[2],
                e1[0] * e2[1] - e1[1] * e2[0],
            )
            ln = math.sqrt(sum(cmp * cmp for cmp in n)) or 1.0
            n = (n[0] / ln, n[1] / ln, n[2] / ln)
            normals.append(n)
            ni = len(normals)
            # dominant-axis planar projection, 1 cm = 0.01 UV
            ax = max(range(3), key=lambda i: abs(n[i]))
            uv_axes = [i for i in range(3) if i != ax]
            corner_uv_ids = []
            for v in (va, vb, vc):
                uvs.append((v[uv_axes[0]] * 0.01, v[uv_axes[1]] * 0.01))
                corner_uv_ids.append(len(uvs))
            chunk.append(
                "f %d/%d/%d %d/%d/%d %d/%d/%d"
                % (
                    a + 1, corner_uv_ids[0], ni,
                    b + 1, corner_uv_ids[1], ni,
                    c + 1, corner_uv_ids[2], ni,
                )
            )
        face_lines.append((mat, chunk))

    for u, v in uvs:
        lines.append("vt %.4f %.4f" % (u, v))
    for nx, ny, nz in normals:
        lines.append("vn %.4f %.4f %.4f" % (nx, ny, nz))
    for mat, chunk in face_lines:
        lines.append("usemtl %s" % mat)
        lines.extend(chunk)

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def write_mtl(path: str, materials: dict[str, tuple[float, float, float]] | None = None) -> None:
    materials = materials if materials is not None else MATERIALS
    lines = ["# virtualSetmaker previz materials (flat colors)"]
    for name in sorted(materials):
        r, g, b = materials[name]
        lines.append("newmtl %s" % name)
        lines.append("Kd %.4f %.4f %.4f" % (r, g, b))
        lines.append("Ka 0 0 0")
        lines.append("Ks 0 0 0")
        lines.append("d %s" % ("0.5" if name == "glass" else "1"))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def props_dir_for(script_path: str) -> str:
    """The ``vsm_props/`` directory beside a generated script."""
    return os.path.join(os.path.dirname(os.path.abspath(script_path)), "vsm_props")
