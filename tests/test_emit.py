import json
import os

import pytest

from virtualsetmaker.emit import build_script
from virtualsetmaker.ir import Scene

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "examples", "example_scene.json")


def _example_scene():
    with open(EXAMPLE, encoding="utf-8") as fh:
        return Scene.from_json(fh.read())


def _embedded_payload(script):
    return json.loads(script.split('SCENE = json.loads(r"""', 1)[1].split('"""', 1)[0])


def test_generated_script_is_syntactically_valid_python():
    script = build_script(_example_scene())
    compile(script, "<generated>", "exec")  # raises SyntaxError if malformed


def test_generated_script_executes_up_to_the_editor_guard():
    # Outside Unreal the script must parse its embedded payload and then exit
    # with the friendly SystemExit — executing (not just compiling) the
    # top-level catches non-Python artifacts in the payload, e.g. the JSON
    # false/true/null that a compile check cannot see (NameError in UE 5.8).
    script = build_script(_example_scene())
    with pytest.raises(SystemExit):
        exec(compile(script, "<generated>", "exec"), {"__name__": "__main__"})


def test_generated_script_uses_modern_unreal_api():
    script = build_script(_example_scene())
    assert "EditorLevelLibrary" not in script  # no deprecated API
    # Spawnables must go through the subsystem (UE 5.6+ deprecated the
    # MovieSceneSequence method; the subsystem form is current in 5.8).
    assert "seq.add_spawnable_from_instance(" not in script
    # Rotators must be built with keywords: the Python ctor order is
    # (roll, pitch, yaw), not C++'s (pitch, yaw, roll).
    assert "unreal.Rotator(roll=" in script
    for expected in (
        "LevelSequenceEditorSubsystem",
        "open_level_sequence",
        "add_spawnable_from_instance(seq, actor)",
        "MovieScene3DTransformTrack",
        "MovieSceneCameraCutTrack",
        "get_cine_camera_component",
        "set_camera_binding_id",
        "current_focal_length",
    ):
        assert expected in script, expected


def test_animated_camera_emits_focal_length_track():
    script = build_script(_example_scene())  # example has a 35->50mm push-in
    assert "MovieSceneFloatTrack" in script
    assert "CurrentFocalLength" in script


def test_embedded_scene_payload_matches_ir_counts():
    scene = _example_scene()
    script = build_script(scene)
    payload = _embedded_payload(script)
    assert len(payload["actors"]) == len(scene.actors)
    assert len(payload["cameras"]) == len(scene.cameras)
    # closed=false wall of 4 points -> 3 segments
    assert len(payload["wall_segments"]) == 3


def test_static_scene_has_no_focal_track():
    scene = Scene.from_dict(
        {
            "cameras": [
                {
                    "id": "c",
                    "name": "c",
                    "keyframes": [
                        {"time_s": 0.0, "location": {"x": 0, "y": 0, "z": 1.5}, "focal_length_mm": 35.0}
                    ],
                }
            ],
            "shots": [{"id": "s", "name": "s", "camera_id": "c", "start_s": 0, "end_s": 2}],
            "duration_s": 2.0,
        }
    )
    script = build_script(scene)
    compile(script, "<generated>", "exec")
    # The focal-animation branch exists in the runtime template but must be
    # switched off in the embedded data for a constant-focal camera.
    payload = _embedded_payload(script)
    assert payload["cameras"][0]["focal_animated"] is False
