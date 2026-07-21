"""Parametric blockout recipes for Shot Designer props.

Each recipe is a list of primitive parts with real-world dimensions, so a CHAIR
becomes a seat + backrest + four legs rather than an anonymous cube. Recipes are
keyed by Shot Designer's ``<objectKey>`` where known (SOFA, DOOROPEN, ...) and
matched by substring otherwise, so unseen key variants (``COUCHMODERN``,
``TABLESMALL``) still land on a sensible shape. Anything unmatched falls back to
a generic cube, and the CLI reports the key so the library can grow.

Part frame (before the prop's own rotation is applied):
* +X = width (right), +Y = depth (toward the prop's front), +Z = up
* ``offset`` is the part's center in cm relative to the prop origin on the floor
* ``size`` is [x, y, z] extent in cm (basic-shape meshes are 100 cm, so the
  emitted actor scale is size/100)
* ``rot`` is an optional [pitch, yaw, roll] in degrees (e.g. pitched cylinders
  for car wheels)
"""

from __future__ import annotations

import math
from typing import Optional

CUBE = "cube"
CYL = "cylinder"
SPHERE = "sphere"


def _p(shape: str, offset, size, rot=(0.0, 0.0, 0.0)) -> dict:
    return {"shape": shape, "offset": list(offset), "size": list(size), "rot": list(rot)}


# ---------------------------------------------------------------------------
# Recipes (dimensions in cm, ordinary real-world furniture sizes)
# ---------------------------------------------------------------------------

RECIPES: dict[str, list[dict]] = {
    "SOFA": [
        _p(CUBE, (0, 0, 22.5), (130, 80, 45)),           # seat (top at 45, real sofas 43-45)
        _p(CUBE, (-77.5, 0, 30), (25, 80, 60)),          # left arm
        _p(CUBE, (77.5, 0, 30), (25, 80, 60)),           # right arm
        _p(CUBE, (0, -27.5, 65), (180, 25, 50)),         # backrest
    ],
    # Club armchair, 90w x 85d x 90h (typical 85-95 cm cube-ish silhouette);
    # backrest kept flush with the arms instead of overhanging them.
    "ARMCHAIR": [
        _p(CUBE, (0, 5, 22.5), (54, 75, 45)),            # seat
        _p(CUBE, (-36, 5, 30), (18, 75, 60)),            # left arm
        _p(CUBE, (36, 5, 30), (18, 75, 60)),             # right arm
        _p(CUBE, (0, -37.5, 45), (90, 10, 90)),          # backrest
    ],
    "CHAIR": [
        _p(CUBE, (0, 0, 42), (45, 45, 8)),               # seat
        _p(CUBE, (0, -18.5, 68.5), (45, 8, 45)),         # back
        _p(CYL, (-18, -18, 21), (5, 5, 42)),
        _p(CYL, (18, -18, 21), (5, 5, 42)),
        _p(CYL, (-18, 18, 21), (5, 5, 42)),
        _p(CYL, (18, 18, 21), (5, 5, 42)),
    ],
    "STOOL": [
        _p(CYL, (0, 0, 60), (35, 35, 8)),
        _p(CYL, (0, 0, 28), (6, 6, 56)),
        _p(CYL, (0, 0, 2), (35, 35, 4)),
    ],
    "BENCH": [
        _p(CUBE, (0, 0, 40), (150, 40, 10)),             # seat slab
        _p(CUBE, (-65, 0, 17.5), (10, 36, 35)),          # leg panels
        _p(CUBE, (65, 0, 17.5), (10, 36, 35)),
    ],
    "TABLE": [
        _p(CUBE, (0, 0, 73), (140, 80, 6)),              # top
        _p(CYL, (-62, -32, 35), (6, 6, 70)),
        _p(CYL, (62, -32, 35), (6, 6, 70)),
        _p(CYL, (-62, 32, 35), (6, 6, 70)),
        _p(CYL, (62, 32, 35), (6, 6, 70)),
    ],
    "TABLEROUND": [
        _p(CYL, (0, 0, 73), (120, 120, 6)),
        _p(CYL, (0, 0, 35), (15, 15, 70)),
        _p(CYL, (0, 0, 2), (50, 50, 4)),
    ],
    "COFFEETABLE": [
        _p(CUBE, (0, 0, 38), (110, 60, 4)),
        _p(CYL, (-48, -23, 18), (5, 5, 36)),
        _p(CYL, (48, -23, 18), (5, 5, 36)),
        _p(CYL, (-48, 23, 18), (5, 5, 36)),
        _p(CYL, (48, 23, 18), (5, 5, 36)),
    ],
    "DESK": [
        _p(CUBE, (0, 0, 72.5), (140, 70, 5)),
        _p(CUBE, (-65, 0, 35), (5, 65, 70)),
        _p(CUBE, (65, 0, 35), (5, 65, 70)),
    ],
    "BED": [
        _p(CUBE, (0, 0, 17.5), (160, 200, 35)),          # base
        _p(CUBE, (0, 0, 45), (150, 190, 20)),            # mattress
        _p(CUBE, (0, -97.5, 45), (160, 10, 90)),         # headboard
    ],
    "BEDSINGLE": [
        _p(CUBE, (0, 0, 17.5), (90, 200, 35)),
        _p(CUBE, (0, 0, 45), (80, 190, 20)),
        _p(CUBE, (0, -97.5, 45), (90, 10, 90)),
    ],
    "DOOR": [
        _p(CUBE, (-50, 0, 105), (10, 10, 210)),          # jamb
        _p(CUBE, (50, 0, 105), (10, 10, 210)),           # jamb
        _p(CUBE, (0, 0, 215), (110, 10, 10)),            # header
        _p(CUBE, (0, 0, 102.5), (90, 5, 205)),           # closed panel
    ],
    "DOOROPEN": [
        _p(CUBE, (-50, 0, 105), (10, 10, 210)),
        _p(CUBE, (50, 0, 105), (10, 10, 210)),
        _p(CUBE, (0, 0, 215), (110, 10, 10)),
        _p(CUBE, (-45, 45, 102.5), (5, 90, 205)),        # panel swung open 90°
    ],
    "DOORDOUBLECLOSED": [
        _p(CUBE, (-95, 0, 105), (10, 10, 210)),
        _p(CUBE, (95, 0, 105), (10, 10, 210)),
        _p(CUBE, (0, 0, 215), (200, 10, 10)),
        _p(CUBE, (-45, 0, 102.5), (90, 5, 205)),
        _p(CUBE, (45, 0, 102.5), (90, 5, 205)),
    ],
    "DOORDOUBLEOPEN": [
        _p(CUBE, (-95, 0, 105), (10, 10, 210)),
        _p(CUBE, (95, 0, 105), (10, 10, 210)),
        _p(CUBE, (0, 0, 215), (200, 10, 10)),
        _p(CUBE, (-90, 45, 102.5), (5, 90, 205)),        # both panels swung 90°
        _p(CUBE, (90, 45, 102.5), (5, 90, 205)),
    ],
    "OPENING": [
        _p(CUBE, (-80, 0, 105), (10, 10, 210)),          # bare gap: jambs + header
        _p(CUBE, (80, 0, 105), (10, 10, 210)),
        _p(CUBE, (0, 0, 215), (170, 10, 10)),
    ],
    # 13 bars on 20 cm recipe centers: after the 155.9 native-width squeeze a
    # full-width run lands ~12.5 cm on center, matching real detention bars
    # (4-6" on center). The old 7 bars read as ~25 cm gaps a person fits through.
    "PRISONBARS": [
        _p(CUBE, (0, 0, 227), (250, 6, 6)),              # top rail
        _p(CUBE, (0, 0, 3), (250, 6, 6)),                # bottom rail
    ] + [_p(CYL, (x, 0, 115), (5, 5, 224)) for x in range(-120, 121, 20)],
    "IMAGEPROP": [_p(CUBE, (0, 0, 1), (200, 200, 2))],   # arbitrary user image footprint
    "WINDOW": [
        _p(CUBE, (-56, 0, 150), (8, 8, 120)),
        _p(CUBE, (56, 0, 150), (8, 8, 120)),
        _p(CUBE, (0, 0, 215), (120, 8, 10)),
        _p(CUBE, (0, 0, 85), (120, 8, 10)),
    ],
    "TV": [
        _p(CUBE, (0, 0, 110), (120, 8, 70)),             # screen
        _p(CUBE, (0, 0, 92.5), (10, 10, 35)),            # column
        _p(CUBE, (0, 0, 72.5), (40, 30, 5)),             # foot
    ],
    "FLOORLAMP": [
        _p(CYL, (0, 0, 2), (40, 40, 4)),
        _p(CYL, (0, 0, 77), (4, 4, 150)),
        _p(CYL, (0, 0, 167), (35, 35, 30)),
    ],
    "PLANT": [
        _p(CYL, (0, 0, 20), (40, 40, 40)),               # pot
        _p(CYL, (0, 0, 70), (8, 8, 60)),                 # trunk
        _p(SPHERE, (0, 0, 120), (80, 80, 100)),          # foliage
    ],
    "BOOKCASE": [
        _p(CUBE, (-43.5, 0, 90), (3, 30, 180)),          # side panels
        _p(CUBE, (43.5, 0, 90), (3, 30, 180)),
        _p(CUBE, (0, -13.5, 90), (90, 3, 180)),          # back panel
        _p(CUBE, (0, 1.5, 2), (84, 27, 4)),              # shelves
        _p(CUBE, (0, 1.5, 46), (84, 27, 4)),
        _p(CUBE, (0, 1.5, 90), (84, 27, 4)),
        _p(CUBE, (0, 1.5, 134), (84, 27, 4)),
        _p(CUBE, (0, 1.5, 178), (84, 27, 4)),
    ],
    # Kitchen base cabinet: US standard 36" (92 cm) counter height with a
    # toe kick and a slightly overhanging countertop slab.
    "COUNTER": [
        _p(CUBE, (0, -2.5, 5), (94, 55, 10)),            # toe kick
        _p(CUBE, (0, -1.5, 49), (100, 57, 78)),          # base cabinet
        _p(CUBE, (0, 0, 90), (100, 60, 4)),              # countertop (top 92)
    ],
    "DRESSER": [
        _p(CUBE, (0, -1.5, 38.5), (120, 47, 77)),        # carcass
        _p(CUBE, (0, -1.5, 78.5), (120, 47, 3)),         # top (80 total)
        _p(CUBE, (0, 23.5, 14), (110, 3, 18)),           # drawer faces
        _p(CUBE, (0, 23.5, 38), (110, 3, 18)),
        _p(CUBE, (0, 23.5, 62), (110, 3, 18)),
    ],
    "NIGHTSTAND": [_p(CUBE, (0, 0, 27.5), (45, 40, 55))],
    "WARDROBE": [
        _p(CUBE, (0, -1.5, 5), (116, 53, 10)),           # plinth
        _p(CUBE, (0, -1.5, 102.5), (120, 57, 185)),      # carcass
        _p(CUBE, (-29.5, 28.5, 105), (57, 3, 180)),      # door slabs
        _p(CUBE, (29.5, 28.5, 105), (57, 3, 180)),
        _p(CUBE, (0, 0, 197.5), (120, 60, 5)),           # crown (200 total)
    ],
    # French-door fridge: US full-size is ~91 wide x 91 deep x 178 high
    # (the old 70x70 read as a slim euro larder, half a fridge too small).
    "FRIDGE": [
        _p(CUBE, (0, -3.5, 89), (91, 84, 178)),          # cabinet
        _p(CUBE, (-22.75, 42, 122), (44, 7, 108)),       # french doors
        _p(CUBE, (22.75, 42, 122), (44, 7, 108)),
        _p(CUBE, (0, 42, 40), (89, 7, 70)),              # freezer drawer
    ],
    # US 30" range: 76w x 66d x 91h cooktop plus a low control backguard.
    "STOVE": [
        _p(CUBE, (0, 0, 44), (76, 64, 88)),              # body
        _p(CUBE, (0, 0, 89.5), (76, 64, 3)),             # cooktop (91 total)
        _p(CUBE, (0, 33, 60), (70, 2, 50)),              # oven door face
        _p(CUBE, (0, -30.5, 98.5), (76, 3, 15)),         # control backguard
    ],
    # Two-piece toilet, 38w x 70d x 76h tank top, 43 seat height.
    "TOILET": [
        _p(CUBE, (0, -25, 56), (38, 20, 40)),            # tank
        _p(CYL, (0, 10, 20), (36, 50, 40)),              # bowl
        _p(CUBE, (0, 8, 41.5), (38, 46, 3)),             # seat
    ],
    "SINK": [
        _p(CYL, (0, 0, 40), (15, 15, 80)),
        _p(CYL, (0, 0, 87.5), (50, 50, 15)),
    ],
    "BATHTUB": [
        _p(CUBE, (0, 0, 25), (170, 75, 50)),             # shell
        _p(CUBE, (-80, 0, 52.5), (10, 75, 5)),           # rim lips imply the basin
        _p(CUBE, (80, 0, 52.5), (10, 75, 5)),
        _p(CUBE, (0, -32.5, 52.5), (150, 10, 5)),
        _p(CUBE, (0, 32.5, 52.5), (150, 10, 5)),
    ],
    "RUG": [_p(CUBE, (0, 0, 1), (200, 140, 2))],
    "CAR": [
        _p(CUBE, (0, 0, 62.5), (180, 450, 60)),          # body
        _p(CUBE, (0, 15, 118), (165, 230, 55)),          # cabin (roof ~145, sedan height)
        _p(CYL, (-80, -140, 32.5), (65, 65, 20), rot=(90, 0, 0)),
        _p(CYL, (80, -140, 32.5), (65, 65, 20), rot=(90, 0, 0)),
        _p(CYL, (-80, 140, 32.5), (65, 65, 20), rot=(90, 0, 0)),
        _p(CYL, (80, 140, 32.5), (65, 65, 20), rot=(90, 0, 0)),
    ],
    # --- Shot Designer props palette ------------------------------------
    "TABLESQUARE": [
        _p(CUBE, (0, 0, 73), (90, 90, 6)),
        _p(CYL, (-38, -38, 35), (6, 6, 70)),
        _p(CYL, (38, -38, 35), (6, 6, 70)),
        _p(CYL, (-38, 38, 35), (6, 6, 70)),
        _p(CYL, (38, 38, 35), (6, 6, 70)),
    ],
    "TABLEOVAL": [
        _p(CYL, (0, 0, 73), (180, 100, 6)),              # oval = stretched cylinder
        _p(CYL, (-55, 0, 35), (14, 14, 70)),
        _p(CYL, (55, 0, 35), (14, 14, 70)),
    ],
    # Small/hand props sit at tabletop height (~75 cm) since that's where they
    # almost always live in a blocking diagram.
    "PAPER": [_p(CUBE, (0, 0, 75.5), (21, 30, 1))],
    "CELLPHONE": [_p(CUBE, (0, 0, 76), (7, 15, 2))],
    "LAPTOP": [
        _p(CUBE, (0, 0, 76), (32, 24, 2)),               # base
        _p(CUBE, (0, -11, 87), (32, 2, 22)),             # screen
    ],
    "KEYBOARD": [_p(CUBE, (0, 0, 76.5), (45, 15, 3))],
    "MONITOR": [
        _p(CUBE, (0, 0, 76.5), (22, 18, 3)),             # foot
        _p(CUBE, (0, -2, 84), (6, 6, 12)),               # column
        _p(CUBE, (0, -3, 101), (55, 4, 33)),             # screen
    ],
    "PLATE": [_p(CYL, (0, 0, 76.5), (26, 26, 3))],
    "CUP": [_p(CYL, (0, 0, 80), (9, 9, 10))],
    "GUN": [_p(CUBE, (0, 0, 76), (4, 18, 14))],
    "RIFLE": [_p(CUBE, (0, 0, 77), (6, 110, 8))],
    "DOG": [
        _p(CUBE, (0, 0, 45), (30, 70, 35)),              # body
        _p(CUBE, (0, 42, 65), (22, 25, 25)),             # head
        _p(CUBE, (0, 57, 58), (10, 12, 10)),             # snout
        _p(CYL, (-10, -25, 14), (6, 6, 28)),             # legs
        _p(CYL, (10, -25, 14), (6, 6, 28)),
        _p(CYL, (-10, 25, 14), (6, 6, 28)),
        _p(CYL, (10, 25, 14), (6, 6, 28)),
    ],
    "BUSH": [_p(SPHERE, (0, 0, 45), (120, 120, 90))],
    "TREE": [
        _p(CYL, (0, 0, 125), (35, 35, 250)),             # trunk
        _p(SPHERE, (0, 0, 375), (350, 350, 300)),        # canopy
    ],
    # --- vehicles ---------------------------------------------------------
    # Cargo/passenger van (Sprinter-class): high roof ~245 cm, short hood.
    "MINIBUS": [
        _p(CUBE, (0, -25, 142.5), (200, 430, 195)),      # box body
        _p(CUBE, (0, 210, 100), (190, 60, 110)),         # hood/nose
        _p(CUBE, (0, 187, 190), (185, 8, 85), rot=(-24, 0, 0)),  # windshield
        _p(CYL, (-85, -160, 35), (70, 70, 20), rot=(90, 0, 0)),
        _p(CYL, (85, -160, 35), (70, 70, 20), rot=(90, 0, 0)),
        _p(CYL, (-85, 165, 35), (70, 70, 20), rot=(90, 0, 0)),
        _p(CYL, (85, 165, 35), (70, 70, 20), rot=(90, 0, 0)),
    ],
    "SEMITRUCK": [
        _p(CUBE, (0, -80, 65), (250, 440, 70)),          # chassis
        _p(CUBE, (0, 160, 222.5), (240, 260, 315)),      # cab (roof ~380, real conventional)
        _p(CYL, (-105, 190, 50), (100, 100, 30), rot=(90, 0, 0)),
        _p(CYL, (105, 190, 50), (100, 100, 30), rot=(90, 0, 0)),
        _p(CYL, (-105, -180, 50), (100, 100, 30), rot=(90, 0, 0)),
        _p(CYL, (105, -180, 50), (100, 100, 30), rot=(90, 0, 0)),
    ],
    "TRUCKTRAILER": [
        _p(CUBE, (0, 0, 245), (250, 1200, 330)),         # box top ~410 (US 13'6" legal max)
        _p(CYL, (-105, -420, 45), (90, 90, 30), rot=(90, 0, 0)),
        _p(CYL, (105, -420, 45), (90, 90, 30), rot=(90, 0, 0)),
        _p(CYL, (-105, -260, 45), (90, 90, 30), rot=(90, 0, 0)),
        _p(CYL, (105, -260, 45), (90, 90, 30), rot=(90, 0, 0)),
    ],
    "MOTORCYCLE": [
        _p(CUBE, (0, 0, 70), (30, 180, 40)),             # body/tank/seat
        _p(CYL, (0, 78, 32.5), (65, 65, 12), rot=(90, 0, 0)),
        _p(CYL, (0, -78, 32.5), (65, 65, 12), rot=(90, 0, 0)),
        _p(CUBE, (0, 62, 105), (60, 5, 5)),              # handlebar
    ],
    "TANK": [
        _p(CUBE, (0, 0, 90), (350, 680, 120)),           # hull
        _p(CUBE, (0, -30, 190), (200, 250, 80)),         # turret
        _p(CYL, (0, 260, 190), (25, 25, 380), rot=(0, 0, 90)),  # barrel (axis +Y)
    ],
    # Cessna-class: HIGH wing over the cabin (the old mid-set wing read as a
    # low-wing type), plus a horizontal tailplane.
    "PLANESMALL": [
        _p(CYL, (0, 0, 150), (100, 100, 700), rot=(0, 0, 90)),  # fuselage
        _p(CUBE, (0, 30, 205), (1000, 150, 12)),         # high wing
        _p(CUBE, (0, -320, 215), (12, 100, 120)),        # tail fin
        _p(CUBE, (0, -320, 160), (340, 90, 10)),         # tailplane
    ],
    "FIGHTERJET": [
        _p(CYL, (0, 0, 180), (110, 110, 1500), rot=(0, 0, 90)),
        _p(CUBE, (0, -150, 180), (900, 320, 15)),
        _p(CUBE, (0, -620, 280), (15, 220, 160)),
        _p(SPHERE, (0, 300, 235), (70, 200, 50)),        # canopy bubble
    ],
    # 737-class: fin tops out ~12.5 m (old 8.75 was a bizjet tail), underslung
    # engines and a tailplane make the silhouette read from any angle.
    "COMMERCIALJET": [
        _p(CYL, (0, 0, 350), (400, 400, 3500), rot=(0, 0, 90)),
        _p(CUBE, (0, 0, 330), (3000, 550, 30)),
        _p(CUBE, (0, -1620, 850), (30, 450, 800)),       # tail fin
        _p(CUBE, (0, -1560, 500), (1100, 300, 25)),      # tailplane
        _p(CYL, (-700, 150, 240), (170, 170, 350), rot=(0, 0, 90)),  # engines
        _p(CYL, (700, 150, 240), (170, 170, 350), rot=(0, 0, 90)),
    ],
    # --- production equipment ---------------------------------------------
    "BOOM": [
        _p(CYL, (0, 0, 2), (45, 45, 4)),                 # base
        _p(CYL, (0, 0, 87), (5, 5, 170)),                # stand
        _p(CYL, (0, 95, 172), (4, 4, 200), rot=(0, 0, 90)),  # boom arm
        _p(CUBE, (0, 200, 172), (8, 26, 8)),             # mic
    ],
    "CRANE": [
        _p(CUBE, (0, 0, 25), (130, 190, 50)),            # base/dolly
        _p(CUBE, (0, 0, 80), (30, 30, 60)),              # pivot post
        _p(CUBE, (0, 100, 145), (22, 480, 22), rot=(-12, 0, 0)),  # jib arm, rising
        _p(CUBE, (0, -130, 110), (60, 70, 60)),          # counterweight
    ],
    "MICROPHONE": [
        _p(CYL, (0, 0, 2), (40, 40, 4)),
        _p(CYL, (0, 0, 77), (4, 4, 150)),
        _p(CUBE, (0, 6, 160), (7, 22, 7)),
    ],
    # Video village: Magliner-style cart (open shelves on posts) with two
    # monitors on top, instead of an anonymous wardrobe-sized box.
    "MONITORVILLAGE": [
        _p(CUBE, (0, 0, 27), (150, 65, 6)),              # bottom shelf
        _p(CUBE, (0, 0, 100), (150, 65, 6)),             # top shelf
        _p(CYL, (-72, -29, 51.5), (5, 5, 103)),          # posts
        _p(CYL, (72, -29, 51.5), (5, 5, 103)),
        _p(CYL, (-72, 29, 51.5), (5, 5, 103)),
        _p(CYL, (72, 29, 51.5), (5, 5, 103)),
        _p(CUBE, (-38, -5, 128), (70, 10, 45)),          # monitors
        _p(CUBE, (38, -5, 128), (70, 10, 45)),
    ],
    "EQUIPMENT": [
        _p(CUBE, (0, 0, 30), (120, 80, 60)),             # road-case stack
        _p(CUBE, (-10, 0, 72.5), (90, 70, 25)),
        _p(CUBE, (20, 5, 97.5), (60, 50, 25)),
    ],
    "ARROW": [_p(CUBE, (0, 0, 1), (30, 150, 2))],        # floor blocking marker
}

# Substring fallbacks, checked in order after an exact-key miss. Earlier rules
# win, so more specific substrings must come first (ARMCHAIR before CHAIR,
# CARPET before CAR, BUSH before BUS, VILLAGE before MONITOR).
ALIASES: list[tuple[str, str]] = [
    # seating
    ("SOFA", "SOFA"),
    ("COUCH", "SOFA"),
    ("LOVESEAT", "ARMCHAIR"),
    ("ARMCHAIR", "ARMCHAIR"),
    ("RECLINER", "ARMCHAIR"),
    ("STOOL", "STOOL"),
    ("BENCH", "BENCH"),
    ("CHAIR", "CHAIR"),
    ("SEAT", "CHAIR"),
    # tables / desks
    ("COFFEETABLE", "COFFEETABLE"),
    ("TABLEROUND", "TABLEROUND"),
    ("ROUNDTABLE", "TABLEROUND"),
    ("TABLESQUARE", "TABLESQUARE"),
    ("SQUARETABLE", "TABLESQUARE"),
    ("TABLEOVAL", "TABLEOVAL"),
    ("OVALTABLE", "TABLEOVAL"),
    ("DESK", "DESK"),
    ("TABLE", "TABLE"),
    # bedroom / storage
    ("BEDSINGLE", "BEDSINGLE"),
    ("SINGLEBED", "BEDSINGLE"),
    ("NIGHTSTAND", "NIGHTSTAND"),
    ("BEDSIDE", "NIGHTSTAND"),
    ("BED", "BED"),
    ("WARDROBE", "WARDROBE"),
    ("CLOSET", "WARDROBE"),
    ("CUPBOARD", "WARDROBE"),
    ("DRESSER", "DRESSER"),
    ("BOOK", "BOOKCASE"),
    ("SHELF", "BOOKCASE"),
    ("SHELVES", "BOOKCASE"),
    # doors / windows (double rules before single; BED rules above catch DOUBLEBED)
    # The app's real keys first: DOUBLEDOOROPEN would otherwise hit DOUBLEDOOR.
    ("DOUBLEDOOROPEN", "DOORDOUBLEOPEN"),
    ("DOUBLEDOORCLOSED", "DOORDOUBLECLOSED"),
    ("DOUBLEOPEN", "DOORDOUBLEOPEN"),
    ("OPENDOUBLE", "DOORDOUBLEOPEN"),
    ("DOORDOUBLE", "DOORDOUBLECLOSED"),
    ("DOUBLEDOOR", "DOORDOUBLECLOSED"),
    ("DOUBLE", "DOORDOUBLECLOSED"),
    ("DOOROPEN", "DOOROPEN"),
    ("DOORCLOSED", "DOOR"),
    ("DOOR", "DOOR"),
    ("OPENING", "OPENING"),
    ("PRISON", "PRISONBARS"),
    ("BARS", "PRISONBARS"),
    ("WINDOW", "WINDOW"),
    ("IMAGEPROP", "IMAGEPROP"),
    ("IMAGE", "IMAGEPROP"),
    # screens / electronics
    ("MONITORVILLAGE", "MONITORVILLAGE"),
    ("VILLAGE", "MONITORVILLAGE"),
    ("TELEVISION", "TV"),
    ("SCREEN", "TV"),
    ("TV", "TV"),
    ("MONITOR", "MONITOR"),
    ("LAPTOP", "LAPTOP"),
    ("KEYBOARD", "KEYBOARD"),
    ("BOOM", "BOOM"),                 # before PHONE: BOOMMICROPHONE contains "PHONE"
    ("MICROPHONE", "MICROPHONE"),
    ("CELLPHONE", "CELLPHONE"),
    ("PHONE", "CELLPHONE"),
    # small / hand props
    ("PAPER", "PAPER"),
    ("PLATE", "PLATE"),
    ("CUP", "CUP"),
    ("BOTTLE", "CUP"),  # the app's real objectKey for its Cup icon is BOTTLE
    ("SHOTGUN", "RIFLE"),
    ("RIFLE", "RIFLE"),
    ("GUN", "GUN"),
    # creatures & greenery
    ("DOG", "DOG"),
    ("BUSH", "BUSH"),
    ("TREE", "TREE"),
    ("PLANT", "PLANT"),
    ("LAMP", "FLOORLAMP"),
    # kitchen / bath
    ("CABINET", "COUNTER"),
    ("COUNTER", "COUNTER"),
    ("KITCHEN", "COUNTER"),
    ("FRIDGE", "FRIDGE"),
    ("REFRIG", "FRIDGE"),
    ("STOVE", "STOVE"),
    ("OVEN", "STOVE"),
    ("TOILET", "TOILET"),
    ("SINK", "SINK"),
    ("BASIN", "SINK"),
    ("BATH", "BATHTUB"),
    ("TUB", "BATHTUB"),
    ("CARPET", "RUG"),
    ("RUG", "RUG"),
    # vehicles (order: specific before generic; BUSH already matched above)
    ("TRUCKTRAILER", "TRUCKTRAILER"),
    ("TRAILER", "TRUCKTRAILER"),
    ("SEMITRUCK", "SEMITRUCK"),
    ("TRUCKSEMI", "SEMITRUCK"),
    ("SEMI", "SEMITRUCK"),
    ("TRUCK", "SEMITRUCK"),
    ("MINIBUS", "MINIBUS"),
    ("BUSMINI", "MINIBUS"),
    ("BUS", "MINIBUS"),
    ("MOTORCYCLE", "MOTORCYCLE"),
    ("MOTORBIKE", "MOTORCYCLE"),
    ("CYCLE", "MOTORCYCLE"),
    ("BIKE", "MOTORCYCLE"),
    ("TANK", "TANK"),
    ("COMMERCIALJET", "COMMERCIALJET"),
    ("JETCOMMERCIAL", "COMMERCIALJET"),
    ("COMMERCIAL", "COMMERCIALJET"),
    ("AIRLINER", "COMMERCIALJET"),
    ("FIGHTERJET", "FIGHTERJET"),
    ("JETFIGHTER", "FIGHTERJET"),
    ("FIGHTER", "FIGHTERJET"),
    ("JET", "FIGHTERJET"),
    ("AIRPLANE", "PLANESMALL"),
    ("PLANE", "PLANESMALL"),
    ("CAR", "CAR"),
    ("VEHICLE", "CAR"),
    # production equipment (BOOM and MICROPHONE match in the electronics block)
    ("CRANE", "CRANE"),
    ("MIC", "MICROPHONE"),
    ("MONITORV", "MONITORVILLAGE"),
    ("EQUIPMENT", "EQUIPMENT"),
    ("ARROW", "ARROW"),
]

# Fallback for anything unrecognized: an obvious placeholder cube.
GENERIC = [_p(CUBE, (0, 0, 50), (100, 100, 100))]

def recipe_height(parts: list[dict]) -> float:
    """Topmost extent of a recipe in cm (ignores part rotations; use
    :func:`recipe_bbox` when rotated parts matter)."""
    if not parts:
        return 0.0
    return max(p["offset"][2] + p["size"][2] / 2.0 for p in parts)


# ---------------------------------------------------------------------------
# Native icon sizes (Shot Designer size calibration)
# ---------------------------------------------------------------------------
# Shot Designer's <objectScaleX/Y> is relative to each icon's NATIVE art size
# in SD units (1 unit = 1 cm), which is undocumented and varies per icon. For
# icons whose native art is larger than our real-world recipe, multiplying the
# recipe by objectScale alone emits the prop too small. With a native span
# recorded here, the emitted world footprint becomes objectScale * native —
# exactly the icon's on-canvas span — regardless of recipe dimensions.
#
# An absent entry assumes native == recipe base span, i.e. the historical
# behavior (verified correct for SOFA at scale 1.0 and DOOROPEN at 0.7).
# Calibration procedure (character-yardstick) is documented in the README.
# A None on either axis means "leave that axis at the raw objectScale":
# used for thin run-of-wall pieces whose depth must stay true-to-life.
SD_NATIVE: dict[str, tuple[float | None, float | None]] = {
    # MEASURED from Shot Designer 1.80.8's own vector art (the installer's
    # FXG assets; the app places art 1 unit = 1 cm, verified in its code:
    # GenericObject sets fxg.scaleX = objectScaleX). Values are art bbox +
    # stroke, axes swapped into the recipe frame (recipe X = art y): anchored
    # on the sofa (art 78.9 deep vs 79.4 measured in a real scene). Doors,
    # windows and openings are wall inserts: their art includes wall stubs,
    # and their verified behavior needs no native entry.
    #
    # PRISONBARS width comes from placement evidence, not art: adjacent bar
    # icons in a real scene tile edge-to-edge with centers 155.85 units apart,
    # so the icon's on-canvas run is ~155.9. Depth is None: the 6 cm rails
    # must not be squeezed by the width correction.
    "PRISONBARS": (155.9, None),
    "TABLESQUARE": (219.5, 119.5),
    "TABLEOVAL": (216.0, 119.5),
    "TABLEROUND": (120.6, 120.6),
    "CHAIR": (66.3, 66.3),
    "SOFA": (154.8, 78.9),
    "PAPER": (48.0, 64.7),
    "CELLPHONE": (18.1, 28.6),
    "LAPTOP": (60.0, 48.2),
    "KEYBOARD": (97.1, 28.8),
    "MONITOR": (73.8, 22.0),
    "PLATE": (46.0, 46.0),
    "CUP": (19.2, 19.2),
    "DOG": (86.5, 83.2),
    "GUN": (40.8, 23.9),
    "RIFLE": (133.1, 41.3),
    "BUSH": (152.2, 152.4),
    "TREE": (412.0, 389.1),
    "CAR": (205.2, 477.5),
    "MINIBUS": (235.5, 588.6),
    "SEMITRUCK": (395.0, 1142.2),
    "TRUCKTRAILER": (390.0, 1323.1),
    "MOTORCYCLE": (139.3, 327.8),
    "TANK": (204.7, 511.7),
    "PLANESMALL": (526.3, 438.0),
    "FIGHTERJET": (504.3, 560.1),
    "COMMERCIALJET": (517.9, 617.0),
    "CRANE": (518.0, 396.9),
    "BOOM": (54.6, 199.9),
    "MONITORVILLAGE": (330.0, 250.1),
    "EQUIPMENT": (323.9, 372.3),
}


def native_span_for(recipe_name: Optional[str]) -> Optional[tuple[float | None, float | None]]:
    """Native icon (x, y) span in SD units for a recipe, or None if untracked.

    A None inside the tuple means that axis has no native correction (raw
    objectScale applies).
    """
    if recipe_name is None:
        return None
    return SD_NATIVE.get(recipe_name)


# ---------------------------------------------------------------------------
# Wall inserts (openings carved out of wall segments)
# ---------------------------------------------------------------------------
# Recipes that live *inside* a wall: the emitter snaps them onto the nearest
# parallel wall segment and splits that segment's cube so there is a real
# opening (with a lintel above, and a sill below windows) instead of a frame
# clipping through a solid wall. Values are the opening's (z_bottom, z_top) in
# cm, matching each recipe's frame: door/opening headers top out at 220
# (header center 215, 10 thick); the window glass sits between the sill
# (80-90) and the header (210-220). The opening's width along the wall is the
# recipe's X span times the prop's scale. PRISONBARS is deliberately absent:
# bars stand as their own room dividers, not inside a wall.
WALL_OPENINGS: dict[str, tuple[float, float]] = {
    "DOOR": (0.0, 220.0),
    "DOOROPEN": (0.0, 220.0),
    "DOORDOUBLECLOSED": (0.0, 220.0),
    "DOORDOUBLEOPEN": (0.0, 220.0),
    "OPENING": (0.0, 220.0),
    "WINDOW": (80.0, 220.0),
}


def recipe_bbox(
    parts: list[dict],
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Axis-aligned ``(lo, hi)`` bounding box of a recipe in cm.

    Fully rotation-aware on all three axes (same projected-OBB math as
    :func:`recipe_span`, plus the Z row) — a pitched car-wheel cylinder
    reaches the floor here just like the real model geometry will, which is
    what the model-vs-recipe bbox contract needs.
    """
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    for part in parts:
        cx, cy, cz = part["offset"]
        half = [s / 2.0 for s in part["size"]]
        pitch, yaw, roll = (math.radians(a) for a in part["rot"])
        cy_, sy_ = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        cr, sr = math.cos(roll), math.sin(roll)
        row_x = (cy_ * cp, cy_ * sp * sr - sy_ * cr, cy_ * sp * cr + sy_ * sr)
        row_y = (sy_ * cp, sy_ * sp * sr + cy_ * cr, sy_ * sp * cr - cy_ * sr)
        row_z = (-sp, cp * sr, cp * cr)
        ex = sum(abs(r) * h for r, h in zip(row_x, half))
        ey = sum(abs(r) * h for r, h in zip(row_y, half))
        ez = sum(abs(r) * h for r, h in zip(row_z, half))
        xs += [cx - ex, cx + ex]
        ys += [cy - ey, cy + ey]
        zs += [cz - ez, cz + ez]
    if not xs:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def recipe_span(parts: list[dict]) -> tuple[float, float]:
    """Axis-aligned (x, y) bounding-box span of a recipe in cm.

    Part rotations are honored in full (pitched car wheels, rolled tank
    barrels): each part's extent along a world axis is the projection of its
    oriented box, sum of |R[i][j]| * half_size[j] under the UE rotator order
    R = Rz(yaw) * Ry(pitch) * Rx(roll).
    """
    xs: list[float] = []
    ys: list[float] = []
    for part in parts:
        cx, cy, _cz = part["offset"]
        half = [s / 2.0 for s in part["size"]]
        pitch, yaw, roll = (math.radians(a) for a in part["rot"])
        cy_, sy_ = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        cr, sr = math.cos(roll), math.sin(roll)
        # Rows of Rz(yaw)·Ry(pitch)·Rx(roll) for the world X and Y axes.
        row_x = (cy_ * cp, cy_ * sp * sr - sy_ * cr, cy_ * sp * cr + sy_ * sr)
        row_y = (sy_ * cp, sy_ * sp * sr + cy_ * cr, sy_ * sp * cr - cy_ * sr)
        ex = sum(abs(r) * h for r, h in zip(row_x, half))
        ey = sum(abs(r) * h for r, h in zip(row_y, half))
        xs += [cx - ex, cx + ex]
        ys += [cy - ey, cy + ey]
    if not xs:
        return 0.0, 0.0
    return max(xs) - min(xs), max(ys) - min(ys)


# ---------------------------------------------------------------------------
# Light fixture blockouts
# ---------------------------------------------------------------------------
# Every Shot Designer light spawns placeholder rig geometry plus an actual
# Unreal light attached at the fixture's emit point. ``emit`` is the offset of
# that emit point (cm, same local frame as prop parts); ``emit: None`` means
# the item is rigging only and no light is spawned (e.g. speed rail).
# ``cls`` is the Unreal light class spawned there: flat sources read best as
# rect lights, omnidirectional lanterns as points, the sun as a directional,
# and fresnels/ellipsoidals/PARs/anything unrecognized as spotlights.

_STAND_BASE = _p(CYL, (0, 0, 2), (85, 85, 4))  # C-stand leg spread ~85 cm
_STAND_POLE = _p(CYL, (0, 0, 82), (5, 5, 160))
# Shared rig geometry (frame on two stands; softbox head; slab head; hung ball)
_FRAME_PARTS = [
    _p(CYL, (-65, 0, 60), (5, 5, 120)),
    _p(CYL, (65, 0, 60), (5, 5, 120)),
    _p(CUBE, (0, 0, 120), (120, 6, 120)),
]
_SOFTBOX_PARTS = [_STAND_BASE, _STAND_POLE, _p(CUBE, (0, 12, 165), (90, 60, 90))]
_SLAB_PARTS = [_STAND_BASE, _STAND_POLE, _p(CUBE, (0, 6, 155), (122, 10, 64))]  # Kino 4ft 4Bank
_HUNG_BALL_PARTS = [_p(CYL, (0, 0, 250), (2, 2, 60)), _p(SPHERE, (0, 0, 190), (60, 60, 60))]
# Handheld omni lamp on a pole ("Light On A Stick", objectKey HOLLYWOODLIGHT)
_STICK_FIXTURE = {
    "parts": [_p(CYL, (0, 0, 90), (4, 4, 180)), _p(CUBE, (0, 0, 190), (15, 15, 15))],
    "emit": (0, 0, 190),
    "cls": "point",
    "model": "RIG_STICK",
}

LIGHT_FIXTURES: list[tuple[str, dict]] = [
    # (substring of kind, fixture) — checked in order, first match wins, so
    # more specific substrings come first (SOFTBOX before SOFT).
    ("SUN", {"parts": [], "emit": (0, 0, 0), "cls": "directional", "model": None}),  # sky: no rig geo
    ("SPEEDRAIL", {  # rigging only, no light (cls unused)
        "parts": [
            _p(CYL, (-100, 0, 120), (5, 5, 240)),
            _p(CYL, (100, 0, 120), (5, 5, 240)),
            _p(CYL, (0, 0, 240), (5, 5, 210), rot=(90, 0, 0)),
        ],
        "emit": None,
        "cls": "spot",
        "model": "RIG_SPEEDRAIL",
    }),
    ("CHINA", {"parts": _HUNG_BALL_PARTS, "emit": (0, 0, 190), "cls": "point", "model": "RIG_HUNGBALL"}),
    ("LANTERN", {"parts": _HUNG_BALL_PARTS, "emit": (0, 0, 190), "cls": "point", "model": "RIG_HUNGBALL"}),
    ("BULB", {"parts": _HUNG_BALL_PARTS, "emit": (0, 0, 190), "cls": "point", "model": "RIG_HUNGBALL"}),
    ("BALLOON", {  # helium balloon lights run ~150-200 cm across
        "parts": [_p(CYL, (0, 0, 260), (2, 2, 80)), _p(SPHERE, (0, 0, 345), (170, 170, 170))],
        "emit": (0, 0, 345),
        "cls": "point",
        "model": "RIG_BALLOON",
    }),
    ("PRACTICAL", {  # in-scene floor lamp
        "parts": [
            _p(CYL, (0, 0, 2), (40, 40, 4)),
            _p(CYL, (0, 0, 72), (4, 4, 140)),
            _p(CYL, (0, 0, 160), (40, 40, 35)),
        ],
        "emit": (0, 0, 150),
        "cls": "point",
        "model": "RIG_PRACTICAL",
    }),
    # "Light On A Stick": the app's real objectKey is HOLLYWOODLIGHT.
    ("HOLLYWOOD", _STICK_FIXTURE),
    ("STICK", _STICK_FIXTURE),
    ("SILK", {"parts": _FRAME_PARTS, "emit": (0, 10, 120), "cls": "rect", "model": "RIG_FRAME"}),
    ("BOUNCE", {"parts": _FRAME_PARTS, "emit": (0, 10, 120), "cls": "rect", "model": "RIG_FRAME"}),
    ("FRAME", {"parts": _FRAME_PARTS, "emit": (0, 10, 120), "cls": "rect", "model": "RIG_FRAME"}),
    ("SOFTBOX", {"parts": _SOFTBOX_PARTS, "emit": (0, 45, 165), "cls": "rect", "model": "RIG_SOFTBOX"}),
    ("SOFT", {"parts": _SOFTBOX_PARTS, "emit": (0, 45, 165), "cls": "rect", "model": "RIG_SOFTBOX"}),
    ("FLO", {"parts": _SLAB_PARTS, "emit": (0, 14, 155), "cls": "rect", "model": "RIG_SLAB"}),
    ("PANEL", {"parts": _SLAB_PARTS, "emit": (0, 14, 155), "cls": "rect", "model": "RIG_SLAB"}),
    ("LED", {
        "parts": [_STAND_BASE, _STAND_POLE, _p(CUBE, (0, 6, 155), (35, 10, 35))],
        "emit": (0, 14, 155),
        "cls": "rect",
        "model": "RIG_LED",
    }),
]

# Anything else (fresnels, open face, ellipsoidal, PAR, scoop, cyc, unknown):
# a classic stand with a boxy head, spotlight at the lens.
LIGHT_FIXTURE_DEFAULT: dict = {
    "parts": [_STAND_BASE, _STAND_POLE, _p(CUBE, (0, 8, 170), (40, 35, 40))],
    "emit": (0, 28, 170),
    "cls": "spot",
    "model": "RIG_DEFAULT",
}


def fixture_for(kind: str) -> dict:
    """Return the rig-geometry fixture for a Shot Designer light kind."""
    key = (kind or "").upper()
    for needle, fixture in LIGHT_FIXTURES:
        if needle in key:
            return fixture
    return LIGHT_FIXTURE_DEFAULT


def match_kind(object_key: str) -> Optional[str]:
    """Return the recipe name for a Shot Designer objectKey, or None."""
    key = (object_key or "").upper().strip()
    if not key:
        return None
    if key in RECIPES:
        return key
    for needle, name in ALIASES:
        if needle in key:
            return name
    return None


def recipe_for(object_key: str) -> tuple[Optional[str], list[dict]]:
    """Return ``(matched_name_or_None, parts)`` — GENERIC parts on a miss."""
    name = match_kind(object_key)
    if name is None:
        return None, GENERIC
    return name, RECIPES[name]
