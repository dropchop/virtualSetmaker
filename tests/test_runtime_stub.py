"""End-to-end trace: exec the generated UE script against a fake ``unreal``
module and assert what actually spawns.

Covers the three Starter Content scenarios for meshed props:
(a) mesh already in the project  -> spawned, scaled from its real bounds;
(b) pack on the engine disk only -> auto-installed, then spawned;
(c) no pack anywhere             -> blockout parts spawn, guidance logged.

The stub models everything up to the Sequencer section; the script's
sequencer half needs a far larger surface, so execution is allowed to stop
there (all spawning happens before it).
"""

import json
import math
import os
import sys
import types

import pytest

from virtualsetmaker.emit import build_script
from virtualsetmaker.parse import parse_file

TABLE_SAMPLE = os.path.join(os.path.dirname(__file__), "..", "samples", "one_with_table.hcw")
pytestmark = pytest.mark.skipif(
    not os.path.exists(TABLE_SAMPLE), reason="table sample .hcw not present"
)

MESH_BBOX = ((-60.0, -50.0, 0.0), (60.0, 50.0, 80.0))  # deliberately not a cube


class _V:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)


class _Rot:
    def __init__(self, roll=0.0, pitch=0.0, yaw=0.0):
        self.roll, self.pitch, self.yaw = roll, pitch, yaw


class _Box:
    def __init__(self, lo, hi):
        self.min, self.max = _V(*lo), _V(*hi)


class _Asset:
    def __init__(self, path):
        self.path = path


class _Mesh(_Asset):
    def get_bounding_box(self):
        return _Box(*MESH_BBOX)


class _Actor:
    def __init__(self, source, loc, rot):
        self.source, self.loc, self.rot = source, loc, rot
        self.label = None
        self.scale = None

    def set_actor_label(self, s):
        self.label = s

    def set_actor_scale3d(self, v):
        self.scale = v

    def __getattr__(self, name):  # folder paths, attach, tint... all no-ops
        return lambda *a, **k: None


def _build_stub(project_content, engine_root, spawns, logs, rescans):
    """A fake `unreal` whose asset universe is the fake project's filesystem:
    /Game/StarterContent/X loads iff <project_content>/StarterContent/X.uasset
    exists — which is exactly what the install helper is supposed to create."""

    class EditorAssetLibrary:
        @staticmethod
        def load_asset(p):
            if p.startswith("/Engine/BasicShapes/") or "Mannequins" in p:
                return _Asset(p)
            if p.startswith("/Game/StarterContent/"):
                rel = p[len("/Game/"):].split(".")[0] + ".uasset"
                if os.path.isfile(os.path.join(project_content, *rel.split("/"))):
                    return _Mesh(p)
            return None

    class _ActorSub:
        def spawn_actor_from_object(self, obj, loc, rot):
            a = _Actor(obj, loc, rot)
            spawns.append(a)
            return a

        def spawn_actor_from_class(self, cls, loc, rot):
            a = _Actor(cls, loc, rot)
            spawns.append(a)
            return a

    class _Registry:
        def get_assets(self, arf):
            return []

        def scan_paths_synchronous(self, paths, **kw):
            rescans.append(list(paths))

    class AssetRegistryHelpers:
        @staticmethod
        def get_asset_registry():
            return _Registry()

        @staticmethod
        def get_asset(data):
            return _Asset(str(data))

    class Paths:
        @staticmethod
        def root_dir():
            return engine_root

        @staticmethod
        def engine_dir():
            return os.path.join(engine_root, "Engine")

        @staticmethod
        def project_content_dir():
            return project_content

        @staticmethod
        def convert_relative_path_to_full(p):
            return p

    class _Txn:
        def __init__(self, name):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class EditorActorSubsystem:
        pass

    actor_sub = _ActorSub()

    stub = types.ModuleType("unreal")
    ns = dict(
        Vector=_V,
        Rotator=_Rot,
        LinearColor=lambda *a: None,
        FrameNumber=lambda v: v,
        EditorAssetLibrary=EditorAssetLibrary,
        AssetRegistryHelpers=AssetRegistryHelpers,
        ARFilter=type("ARFilter", (), {"set_editor_property": lambda self, k, v: None}),
        TopLevelAssetPath=lambda a, b: (a, b),
        ScopedEditorTransaction=_Txn,
        Paths=Paths,
        EditorActorSubsystem=EditorActorSubsystem,
        AttachmentRule=types.SimpleNamespace(KEEP_WORLD="KEEP_WORLD"),
        get_editor_subsystem=lambda cls: actor_sub if cls is EditorActorSubsystem else object(),
        log=lambda m: logs.append(("log", str(m))),
        log_warning=lambda m: logs.append(("warn", str(m))),
        log_error=lambda m: logs.append(("error", str(m))),
    )
    for k, v in ns.items():
        setattr(stub, k, v)
    # PEP 562 module fallback: any unmodeled unreal.X becomes a dummy class,
    # so execution proceeds until something calls real behavior we don't fake
    # (the Sequencer section) — everything spawnable has spawned by then.
    stub.__getattr__ = lambda name: type(name, (), {})
    return stub


def _run(tmp_path, seed_project=False, seed_engine=False):
    project = os.path.join(str(tmp_path), "Proj", "Content")
    engine = os.path.join(str(tmp_path), "UE")
    os.makedirs(project, exist_ok=True)
    if seed_project:
        for rel in ("StarterContent/Props/SM_TableRound.uasset",
                    "StarterContent/Props/SM_Chair.uasset"):
            path = os.path.join(project, *rel.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w").close()
    if seed_engine:
        src = os.path.join(engine, "Samples", "StarterContent", "Content", "StarterContent")
        for rel in ("Props/SM_Chair.uasset", "Props/SM_TableRound.uasset",
                    "Props/Materials/M_TableRound.uasset",
                    "Materials/M_Basic_Wood.uasset", "Textures/T_Wood_D.uasset"):
            path = os.path.join(src, *rel.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w").close()

    script = build_script(parse_file(TABLE_SAMPLE))
    payload = json.loads(script.split('SCENE = json.loads(r"""', 1)[1].split('"""', 1)[0])
    spawns, logs, rescans = [], [], []
    stub = _build_stub(project, engine, spawns, logs, rescans)
    old = sys.modules.get("unreal")
    sys.modules["unreal"] = stub
    try:
        try:
            exec(compile(script, "<generated>", "exec"), {"__name__": "__main__"})
        except Exception:
            pass  # sequencer surface is not modeled; spawning is done by then
    finally:
        if old is None:
            del sys.modules["unreal"]
        else:
            sys.modules["unreal"] = old
    return payload, spawns, logs, rescans, project


def _meshed_prop(payload, name="TABLEROUND"):
    return next(p for p in payload["props"] if p["matched"] == name and "mesh" in p)


def test_mesh_spawns_scaled_from_its_real_bounds(tmp_path):
    payload, spawns, _logs, _rescans, _proj = _run(tmp_path, seed_project=True)
    prop = _meshed_prop(payload)
    m = prop["mesh"]
    actor = next(a for a in spawns if isinstance(a.source, _Mesh)
                 and a.source.path == m["asset"] and a.label == "Prop_" + prop["label"])
    lo, hi = MESH_BBOX
    for i, axis in enumerate("xyz"):
        expected = m["size"][i] / (hi[i] - lo[i])
        assert getattr(actor.scale, axis) == pytest.approx(expected), axis
    # Fake bbox is XY-centered with its bottom at z=0, so no pivot shift:
    # the actor lands exactly on the prop origin, feet on the floor.
    assert actor.loc.x == pytest.approx(m["loc"][0])
    assert actor.loc.y == pytest.approx(m["loc"][1])
    assert actor.loc.z == pytest.approx(0.0)
    assert actor.rot.yaw == pytest.approx(m["yaw"] % 360.0) or \
        actor.rot.yaw == pytest.approx(m["yaw"])
    # And no blockout parts spawned for this prop.
    assert not [a for a in spawns
                if a.label and a.label.startswith("Prop_%s_part" % prop["label"])]


def test_pack_on_engine_disk_is_auto_installed_then_spawned(tmp_path):
    payload, spawns, logs, rescans, proj = _run(tmp_path, seed_engine=True)
    prop = _meshed_prop(payload)
    # Files landed in the project (Props + Materials + Textures trees)...
    for rel in ("StarterContent/Props/SM_TableRound.uasset",
                "StarterContent/Props/Materials/M_TableRound.uasset",
                "StarterContent/Materials/M_Basic_Wood.uasset",
                "StarterContent/Textures/T_Wood_D.uasset"):
        assert os.path.isfile(os.path.join(proj, *rel.split("/"))), rel
    # ...the registry was rescanned, and the mesh actually spawned.
    assert ["/Game/StarterContent"] in rescans
    assert any(isinstance(a.source, _Mesh) and a.source.path == prop["mesh"]["asset"]
               for a in spawns)


def test_no_starter_content_anywhere_falls_back_to_blockout(tmp_path):
    payload, spawns, logs, _rescans, _proj = _run(tmp_path)
    prop = _meshed_prop(payload)
    assert not [a for a in spawns if isinstance(a.source, _Mesh)]
    # The blockout parts spawned instead (first part carries the prop label)...
    assert any(a.label == "Prop_" + prop["label"] for a in spawns)
    # ...and the log explains the UE 5.7+ situation and the manual remedy.
    assert any("Starter Content" in m and "5.7" in m
               for kind, m in logs if kind == "warn")
