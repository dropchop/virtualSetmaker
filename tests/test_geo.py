"""Mesh-kit primitives: closed shells, outward winding, transform math."""

import math

import pytest

from virtualsetmaker.geo.mesh import Mesh, _rot_matrix
from virtualsetmaker.geo.primitives import (
    box,
    cone,
    cylinder,
    lathe,
    prism,
    torus,
    tube,
    uv_sphere,
)


def _samples():
    return {
        "box": box((10, 20, 30)),
        "box_chamfered": box((10, 20, 30), chamfer=2),
        "cylinder": cylinder(5, 8, 20),
        "cone": cone(6, 15),
        "lathe_pot": lathe([(5, 0), (7, 2), (8, 20), (6, 22), (0, 21)]),
        "sphere": uv_sphere((10, 12, 14)),
        "prism_z": prism([(-5, -5), (5, -5), (5, 5), (-5, 5)], "z", 0, 10),
        "prism_x": prism([(-5, 0), (5, 0), (0, 8)], "x", -3, 3),
        "torus": torus(8, 2),
        "tube": tube([(0, 0, 0), (0, 0, 10), (5, 0, 15)], 1.0),
    }


def test_primitives_are_wound_outward():
    for name, m in _samples().items():
        assert m.signed_volume() > 0, name


def test_box_volume_is_exact():
    assert box((10, 20, 30)).signed_volume() == pytest.approx(6000.0)


def test_chamfered_box_keeps_its_bbox_and_loses_volume():
    m = box((10, 20, 30), chamfer=2)
    lo, hi = m.bbox()
    assert lo == pytest.approx((-5, -10, -15))
    assert hi == pytest.approx((5, 10, 15))
    assert 0 < m.signed_volume() < 6000.0


def test_mirror_x_preserves_outward_winding():
    m = prism([(-5, 0), (5, 0), (0, 8)], "x", -3, 3)  # asymmetric in z
    v = m.signed_volume()
    m.mirror_x()
    assert m.signed_volume() == pytest.approx(v)


def test_rotation_matches_recipe_span_convention():
    # _rot_matrix must be the same Rz(yaw)*Ry(pitch)*Rx(roll) the blockout
    # math uses: pitch +90 sends +Z to +X, yaw +90 sends +X to +Y.
    m = Mesh(verts=[(0.0, 0.0, 1.0)], faces=[], face_mats=[])
    m.rotate(pitch=90)
    assert m.verts[0] == pytest.approx((1.0, 0.0, 0.0), abs=1e-9)
    m.rotate(yaw=90)
    assert m.verts[0] == pytest.approx((0.0, 1.0, 0.0), abs=1e-9)


def test_fit_to_snaps_bbox_exactly():
    m = cylinder(5, 5, 20)
    m.fit_to((-3, -4, 10), (3, 4, 30))
    lo, hi = m.bbox()
    assert lo == pytest.approx((-3, -4, 10))
    assert hi == pytest.approx((3, 4, 30))


def test_concat_offsets_faces_and_keeps_materials():
    a = box((10, 10, 10), mat="wood")
    n_a = len(a.verts)
    b = box((5, 5, 5), center=(20, 0, 0), mat="metal")
    merged = Mesh.concat([a, b])
    assert len(merged.verts) == n_a + len(b.verts)
    assert set(merged.face_mats) == {"wood", "metal"}
    assert merged.signed_volume() > 0
