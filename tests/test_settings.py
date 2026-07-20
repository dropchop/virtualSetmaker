import os

from virtualsetmaker.emit.unreal_python import build_script
from virtualsetmaker.ir import Scene, Wall, Vec3
from virtualsetmaker.parse import parse_file
from virtualsetmaker.settings import (
    Defaults,
    defaults_from_settings,
    load_settings,
    resolve_defaults,
    save_settings,
)

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "samples", "Sceneforclaude.hcw")


def test_settings_roundtrip(tmp_path):
    path = str(tmp_path / "settings.json")
    save_settings({"output_dir": "/tmp/x", "defaults": {"wall_height_cm": 300}}, path)
    raw = load_settings(path)
    assert raw["output_dir"] == "/tmp/x"
    assert defaults_from_settings(raw).wall_height_cm == 300.0


def test_missing_or_malformed_settings_fall_back(tmp_path):
    assert load_settings(str(tmp_path / "missing.json")) == {}
    bad = tmp_path / "bad.json"
    bad.write_text("not json at all {")
    assert load_settings(str(bad)) == {}
    # bad value types inside defaults are skipped, not fatal
    d = defaults_from_settings({"defaults": {"focal_length_mm": "wide", "wall_height_cm": -5}})
    assert d.focal_length_mm == 35.0
    assert d.wall_height_cm == 250.0


def test_flag_beats_config_beats_builtin():
    raw = {"defaults": {"focal_length_mm": 50}}
    assert resolve_defaults(raw, {}).focal_length_mm == 50.0
    assert resolve_defaults(raw, {"focal_length_mm": 85.0}).focal_length_mm == 85.0
    assert resolve_defaults({}, {}).focal_length_mm == 35.0


def test_legacy_top_level_units_key_wins():
    raw = {"units_per_meter": 50, "defaults": {"units_per_meter": 200}}
    assert defaults_from_settings(raw).units_per_meter == 50.0


def test_build_script_embeds_emit_options():
    scene = Scene(walls=[Wall(id="w", points=[Vec3(0, 0, 0), Vec3(2, 0, 0)])])
    script = build_script(
        scene, Defaults(wall_height_cm=300.0, ue_content_path="/Game/Custom", frame_rate=30.0)
    )
    assert "WALL_HEIGHT_CM = 300.0" in script
    assert "UE_CONTENT_PATH = '/Game/Custom'" in script
    assert '"fps": 30.0' in script


def test_mannequin_path_overrides_are_embedded():
    script = build_script(Scene(), Defaults(manny_paths=["/Game/My/Hero.Hero"]))
    assert "/Game/My/Hero.Hero" in script
    assert "SKM_Quinn" in script  # quinn untouched -> built-in candidates remain


def test_parse_time_options_shape_the_scene():
    scene = parse_file(SAMPLE, camera_height_m=2.0, focal_length_mm=50.0)
    kf = scene.cameras[0].keyframes[0]
    assert kf.location.z == 2.0
    assert kf.focal_length_mm == 50.0
