import os

import pytest

from virtualsetmaker.build import build_hcw, default_output_name

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "samples", "Sceneforclaude.hcw")
pytestmark = pytest.mark.skipif(not os.path.exists(SAMPLE), reason="sample .hcw not present")


def test_default_output_name():
    assert default_output_name("/x/y/My Scene.hcw") == "My Scene_unreal.py"


def test_build_hcw_writes_compilable_script(tmp_path):
    out = tmp_path / "out.py"
    report = build_hcw(SAMPLE, str(out))
    assert out.exists()
    compile(out.read_text(encoding="utf-8"), "<generated>", "exec")
    assert report.actors == 2
    assert report.props == 2
    assert report.lights == 2
    assert report.cameras == 1
    assert report.warnings == []
    assert report.unmatched_kinds == []  # SOFA and DOOROPEN both have recipes
    assert "2 actors" in report.summary()


def test_build_hcw_raises_on_non_shotdesigner(tmp_path):
    bad = tmp_path / "bad.hcw"
    bad.write_text("<NotAScene/>")
    with pytest.raises(Exception):
        build_hcw(str(bad), str(tmp_path / "never.py"))
    assert not (tmp_path / "never.py").exists()
