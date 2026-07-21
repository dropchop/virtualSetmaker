"""OBJ/MTL writer: parse the output back and pin the axis/winding contract."""

import os

import pytest

from virtualsetmaker.geo.materials import MATERIALS
from virtualsetmaker.geo.obj_writer import write_mtl, write_obj
from virtualsetmaker.geo.primitives import box, prism


def _parse_obj(path):
    verts, normals, uvs, faces, mtls = [], [], [], [], []
    current = None
    for line in open(path, encoding="utf-8"):
        tok = line.split()
        if not tok:
            continue
        if tok[0] == "v":
            verts.append(tuple(float(v) for v in tok[1:4]))
        elif tok[0] == "vn":
            normals.append(tuple(float(v) for v in tok[1:4]))
        elif tok[0] == "vt":
            uvs.append(tuple(float(v) for v in tok[1:3]))
        elif tok[0] == "usemtl":
            current = tok[1]
            mtls.append(current)
        elif tok[0] == "f":
            corners = []
            for c in tok[1:]:
                vi, ti, ni = (int(x) for x in c.split("/"))
                corners.append((vi - 1, ti - 1, ni - 1))
            faces.append((corners, current))
    return verts, normals, uvs, faces, mtls


def _signed_volume(verts, faces):
    total = 0.0
    for corners, _mat in faces:
        (a, b, c) = (verts[corners[i][0]] for i in range(3))
        total += (
            a[0] * (b[1] * c[2] - b[2] * c[1])
            - a[1] * (b[0] * c[2] - b[2] * c[0])
            + a[2] * (b[0] * c[1] - b[1] * c[0])
        )
    return total / 6.0


def test_axis_contract_is_verbatim_z_up(tmp_path):
    # UE 5.8's Interchange OBJ translator imports coordinates verbatim
    # (measured on a live editor), so the file must carry the authored
    # recipe frame unchanged: a 10 x 20 x 30 box stays 10 x 20 x 30.
    m = box((10, 20, 30), mat="wood")
    p = str(tmp_path / "SM_VSM_TEST.obj")
    write_obj(m, p, object_name="VSM_TEST")
    verts, normals, uvs, faces, _mtls = _parse_obj(p)
    lo = [min(v[i] for v in verts) for i in range(3)]
    hi = [max(v[i] for v in verts) for i in range(3)]
    assert [h - l for h, l in zip(hi, lo)] == pytest.approx([10.0, 20.0, 30.0])
    assert normals and uvs
    assert all(len(corners) == 3 for corners, _ in faces)


def test_faces_are_double_sided(tmp_path):
    # The translator's winding convention is undocumented, so every triangle
    # ships in both windings (opposite normals): props can't import
    # inside-out, and coincident opposite pairs never z-fight (exactly one
    # is front-facing from any viewpoint).
    m = box((10, 20, 30), mat="wood")
    p = str(tmp_path / "SM_VSM_DS.obj")
    write_obj(m, p, object_name="VSM_DS")
    verts, _n, _uv, faces, _mtls = _parse_obj(p)
    assert len(faces) == 2 * m.tri_count()
    # Opposite windings cancel: net signed volume ~0, and the front copies
    # (even indices: writer emits front, then its reversed twin) are outward.
    assert abs(_signed_volume(verts, faces)) < 1e-6 * 6000
    fronts = [f for i, f in enumerate(faces) if i % 2 == 0]
    assert _signed_volume(verts, fronts) == pytest.approx(6000.0)


def test_faces_grouped_by_material_and_mtl_has_all_colors(tmp_path):
    from virtualsetmaker.geo.mesh import Mesh

    m = Mesh.concat([box((10, 10, 10), mat="wood"),
                     box((5, 5, 5), center=(20, 0, 0), mat="metal")])
    p = str(tmp_path / "SM_VSM_TWO.obj")
    write_obj(m, p, object_name="VSM_TWO")
    _v, _n, _uv, faces, mtls = _parse_obj(p)
    assert sorted(mtls) == ["metal", "wood"]  # one usemtl run per material
    assert {mat for _c, mat in faces} == {"metal", "wood"}

    mtl_path = str(tmp_path / "vsm_props.mtl")
    write_mtl(mtl_path)
    text = open(mtl_path).read()
    for name, (r, g, b) in MATERIALS.items():
        assert "newmtl %s" % name in text
        assert "Kd %.4f %.4f %.4f" % (r, g, b) in text


def test_asymmetric_model_lands_in_ue_unchanged(tmp_path):
    # A shape asymmetric in Y (a "backrest" at -Y): under the verbatim
    # importer, what's in the file IS what UE reconstructs — the backrest
    # must already sit at -Y in the file. This is the CHAIR-faces-the-right-
    # way contract.
    m = prism([(-40, 0), (-30, 90), (-40, 90)], "x", -20, 20, mat="wood")
    p = str(tmp_path / "SM_VSM_BACK.obj")
    write_obj(m, p, object_name="VSM_BACK")
    verts, _n, _uv, faces, _mtls = _parse_obj(p)
    assert min(v[1] for v in verts) == pytest.approx(-40.0)
    assert max(v[1] for v in verts) == pytest.approx(-30.0)
    assert max(v[2] for v in verts) == pytest.approx(90.0)
