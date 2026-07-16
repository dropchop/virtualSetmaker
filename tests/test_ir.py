import json
import os

from virtualsetmaker.ir import Camera, CameraKeyframe, Scene, Vec3

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "examples", "example_scene.json")


def test_json_round_trip_preserves_scene():
    with open(EXAMPLE, encoding="utf-8") as fh:
        text = fh.read()
    scene = Scene.from_json(text)
    again = Scene.from_json(scene.to_json())
    assert again.to_dict() == scene.to_dict()


def test_example_scene_is_valid():
    with open(EXAMPLE, encoding="utf-8") as fh:
        scene = Scene.from_json(fh.read())
    assert scene.validate() == []
    assert len(scene.actors) == 2
    assert scene.cameras[0].is_animated


def test_validate_flags_unknown_camera_reference():
    scene = Scene.from_dict(
        {
            "shots": [{"id": "s", "name": "s", "camera_id": "ghost", "start_s": 0, "end_s": 1}],
        }
    )
    problems = scene.validate()
    assert any("unknown camera" in p for p in problems)


def test_validate_flags_duplicate_ids():
    scene = Scene(
        actors=[],
        cameras=[
            Camera(id="dup", name="a", keyframes=[CameraKeyframe(0.0, Vec3())]),
            Camera(id="dup", name="b", keyframes=[CameraKeyframe(0.0, Vec3())]),
        ],
    )
    assert any("duplicate" in p for p in scene.validate())


def test_validate_flags_out_of_order_keyframes():
    scene = Scene(
        duration_s=10.0,
        cameras=[
            Camera(
                id="c",
                name="c",
                keyframes=[CameraKeyframe(5.0, Vec3()), CameraKeyframe(1.0, Vec3())],
            )
        ],
    )
    assert any("time-ordered" in p for p in scene.validate())
