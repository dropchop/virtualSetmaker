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
    # UE 5.8: MovieSceneBindingProxy dropped get_binding_id(); the camera-cut
    # binding ID must come from the sequence helper instead.
    assert ".get_binding_id()" not in script
    # UE 5.8: ARFilter.ClassPaths is not editor-settable on an instance; it
    # must be passed to the constructor, not via set_editor_property.
    assert 'set_editor_property("class_paths"' not in script
    for expected in (
        "LevelSequenceEditorSubsystem",
        "open_level_sequence",
        "add_spawnable_from_instance(seq, actor)",
        "MovieScene3DTransformTrack",
        "MovieSceneCameraCutTrack",
        "get_cine_camera_component",
        "set_camera_binding_id",
        "MovieSceneSequenceExtensions.make_binding_id(",
        "unreal.ARFilter(",
        "current_focal_length",
    ):
        assert expected in script, expected


def test_animated_camera_emits_focal_length_track():
    script = build_script(_example_scene())  # example has a 35->50mm push-in
    assert "MovieSceneFloatTrack" in script
    assert "CurrentFocalLength" in script


def test_camera_keys_use_tick_resolution_time_unit():
    # _secs_to_frame yields TICK-resolution frames, but add_key defaults its
    # time_unit to DISPLAY_RATE. Without an explicit TICK_RESOLUTION the second
    # key of a moving camera lands hundreds of frames past the section and the
    # move never plays -- so every channel add_key must go through _key().
    script = build_script(_example_scene())
    assert "MovieSceneTimeUnit.TICK_RESOLUTION" in script
    # UE 5.4 renamed SequenceTimeUnit -> MovieSceneTimeUnit and removed the old
    # name: emitting it raises AttributeError on 5.8 and aborts the build.
    assert "SequenceTimeUnit" not in script
    # No channel may call add_key without the explicit tick-resolution unit.
    assert "chans[0].add_key(" not in script
    assert "fchan.add_key(" not in script


def test_camera_reuses_auto_created_transform_track():
    # add_spawnable_from_instance goes through the open Sequencer, which may
    # auto-create a transform track per the editor's default-tracks setting.
    # Keying a second transform track makes Sequencer blend the two absolute
    # transforms: a moving camera travels half the distance and ends between
    # its keyed pose and the spawn pose. The runtime must reuse the existing
    # track (wiping its sections) rather than always adding a fresh one.
    script = build_script(_example_scene())
    assert "find_tracks_by_exact_type(unreal.MovieScene3DTransformTrack)" in script
    assert "track.remove_section(" in script


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


def test_generated_script_reports_spawn_failures_instead_of_dying():
    script = build_script(_example_scene())
    # Every spawn goes through the guarded helper: a None/raising spawn is
    # logged and skipped, never allowed to abort the rest of the build.
    assert "VSM: could not spawn" in script
    assert "_FAILURES" in script
    # The end-of-run summary reports what actually spawned vs what the scene
    # data contains, and calls out a scene with no props at all.
    assert "spawned %d/%d actors" in script
    assert "contains NO props" in script


def test_camera_filmback_is_applied_from_sensor_data():
    script = build_script(_example_scene())
    # Sensor size is set on the CineCamera filmback before binding (the
    # template snapshot), alongside the focal length.
    assert 'comp.get_editor_property("filmback")' in script
    assert '"sensor_width"' in script
    assert '"sensor_height"' in script
    payload = _embedded_payload(script)
    assert payload["cameras"][0]["sensor"] == [36.0, 24.0]


def test_actor_colors_reach_the_capsule_tint():
    scene = Scene.from_dict(
        {
            "actors": [
                {"id": "a", "name": "a", "location": {"x": 0, "y": 0, "z": 0},
                 "color_rgb": [252, 131, 123]},
                {"id": "b", "name": "b", "location": {"x": 1, "y": 0, "z": 0},
                 "color": "Blue"},
                {"id": "c", "name": "c", "location": {"x": 2, "y": 0, "z": 0}},
            ]
        }
    )
    script = build_script(scene)
    assert "_tint(actor" in script
    assert "BASIC_SHAPE_MATERIAL" in script
    payload = _embedded_payload(script)
    rgbs = [a["rgb"] for a in payload["actors"]]
    assert rgbs[0] == [round(252 / 255, 4), round(131 / 255, 4), round(123 / 255, 4)]
    assert rgbs[1] == [round(148 / 255, 4), round(184 / 255, 4), round(255 / 255, 4)]
    assert rgbs[2] is None  # no color info: left untinted


def test_actor_color_rgb_survives_ir_json_roundtrip():
    scene = Scene.from_dict(
        {"actors": [{"id": "a", "name": "a", "location": {"x": 0, "y": 0, "z": 0},
                     "color_rgb": [1, 2, 3]}]}
    )
    again = Scene.from_json(scene.to_json())
    assert again.actors[0].color_rgb == [1, 2, 3]
    # ...and absence stays absence.
    bare = Scene.from_json(Scene.from_dict(
        {"actors": [{"id": "a", "name": "a", "location": {"x": 0, "y": 0, "z": 0}}]}
    ).to_json())
    assert bare.actors[0].color_rgb is None


def test_actors_carry_the_female_flag_for_manny_vs_quinn():
    script = build_script(_example_scene())
    # The runtime picks SKM_Quinn for female (Type B) characters and SKM_Manny
    # otherwise, with a -90 yaw offset because mannequin meshes face +Y.
    assert "MANNY_CANDIDATES" in script
    assert "QUINN_CANDIDATES" in script
    assert "MANNEQUIN_YAW_OFFSET = -90.0" in script
    assert 'quinn if a["female"] else manny' in script
    # And the missing-content case tells the user how to add the pack.
    assert "Add Feature or Content Pack" in script


def test_runtime_auto_installs_mannequins_from_engine_templates():
    script = build_script(_example_scene())
    # Projects without any skeletal mesh (Film/Video "virtual production",
    # Blank) get the mannequins copied in from the engine install's Templates/
    # folder, then the search reruns. Copy must never overwrite project files.
    assert "def _install_mannequin_pack" in script
    assert "unreal.Paths.root_dir()" in script
    assert 'os.path.join(root, "Templates")' in script
    assert "if manny is None and _install_mannequin_pack():" in script
    assert "scan_paths_synchronous" in script
    assert "if not os.path.exists(target):" in script
