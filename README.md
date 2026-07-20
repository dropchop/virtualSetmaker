# virtualSetmaker

Turn **Shot Designer** (Hollywood Camera Work `.hcw`) scene files into **Unreal
Engine 5.8** scenes (compatible with 5.6+) — cameras (with moves), actors,
props, walls, and lights — via a Python script you run inside the editor.

```
Shot Designer .hcw ──parse──▶  IR (JSON)  ──emit──▶  Unreal 5.8 Python script
   (plain XML)               neutral scene           run in the editor
```

## Install

No third-party dependencies for the core pipeline (stdlib only).

```bash
pip install -e .            # provides the `vsm` command
# or run without installing:
PYTHONPATH=src python -m virtualsetmaker.cli --help
```

## Use

```bash
# Parse a Shot Designer scene and emit an Unreal script:
vsm build samples/Sceneforclaude.hcw -o scene.py

# Inspect the intermediate representation as JSON:
vsm parse samples/Sceneforclaude.hcw -o scene.json

# Emit straight from a hand-authored IR (no .hcw needed) — good for demos:
vsm emit examples/example_scene.json -o scene.py

# Just confirm a file is a Shot Designer scene:
vsm probe samples/Sceneforclaude.hcw

# List the prop blockout library:
vsm props

# Open the graphical exporter:
vsm gui        # (or run `vsm-gui`)
```

## GUI

`vsm gui` (or the `vsm-gui` command / `vsm-gui.exe`) opens a small exporter:
add one or more `.hcw` files, choose an export folder, hit **Export** — each
scene becomes `<name>_unreal.py` in that folder, with a log of object counts
and any unmatched-prop notes. Last-used folders are remembered in
`~/.virtualsetmaker.json`.

## Windows

**Standalone exe (no Python needed to run it):**

1. Get this repo onto the PC (clone or download ZIP).
2. Double-click `packaging\build_windows.bat` — one-time build; needs Python 3
   from [python.org](https://www.python.org/downloads/) with the default
   tcl/tk option. It installs PyInstaller and produces **`dist\vsm-gui.exe`**.
3. Double-click `dist\vsm-gui.exe` to use the exporter from then on.

**Or via pip:** install Python 3.9+, then `pip install .` in the repo — this
gives `vsm` (terminal) and `vsm-gui` (windowed, no console) commands.

### Running the generated script in Unreal (5.8, or any 5.6+)

1. Enable **Edit → Plugins → "Python Editor Script Plugin"** (restart once).
2. Open the **Output Log**, switch the dropdown from `Cmd` to **`Python`**.
3. Run `py "C:/path/to/scene.py"` (or paste the file path).

It spawns the actors/props/walls/lights into the current level and creates a
**Level Sequence** (`/Game/VSM/SEQ_<name>`) with the CineCamera(s), any camera
move keyframes, focal-length animation, and a camera-cut track. The sequence
is opened in Sequencer as part of the build (required by the UE 5.6+
`LevelSequenceEditorSubsystem` spawnable API) and left open for you.

## Scale & conventions

* **1 Shot Designer unit = 1 cm** (override with `--units-per-meter`).
* Shot Designer positions are screen-space (`+y` down) with angles in radians.
  Both that frame and Unreal's are left-handed, so coordinates and yaw carry
  over **unchanged** (chirality preserved — scenes and shots are never
  mirrored); the whole conversion is pinned down in one place,
  [`coords.py`](src/virtualsetmaker/coords.py).
* Actors render as the UE **Mannequin** — `SKM_Manny`, or `SKM_Quinn` for
  Shot Designer Type B (female) characters — facing where the character faces,
  with a capsule fallback (plus instructions in the Output Log for adding the
  Third Person content pack) if the meshes aren't in the project.

## Prop blockouts

Props aren't anonymous cubes: each Shot Designer `objectKey` maps to a
**parametric blockout recipe** in
[`emit/blockouts.py`](src/virtualsetmaker/emit/blockouts.py) — a chair is a seat
+ backrest + four legs, a table is a top + legs, an open door is a frame + a
swung panel, all at real-world dimensions. Run `vsm props` to see the recipes.

The library covers **the entire Shot Designer object palette** (62 recipes,
mapped from the app's palette screenshots): all furniture and tables, desk/hand
props (laptop, monitor, phone, plate, cup, paper, guns), greenery (bush, tree),
every vehicle (car, mini bus, semi truck, trailer, motorcycle, tank, small
plane, fighter jet, commercial jet), production gear (camera crane, boom mic,
microphone, monitor village, equipment), all door/window types (open, closed,
double open, double closed, medium opening, prison bars, window), and floor
arrows.

Lights spawn as **placeholder rig geometry + a real Unreal light** attached at
the fixture's emit point, grouped so they move together: fresnels/ellipsoidal/
PAR/scoop/cyc/open-face get a stand + head with a pitched **SpotLight** at the
lens; panels/FLO/softbox/silk/bounce get their slab/frame with a **RectLight**
on the face; china ball/balloon/practical/light-on-a-stick get hanging or lamp
geo with a **PointLight** inside; **Sun** spawns a **DirectionalLight** only
(position is meaningless for it, so no rig); the Virtual Speed Rail spawns
rigging geo with no light.

Matching is exact key first, then ordered substring aliases (`COUCHMODERN` →
SOFA; `BOOMMICROPHONE` → boom rig, not phone), so unseen key-name variants land
on the right shape. Unmatched kinds fall back to a labeled 1 m cube and
`vsm build` prints a note — send a `.hcw` using that prop and the recipe can be
added in a few lines. Parts spawn grouped (attached to the first part) in the
`VSM/Props` outliner folder, so each prop moves as one unit.

## Status

* **Static scenes** (placement of camera, actors, props, walls, lights): done,
  verified against a real `.hcw`.
* **Camera moves**: done. Shot Designer stores a move as numbered camera *stop
  marks* (`<stopMarks>`) linked by a `<Track>` dolly path; the parser merges
  each chain into one camera keyed at the start and end stops (position and
  look direction from the stops themselves) plus a key per intermediate track
  point so curved paths keep their bow (Unreal's AUTO tangents smooth through
  them). Timing comes from path length at the scene's camera-speed index
  (speed 3 ≈ 0.75 m/s dolly; `_DOLLY_MPS_PER_SPEED` in `parse/shotdesigner.py`).
  Verified against straight-line and curved-move samples in `samples/`.

## Changelog

### 2026-07-17

* **Actors spawn as UE Mannequins** — `SKM_Manny` for Type A characters,
  `SKM_Quinn` for Type B (the `.hcw` `<female>` flag), with the correct facing
  (mannequin meshes are authored facing +Y, so spawns apply a −90° yaw
  offset). If the project lacks the meshes, the Output Log explains how to add
  the Third Person content pack instead of silently dropping capsules.
* **Fixed mirrored scenes** — the screen→Unreal conversion previously negated
  Y, which reflected the entire scene: props appeared on the wrong side of the
  room and every through-camera shot was flipped left/right. Coordinates and
  yaw now carry over unchanged, so Unreal matches the Shot Designer plan
  exactly.
* **Calibrated prop orientation** — freestanding props store the direction of
  their *back* in the `.hcw` (a sofa placed against a wall now sits flush,
  facing the room); doors/windows snapped into a wall follow the wall's
  direction, with door panels swinging into the room.
* **Export diagnostics** — unsupported Shot Designer object types and
  multi-snapshot documents are reported at export instead of dropped silently;
  the generated script survives individual spawn failures, names them in the
  Output Log, and reports spawned-vs-expected counts per category.
* **Known issue** — prop footprints are real-world recipe dimensions ×
  `objectScale`, but some Shot Designer icons (notably tables) have native
  sizes larger than real-world furniture, so those props come out small.
  Per-icon size calibration is in progress.

### 2026-07-16

* **Camera moves** — stop marks + dolly `<Track>` chains become one keyframed
  CineCamera per move, with curve bow preserved and timing from path length at
  the scene's camera-speed index.
* **Unreal 5.8 target** (compatible 5.6+) — spawnables go through
  `LevelSequenceEditorSubsystem`.
* **Fixes** — generated-script rotations (the UE Python `Rotator` constructor
  is `(roll, pitch, yaw)`, not the C++ order), scene data embedded as JSON
  (not pasted as a Python literal), and the Windows standalone-exe build.
* **Initial release** — `.hcw` → IR → Unreal editor Python script; full prop
  palette blockout library; lights with real Unreal light types; tkinter GUI
  and Windows packaging.

## Layout

```
src/virtualsetmaker/
  ir.py                 neutral scene dataclasses (+ JSON, validation)
  coords.py             the single Shot Designer→Unreal coordinate transform
  parse/shotdesigner.py .hcw XML → IR
  parse/probe.py        format guard
  emit/unreal_python.py IR → Unreal 5.8 Python script
  emit/blockouts.py     prop + light-fixture blockout recipes
  build.py              shared build core (used by CLI and GUI)
  gui.py                tkinter exporter (vsm gui / vsm-gui)
  cli.py                the `vsm` command
packaging/              PyInstaller spec + Windows one-click build script
examples/example_scene.json   hand-authored IR with an animated push-in
samples/Sceneforclaude.hcw    real Shot Designer sample
tests/                        pytest suite (IR, coords, parser, emitter)
```

## Test

```bash
pip install -e ".[dev]"
pytest
```
