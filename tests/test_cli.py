import io
import os
import shutil
from contextlib import redirect_stderr, redirect_stdout

from virtualsetmaker.cli import main

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "samples", "Sceneforclaude.hcw")


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def test_build_missing_file_prints_error_not_traceback(tmp_path):
    code, _out, err = _run(["build", str(tmp_path / "nope.hcw")])
    assert code == 1
    assert err.startswith("error: ")
    assert "Traceback" not in err


def test_build_non_shotdesigner_file_prints_error(tmp_path):
    bad = tmp_path / "bad.hcw"
    bad.write_text("<NotAScene/>")
    code, _out, err = _run(["build", str(bad)])
    assert code == 1
    assert err.startswith("error: ")


def test_parse_missing_file_prints_error(tmp_path):
    code, _out, err = _run(["parse", str(tmp_path / "nope.hcw")])
    assert code == 1
    assert err.startswith("error: ")


def test_emit_garbage_json_prints_error(tmp_path):
    garbage = tmp_path / "scene.json"
    garbage.write_text("{ not json")
    code, _out, err = _run(["emit", str(garbage)])
    assert code == 1
    assert err.startswith("error: ")
    assert "IR JSON" in err


def test_build_default_output_is_unreal_py_beside_input(tmp_path):
    inp = tmp_path / "MyScene.hcw"
    shutil.copyfile(SAMPLE, str(inp))
    code, out, _err = _run(["build", str(inp)])
    assert code == 0
    expected = tmp_path / "MyScene_unreal.py"
    assert expected.exists()
    assert str(expected) in out


def test_build_flags_reach_the_emitted_script(tmp_path):
    inp = tmp_path / "MyScene.hcw"
    shutil.copyfile(SAMPLE, str(inp))
    out_path = tmp_path / "custom.py"
    code, _out, _err = _run(
        ["build", str(inp), "-o", str(out_path),
         "--wall-height", "275", "--content-path", "/Game/Blocking", "--focal-length", "50"]
    )
    assert code == 0
    script = out_path.read_text()
    assert "WALL_HEIGHT_CM = 275.0" in script
    assert "UE_CONTENT_PATH = '/Game/Blocking'" in script
    assert '"focal": 50.0' in script


def test_probe_ok_on_sample():
    code, out, _err = _run(["probe", SAMPLE])
    assert code == 0
    assert "Shot Designer scene OK" in out
