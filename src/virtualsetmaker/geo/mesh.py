"""Triangle-mesh container for the shipped prop models.

Meshes live in the **recipe frame**: +X right, +Y toward the prop's front,
+Z up, origin on the floor, units are cm — identical to blockout recipes, so
a model and its recipe are interchangeable in every downstream calculation.
Faces are wound so the right-hand-rule normal points out of the solid
(positive signed volume).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


def _rot_matrix(pitch: float, yaw: float, roll: float) -> list[list[float]]:
    """Rows of ``Rz(yaw)·Ry(pitch)·Rx(roll)`` — the same UE rotator order used
    by :func:`virtualsetmaker.emit.blockouts.recipe_span`."""
    p, y, r = (math.radians(a) for a in (pitch, yaw, roll))
    cy, sy = math.cos(y), math.sin(y)
    cp, sp = math.cos(p), math.sin(p)
    cr, sr = math.cos(r), math.sin(r)
    return [
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
        [-sp, cp * sr, cp * cr],
    ]


@dataclass
class Mesh:
    verts: list[tuple[float, float, float]] = field(default_factory=list)
    faces: list[tuple[int, int, int]] = field(default_factory=list)
    face_mats: list[str] = field(default_factory=list)

    # -- construction ------------------------------------------------------

    def add(self, other: "Mesh") -> "Mesh":
        base = len(self.verts)
        self.verts.extend(other.verts)
        self.faces.extend((a + base, b + base, c + base) for a, b, c in other.faces)
        self.face_mats.extend(other.face_mats)
        return self

    @classmethod
    def concat(cls, meshes: list["Mesh"]) -> "Mesh":
        out = cls()
        for m in meshes:
            out.add(m)
        return out

    # -- transforms (in place, chainable) ------------------------------------

    def translate(self, dx: float, dy: float, dz: float) -> "Mesh":
        self.verts = [(x + dx, y + dy, z + dz) for x, y, z in self.verts]
        return self

    def scale(self, sx: float, sy: float, sz: float) -> "Mesh":
        self.verts = [(x * sx, y * sy, z * sz) for x, y, z in self.verts]
        if sx * sy * sz < 0:  # odd number of negative axes = reflection
            self._flip_winding()
        return self

    def rotate(self, pitch: float = 0.0, yaw: float = 0.0, roll: float = 0.0) -> "Mesh":
        m = _rot_matrix(pitch, yaw, roll)
        self.verts = [
            (
                m[0][0] * x + m[0][1] * y + m[0][2] * z,
                m[1][0] * x + m[1][1] * y + m[1][2] * z,
                m[2][0] * x + m[2][1] * y + m[2][2] * z,
            )
            for x, y, z in self.verts
        ]
        return self

    def mirror_x(self) -> "Mesh":
        return self.scale(-1.0, 1.0, 1.0)  # scale() flips winding for us

    def _flip_winding(self) -> None:
        self.faces = [(a, c, b) for a, b, c in self.faces]

    # -- queries -------------------------------------------------------------

    def bbox(self) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        xs = [v[0] for v in self.verts]
        ys = [v[1] for v in self.verts]
        zs = [v[2] for v in self.verts]
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

    def signed_volume(self) -> float:
        """Positive when faces are wound outward (right-hand rule)."""
        total = 0.0
        for a, b, c in self.faces:
            (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = (
                self.verts[a],
                self.verts[b],
                self.verts[c],
            )
            total += (
                x0 * (y1 * z2 - z1 * y2)
                - y0 * (x1 * z2 - z1 * x2)
                + z0 * (x1 * y2 - y1 * x2)
            )
        return total / 6.0

    def ensure_outward(self) -> "Mesh":
        """Flip all faces if the mesh is globally wound inward.

        Only valid for a single consistently-wound closed shell (which is what
        every primitive factory produces before merging)."""
        if self.signed_volume() < 0:
            self._flip_winding()
        return self

    def fit_to(
        self,
        lo: tuple[float, float, float],
        hi: tuple[float, float, float],
    ) -> "Mesh":
        """Affine-snap the bbox exactly onto ``lo..hi`` (per-axis scale+shift).

        Used to kill sub-millimeter drift from lathe/chamfer radii after a
        model is authored to its recipe's dimensions — never to correct a
        gross authoring error (callers pre-check the extents are close)."""
        (alo, ahi) = self.bbox()
        s = []
        t = []
        for i in range(3):
            span = ahi[i] - alo[i]
            want = hi[i] - lo[i]
            si = want / span if span > 1e-9 else 1.0
            s.append(si)
            t.append(lo[i] - alo[i] * si)
        self.verts = [
            (x * s[0] + t[0], y * s[1] + t[1], z * s[2] + t[2]) for x, y, z in self.verts
        ]
        return self

    def tri_count(self) -> int:
        return len(self.faces)
