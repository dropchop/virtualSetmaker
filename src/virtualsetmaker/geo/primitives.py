"""Primitive factories for the prop mesh kit.

Every factory returns a closed, outward-wound :class:`~.mesh.Mesh` in the
recipe frame (cm, +Z up). Construction is wound consistently within each
shell and then globally oriented by signed volume (``ensure_outward``), so
individual factories don't need hand-derived winding proofs.
"""

from __future__ import annotations

import math

from .mesh import Mesh


def _quad(mesh: Mesh, a: int, b: int, c: int, d: int, mat: str) -> None:
    mesh.faces.append((a, b, c))
    mesh.face_mats.append(mat)
    mesh.faces.append((a, c, d))
    mesh.face_mats.append(mat)


def _tri(mesh: Mesh, a: int, b: int, c: int, mat: str) -> None:
    mesh.faces.append((a, b, c))
    mesh.face_mats.append(mat)


def box(size, center=(0.0, 0.0, 0.0), chamfer: float = 0.0, mat: str = "plastic_light") -> Mesh:
    """Axis-aligned cuboid; ``chamfer > 0`` bevels all 12 edges (24-vert solid)."""
    hx, hy, hz = size[0] / 2.0, size[1] / 2.0, size[2] / 2.0
    cx, cy, cz = center
    c = min(chamfer, hx * 0.49, hy * 0.49, hz * 0.49)
    m = Mesh()
    if c <= 1e-9:
        for sz_ in (-1, 1):
            for sy_ in (-1, 1):
                for sx_ in (-1, 1):
                    m.verts.append((cx + sx_ * hx, cy + sy_ * hy, cz + sz_ * hz))
        # vertex index = sx>0 | sy>0<<1 | sz>0<<2
        quads = [
            (0, 1, 3, 2, "z-"), (4, 6, 7, 5, "z+"),
            (0, 2, 6, 4, "x-"), (1, 5, 7, 3, "x+"),
            (0, 4, 5, 1, "y-"), (2, 3, 7, 6, "y+"),
        ]
        for a, b, c_, d, _tag in quads:
            _quad(m, a, b, c_, d, mat)
        return m.ensure_outward()

    # Chamfered: each corner contributes one vertex per adjacent face plane.
    idx: dict[tuple[int, int, int, str], int] = {}
    for sx_ in (-1, 1):
        for sy_ in (-1, 1):
            for sz_ in (-1, 1):
                fx = (cx + sx_ * hx, cy + sy_ * (hy - c), cz + sz_ * (hz - c))
                fy = (cx + sx_ * (hx - c), cy + sy_ * hy, cz + sz_ * (hz - c))
                fz = (cx + sx_ * (hx - c), cy + sy_ * (hy - c), cz + sz_ * hz)
                for tag, v in (("x", fx), ("y", fy), ("z", fz)):
                    idx[(sx_, sy_, sz_, tag)] = len(m.verts)
                    m.verts.append(v)

    def corner(sx_, sy_, sz_, tag):
        return idx[(sx_, sy_, sz_, tag)]

    # 6 inset face rectangles.
    for s in (-1, 1):
        _quad(m, corner(s, -1, -1, "x"), corner(s, 1, -1, "x"),
              corner(s, 1, 1, "x"), corner(s, -1, 1, "x"), mat)
        _quad(m, corner(-1, s, -1, "y"), corner(1, s, -1, "y"),
              corner(1, s, 1, "y"), corner(-1, s, 1, "y"), mat)
        _quad(m, corner(-1, -1, s, "z"), corner(1, -1, s, "z"),
              corner(1, 1, s, "z"), corner(-1, 1, s, "z"), mat)
    # 12 edge bevels: for each pair of face tags, the edge quad joins the two
    # face verts of the two corners sharing that edge.
    for sy_ in (-1, 1):
        for sz_ in (-1, 1):  # edges along X (faces y & z)
            _quad(m, corner(-1, sy_, sz_, "y"), corner(1, sy_, sz_, "y"),
                  corner(1, sy_, sz_, "z"), corner(-1, sy_, sz_, "z"), mat)
    for sx_ in (-1, 1):
        for sz_ in (-1, 1):  # edges along Y (faces x & z)
            _quad(m, corner(sx_, -1, sz_, "x"), corner(sx_, 1, sz_, "x"),
                  corner(sx_, 1, sz_, "z"), corner(sx_, -1, sz_, "z"), mat)
        for sy_ in (-1, 1):  # edges along Z (faces x & y)
            _quad(m, corner(sx_, sy_, -1, "x"), corner(sx_, sy_, 1, "x"),
                  corner(sx_, sy_, 1, "y"), corner(sx_, sy_, -1, "y"), mat)
    # 8 corner triangles.
    for sx_ in (-1, 1):
        for sy_ in (-1, 1):
            for sz_ in (-1, 1):
                _tri(m, corner(sx_, sy_, sz_, "x"), corner(sx_, sy_, sz_, "y"),
                     corner(sx_, sy_, sz_, "z"), mat)
    return _orient_convex(m, center)


def _orient_convex(m: Mesh, center) -> Mesh:
    """Per-face outward orientation for convex solids (normal vs centroid)."""
    fixed = []
    for (a, b, c) in m.faces:
        va, vb, vc = m.verts[a], m.verts[b], m.verts[c]
        e1 = tuple(vb[i] - va[i] for i in range(3))
        e2 = tuple(vc[i] - va[i] for i in range(3))
        n = (
            e1[1] * e2[2] - e1[2] * e2[1],
            e1[2] * e2[0] - e1[0] * e2[2],
            e1[0] * e2[1] - e1[1] * e2[0],
        )
        mid = tuple((va[i] + vb[i] + vc[i]) / 3.0 - center[i] for i in range(3))
        if sum(n[i] * mid[i] for i in range(3)) < 0:
            fixed.append((a, c, b))
        else:
            fixed.append((a, b, c))
    m.faces = fixed
    return m


def lathe(profile, seg: int = 16, center=(0.0, 0.0, 0.0), mat: str = "plastic_light") -> Mesh:
    """Revolve a bottom-to-top ``[(radius, z), ...]`` profile about +Z.

    ``r == 0`` endpoints become poles; open ends (r > 0) are capped flat.
    """
    m = Mesh()
    cx, cy, cz = center
    rings: list[list[int] | int] = []  # per profile point: list of ring ids, or pole id
    for r, z in profile:
        if abs(r) < 1e-9:
            rings.append(len(m.verts))
            m.verts.append((cx, cy, cz + z))
        else:
            ring = []
            for i in range(seg):
                t = 2.0 * math.pi * i / seg
                ring.append(len(m.verts))
                m.verts.append((cx + r * math.cos(t), cy + r * math.sin(t), cz + z))
            rings.append(ring)

    def is_pole(entry):
        return isinstance(entry, int)

    # side bands
    for k in range(len(rings) - 1):
        lo, hi = rings[k], rings[k + 1]
        if is_pole(lo) and is_pole(hi):
            continue
        if is_pole(lo):
            for i in range(seg):
                _tri(m, lo, hi[(i + 1) % seg], hi[i], mat)
        elif is_pole(hi):
            for i in range(seg):
                _tri(m, lo[i], lo[(i + 1) % seg], hi, mat)
        else:
            for i in range(seg):
                j = (i + 1) % seg
                _quad(m, lo[i], lo[j], hi[j], hi[i], mat)
    # caps on open ends
    if not is_pole(rings[0]):
        ring = rings[0]
        c0 = len(m.verts)
        m.verts.append((cx, cy, cz + profile[0][1]))
        for i in range(seg):
            _tri(m, c0, ring[(i + 1) % seg], ring[i], mat)
    if not is_pole(rings[-1]):
        ring = rings[-1]
        c1 = len(m.verts)
        m.verts.append((cx, cy, cz + profile[-1][1]))
        for i in range(seg):
            _tri(m, c1, ring[i], ring[(i + 1) % seg], mat)
    return m.ensure_outward()


def cylinder(rx: float, ry: float, h: float, center=(0.0, 0.0, 0.0), seg: int = 16,
             mat: str = "plastic_light") -> Mesh:
    """Elliptical cylinder standing on ``center`` (z = base) .. base+h."""
    m = lathe([(1.0, 0.0), (1.0, 1.0)], seg=seg, mat=mat)
    m.scale(rx, ry, h)
    return m.translate(*center)


def cone(r: float, h: float, center=(0.0, 0.0, 0.0), seg: int = 16,
         mat: str = "plastic_light") -> Mesh:
    m = lathe([(r, 0.0), (0.0, h)], seg=seg, mat=mat)
    return m.translate(*center)


def uv_sphere(size, center=(0.0, 0.0, 0.0), seg: int = 12, rings: int = 8,
              mat: str = "plastic_light") -> Mesh:
    profile = []
    for k in range(rings + 1):
        a = math.pi * k / rings
        profile.append((math.sin(a), -math.cos(a)))
    m = lathe(profile, seg=seg, mat=mat)
    m.scale(size[0] / 2.0, size[1] / 2.0, size[2] / 2.0)
    return m.translate(*center)


def prism(points_2d, axis: str, lo: float, hi: float, mat: str = "plastic_light") -> Mesh:
    """CONVEX polygon (CCW) extruded along ``axis`` from ``lo`` to ``hi``.

    2D coords map to the remaining axes in order: axis "x" -> (y, z),
    "y" -> (x, z), "z" -> (x, y). Concave silhouettes must be composed from
    several convex prisms (fan triangulation is used for the caps).
    """
    def lift(u, v, w):
        if axis == "x":
            return (w, u, v)
        if axis == "y":
            return (u, w, v)
        return (u, v, w)

    n = len(points_2d)
    m = Mesh()
    for w in (lo, hi):
        for (u, v) in points_2d:
            m.verts.append(lift(u, v, w))
    for i in range(n):  # sides
        j = (i + 1) % n
        _quad(m, i, j, n + j, n + i, mat)
    for i in range(1, n - 1):  # caps (fan)
        _tri(m, 0, i, i + 1, mat)          # lo cap
        _tri(m, n, n + i + 1, n + i, mat)  # hi cap
    return m.ensure_outward()


def torus(major_r: float, minor_r: float, center=(0.0, 0.0, 0.0), seg: int = 16,
          ring_seg: int = 8, squash_z: float = 1.0, mat: str = "plastic_light") -> Mesh:
    m = Mesh()
    for i in range(seg):
        t = 2.0 * math.pi * i / seg
        ct, st = math.cos(t), math.sin(t)
        for j in range(ring_seg):
            p = 2.0 * math.pi * j / ring_seg
            r = major_r + minor_r * math.cos(p)
            m.verts.append((r * ct, r * st, minor_r * math.sin(p) * squash_z))
    for i in range(seg):
        i2 = (i + 1) % seg
        for j in range(ring_seg):
            j2 = (j + 1) % ring_seg
            _quad(m, i * ring_seg + j, i2 * ring_seg + j, i2 * ring_seg + j2,
                  i * ring_seg + j2, mat)
    m.ensure_outward()
    return m.translate(*center)


def tube(points, radius: float, seg: int = 8, mat: str = "metal") -> Mesh:
    """Butt-joined capped cylinders along a 3D polyline (rails, handles, jibs)."""
    out = Mesh()
    for (a, b) in zip(points, points[1:]):
        d = tuple(b[i] - a[i] for i in range(3))
        length = math.sqrt(sum(c * c for c in d))
        if length < 1e-9:
            continue
        seg_mesh = lathe([(radius, 0.0), (radius, length)], seg=seg, mat=mat)
        # rotate +Z onto d: yaw about Z after pitching Z toward XY
        dx, dy, dz = (c / length for c in d)
        pitch = math.degrees(math.acos(max(-1.0, min(1.0, dz))))
        yaw = math.degrees(math.atan2(dy, dx))
        # pitch rotates +Z toward +X (Ry), then yaw carries it to (dx, dy)
        seg_mesh.rotate(pitch=pitch, yaw=0.0, roll=0.0)
        seg_mesh.rotate(yaw=yaw)
        out.add(seg_mesh.translate(*a))
    return out
