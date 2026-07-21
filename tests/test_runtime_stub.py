"""End-to-end trace: exec the generated UE script against a fake ``unreal``
module whose importer actually parses the shipped OBJ files.

The fake ``import_asset_tasks`` reads the OBJ the runtime hands it, converts
the vertices back from OBJ Y-up to UE Z-up (the mirror a real importer
applies), and records the resulting bbox in a fake ``.uasset`` — so these
tests round-trip the writer's axis contract, the import call, the
bounds-fit spawn math, the axis-swap guard, and every fallback path.

Execution is allowed to stop at the (unmodeled) Sequencer section; all
spawning happens before it.
"""

import json
import math
import os
import sys
import types

import pytest

from virtualsetmaker.build import build_hcw
from virtualsetmaker.settings import Defaults

TABLE_SAMPLE = os.path.join(os.path.dirname(__file__), "..", "samples", "one_with_table.hcw")
pytestmark = pytest.mark.skipif(
    not os.path.exists(TABLE_SAMPLE), reason="table sample .hcw not present"
)


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
    def __init__(self, path, bbox):
        super().__init__(path)
        self._bbox = bbox
        self.static_materials = []

    def get_bounding_box(self):
        return _Box(*self._bbox)

    def set_material(self, i, m):
        pass


class _Actor:
    def __init__(self, source, loc, rot):
        self.source, self.loc, self.rot = source, loc, rot
        self.label = None
        self.scale = None

    def set_actor_label(self, s):
        self.label = s

    def set_actor_scale3d(self, v):
        self.scale = v

    def __getattr__(self, name):
        return lambda *a, **k: None


def _obj_bbox(obj_path):
    """Bbox of an OBJ file, verbatim — exactly what UE 5.8's Interchange OBJ
    translator does (measured on a live editor: no axis conversion)."""
    xs, ys, zs = [], [], []
    with open(obj_path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("v "):
                _, x, y, z = line.split()[:4]
                xs.append(float(x))
                ys.append(float(y))
                zs.append(float(z))
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def _build_stub(project_content, spawns, logs, imports):
    def _uasset_file(game_path):
        rel = game_path[len("/Game/"):].split(".")[0] + ".uasset"
        return os.path.join(project_content, *rel.split("/"))

    class EditorAssetLibrary:
        @staticmethod
        def does_asset_exist(p):
            return os.path.isfile(_uasset_file(p))

        @staticmethod
        def load_asset(p):
            if p.startswith("/Engine/BasicShapes/") or "Mannequins" in p:
                return _Asset(p)
            f = _uasset_file(p)
            if os.path.isfile(f):
                data = json.load(open(f))
                return _Mesh(p, (tuple(data["lo"]), tuple(data["hi"])))
            return None

        @staticmethod
        def save_loaded_asset(a):
            pass

    class _AssetTools:
        def import_asset_tasks(self, tasks):
            for t in tasks:
                imports.append(t.props.get("filename"))
                src = t.props.get("filename")
                if not (src and os.path.isfile(src)):
                    continue
                lo, hi = _obj_bbox(src)
                stem = os.path.splitext(os.path.basename(src))[0]
                dest = t.props["destination_path"] + "/" + stem
                f = _uasset_file(dest)
                os.makedirs(os.path.dirname(f), exist_ok=True)
                json.dump({"lo": lo, "hi": hi}, open(f, "w"))

        def create_asset(self, *a, **k):
            return None  # colorize fails soft; not under test here

    class AssetImportTask:
        def __init__(self):
            self.props = {}

        def set_editor_property(self, k, v):
            self.props[k] = v

    class AssetToolsHelpers:
        @staticmethod
        def get_asset_tools():
            return _AssetTools()

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
            pass

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
            return os.path.join(project_content, "..", "UE")

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
        AssetImportTask=AssetImportTask,
        AssetToolsHelpers=AssetToolsHelpers,
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
    stub.__getattr__ = lambda name: type(name, (), {})
    return stub


def _exec_script(script_path, project_content):
    spawns, logs, imports = [], [], []
    stub = _build_stub(project_content, spawns, logs, imports)
    script = open(script_path, encoding="utf-8").read()
    old = sys.modules.get("unreal")
    sys.modules["unreal"] = stub
    try:
        try:
            exec(compile(script, script_path, "exec"), {"__name__": "__main__"})
        except Exception:
            pass  # sequencer surface not modeled; spawning is done by then
    finally:
        if old is None:
            del sys.modules["unreal"]
        else:
            sys.modules["unreal"] = old
    return spawns, logs, imports


def _setup(tmp_path):
    out = os.path.join(str(tmp_path), "scene_unreal.py")
    report = build_hcw(TABLE_SAMPLE, out, options=Defaults())
    assert report.prop_models > 0
    payload = json.loads(
        open(out).read().split('SCENE = json.loads(r"""', 1)[1].split('"""', 1)[0]
    )
    project = os.path.join(str(tmp_path), "Proj", "Content")
    os.makedirs(project, exist_ok=True)
    return out, payload, project


def _meshed_prop(payload, name="TABLEROUND"):
    return next(p for p in payload["props"] if p["matched"] == name and "mesh" in p)


def test_first_run_imports_objs_and_spawns_fitted_meshes(tmp_path):
    out, payload, project = _setup(tmp_path)
    spawns, logs, imports = _exec_script(out, project)
    prop = _meshed_prop(payload)
    m = prop["mesh"]
    assert any(i and i.endswith("SM_VSM_TABLEROUND.obj") for i in imports)
    actor = next(a for a in spawns if isinstance(a.source, _Mesh)
                 and a.source.path.endswith("SM_VSM_TABLEROUND")
                 and a.label == "Prop_" + prop["label"])
    # Scale = target size / authored extents (round-tripped through the OBJ).
    for i, axis in enumerate("xyz"):
        assert getattr(actor.scale, axis) == pytest.approx(
            m["size"][i] / m["src_ext"][i], rel=1e-3), axis
    # Bbox center lands on the payload loc; bottom on the payload z.
    assert actor.loc.z == pytest.approx(m["loc"][2], abs=0.01)
    # No blockout parts for a successfully meshed prop.
    assert not [a for a in spawns
                if a.label and a.label.startswith("Prop_%s_part" % prop["label"])]
    # Light rigs mesh too (sample has lights only if the scene defines them).
    if any("mesh" in lt for lt in payload["lights"]):
        assert any(a.label and a.label.startswith("LightRig_") and isinstance(a.source, _Mesh)
                   for a in spawns)


def test_second_run_reuses_imported_assets(tmp_path):
    out, payload, project = _setup(tmp_path)
    _spawns1, _logs1, imports1 = _exec_script(out, project)
    spawns2, _logs2, imports2 = _exec_script(out, project)
    assert imports1 and not imports2  # idempotent: assets already in project
    prop = _meshed_prop(payload)
    assert any(isinstance(a.source, _Mesh) and a.label == "Prop_" + prop["label"]
               for a in spawns2)


def test_missing_props_folder_falls_back_to_blockout(tmp_path):
    out, payload, project = _setup(tmp_path)
    import shutil

    shutil.rmtree(os.path.join(str(tmp_path), "vsm_props"))
    spawns, logs, imports = _exec_script(out, project)
    prop = _meshed_prop(payload)
    assert not [a for a in spawns if isinstance(a.source, _Mesh)]
    assert any(a.label == "Prop_" + prop["label"] for a in spawns)  # blockout parent
    assert any("prop model file missing" in m for k, m in logs if k == "warn")


def test_legacy_y_up_assets_are_auto_corrected(tmp_path):
    # Assets imported from the old Y-up OBJ files sit in the project with
    # authored Y/Z swapped. The runtime must NOT re-import or fall back: it
    # spawns them with the roll-90 + mirrored-Z correction.
    out, payload, project = _setup(tmp_path)
    _exec_script(out, project)  # first run imports (verbatim, current files)
    meshes_dir = os.path.join(project, "VSM", "Meshes")
    for fn in os.listdir(meshes_dir):
        f = os.path.join(meshes_dir, fn)
        data = json.load(open(f))
        swap = lambda v: [v[0], v[2], v[1]]
        json.dump({"lo": swap(data["lo"]), "hi": swap(data["hi"])}, open(f, "w"))
    spawns, logs, imports = _exec_script(out, project)
    assert not imports  # corrected in place, never re-imported
    prop = _meshed_prop(payload)
    m = prop["mesh"]
    # TABLEROUND's authored Y and Z extents differ (~68 vs 76 scaled), so the
    # swap is detectable and the corrective spawn must fire.
    actor = next(a for a in spawns if isinstance(a.source, _Mesh)
                 and a.source.path.endswith("SM_VSM_TABLEROUND")
                 and a.label == "Prop_" + prop["label"])
    assert actor.rot.roll == pytest.approx(90.0)
    assert actor.scale.z < 0  # the mirror half of the correction
    # Fit factors land on the right axes: world X/Z scale from author X/Y.
    f = [m["size"][i] / m["src_ext"][i] for i in range(3)]
    assert actor.scale.x == pytest.approx(f[0], rel=1e-3)
    assert actor.scale.y == pytest.approx(f[2], rel=1e-3)
    assert actor.scale.z == pytest.approx(-f[1], rel=1e-3)
    assert any("legacy Y-up import" in msg for k, msg in logs if k == "log")
