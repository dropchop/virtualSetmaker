import json
import os

from virtualsetmaker.emit import build_script
from virtualsetmaker.ir import Scene

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "examples", "example_scene.json")


def _example_scene():
    with open(EXAMPLE, encoding="utf-8") as fh:
        return Scene.from_json(fh.read())


def test_generated_script_is_syntactically_valid_python():
    script = build_script(_example_scene())
    compile(script, "<generated>", "exec")  # raises SyntaxError if malformed


def test_generated_script_uses_modern_unreal_api():
    script = build_script(_example_scene())
    assert "EditorLevelLibrary" not in script  # no deprecated API
    for expected in (
        "add_spawnable_from_instance",
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
    payload = json.loads(script.split("SCENE = ", 1)[1].split("\n\n", 1)[0])
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
    assert "MovieSceneFloatTrack" not in script
