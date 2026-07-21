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
        _p(CUBE, (0, 0, 20), (130, 80, 40)),            # seat
        _p(CUBE, (-77.5, 0, 30), (25, 80, 60)),          # left arm
        _p(CUBE, (77.5, 0, 30), (25, 80, 60)),           # right arm
        _p(CUBE, (0, -27.5, 65), (180, 25, 50)),         # backrest
    ],
    "ARMCHAIR": [
        _p(CUBE, (0, 0, 20), (60, 70, 40)),
        _p(CUBE, (-40, 0, 27.5), (20, 70, 55)),
        _p(CUBE, (40, 0, 27.5), (20, 70, 55)),
        _p(CUBE, (0, -24, 65), (100, 22, 50)),
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
    "BENCH": [_p(CUBE, (0, 0, 22.5), (150, 40, 45))],
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
    "PRISONBARS": [
        _p(CUBE, (0, 0, 227), (250, 6, 6)),              # top rail
        _p(CUBE, (0, 0, 3), (250, 6, 6)),                # bottom rail
        _p(CYL, (-120, 0, 115), (5, 5, 224)),
        _p(CYL, (-80, 0, 115), (5, 5, 224)),
        _p(CYL, (-40, 0, 115), (5, 5, 224)),
        _p(CYL, (0, 0, 115), (5, 5, 224)),
        _p(CYL, (40, 0, 115), (5, 5, 224)),
        _p(CYL, (80, 0, 115), (5, 5, 224)),
        _p(CYL, (120, 0, 115), (5, 5, 224)),
    ],
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
    "BOOKCASE": [_p(CUBE, (0, 0, 90), (90, 30, 180))],
    "COUNTER": [_p(CUBE, (0, 0, 45), (100, 60, 90))],
    "DRESSER": [_p(CUBE, (0, 0, 40), (120, 50, 80))],
    "NIGHTSTAND": [_p(CUBE, (0, 0, 27.5), (45, 40, 55))],
    "WARDROBE": [_p(CUBE, (0, 0, 100), (120, 60, 200))],
    "FRIDGE": [_p(CUBE, (0, 0, 90), (70, 70, 180))],
    "STOVE": [_p(CUBE, (0, 0, 45), (76, 70, 90))],
    "TOILET": [
        _p(CUBE, (0, 0, 20), (40, 60, 40)),
        _p(CUBE, (0, -22.5, 60), (45, 15, 40)),
    ],
    "SINK": [
        _p(CYL, (0, 0, 40), (15, 15, 80)),
        _p(CYL, (0, 0, 87.5), (50, 50, 15)),
    ],
    "BATHTUB": [_p(CUBE, (0, 0, 27.5), (170, 75, 55))],
    "RUG": [_p(CUBE, (0, 0, 1), (200, 140, 2))],
    "CAR": [
        _p(CUBE, (0, 0, 60), (180, 450, 55)),            # body
        _p(CUBE, (0, 20, 110), (170, 220, 45)),          # cabin
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
    ],
    "BUSH": [_p(SPHERE, (0, 0, 45), (120, 120, 90))],
    "TREE": [
        _p(CYL, (0, 0, 125), (35, 35, 250)),             # trunk
        _p(SPHERE, (0, 0, 375), (350, 350, 300)),        # canopy
    ],
    # --- vehicles ---------------------------------------------------------
    "MINIBUS": [
        _p(CUBE, (0, 0, 110), (200, 480, 160)),
        _p(CYL, (-85, -160, 35), (70, 70, 20), rot=(90, 0, 0)),
        _p(CYL, (85, -160, 35), (70, 70, 20), rot=(90, 0, 0)),
        _p(CYL, (-85, 160, 35), (70, 70, 20), rot=(90, 0, 0)),
        _p(CYL, (85, 160, 35), (70, 70, 20), rot=(90, 0, 0)),
    ],
    "SEMITRUCK": [
        _p(CUBE, (0, -80, 65), (250, 440, 70)),          # chassis
        _p(CUBE, (0, 160, 185), (240, 260, 240)),        # cab
        _p(CYL, (-105, 190, 50), (100, 100, 30), rot=(90, 0, 0)),
        _p(CYL, (105, 190, 50), (100, 100, 30), rot=(90, 0, 0)),
        _p(CYL, (-105, -180, 50), (100, 100, 30), rot=(90, 0, 0)),
        _p(CYL, (105, -180, 50), (100, 100, 30), rot=(90, 0, 0)),
    ],
    "TRUCKTRAILER": [
        _p(CUBE, (0, 0, 180), (250, 1200, 270)),
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
    "PLANESMALL": [
        _p(CYL, (0, 0, 150), (100, 100, 700), rot=(0, 0, 90)),  # fuselage
        _p(CUBE, (0, 60, 150), (1000, 150, 12)),         # wing
        _p(CUBE, (0, -320, 215), (12, 100, 120)),        # tail fin
    ],
    "FIGHTERJET": [
        _p(CYL, (0, 0, 180), (110, 110, 1500), rot=(0, 0, 90)),
        _p(CUBE, (0, -150, 180), (900, 320, 15)),
        _p(CUBE, (0, -620, 280), (15, 220, 160)),
    ],
    "COMMERCIALJET": [
        _p(CYL, (0, 0, 350), (400, 400, 3500), rot=(0, 0, 90)),
        _p(CUBE, (0, 0, 330), (3000, 550, 30)),
        _p(CUBE, (0, -1620, 600), (30, 450, 550)),
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
        _p(CUBE, (0, 130, 130), (22, 480, 22)),          # arm
        _p(CUBE, (0, -125, 130), (60, 70, 60)),          # counterweight
    ],
    "MICROPHONE": [
        _p(CYL, (0, 0, 2), (40, 40, 4)),
        _p(CYL, (0, 0, 77), (4, 4, 150)),
        _p(CUBE, (0, 6, 160), (7, 22, 7)),
    ],
    "MONITORVILLAGE": [
        _p(CUBE, (0, 0, 70), (100, 60, 140)),            # cart
        _p(CUBE, (0, -5, 165), (90, 8, 50)),             # monitors
    ],
    "EQUIPMENT": [_p(CUBE, (0, 0, 50), (120, 80, 100))],
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

_STAND_BASE = _p(CYL, (0, 0, 2), (60, 60, 4))
_STAND_POLE = _p(CYL, (0, 0, 82), (5, 5, 160))
# Shared rig geometry (frame on two stands; softbox head; slab head; hung ball)
_FRAME_PARTS = [
    _p(CYL, (-65, 0, 60), (5, 5, 120)),
    _p(CYL, (65, 0, 60), (5, 5, 120)),
    _p(CUBE, (0, 0, 120), (120, 6, 120)),
]
_SOFTBOX_PARTS = [_STAND_BASE, _STAND_POLE, _p(CUBE, (0, 12, 165), (90, 60, 90))]
_SLAB_PARTS = [_STAND_BASE, _STAND_POLE, _p(CUBE, (0, 6, 155), (100, 10, 60))]
_HUNG_BALL_PARTS = [_p(CYL, (0, 0, 250), (2, 2, 60)), _p(SPHERE, (0, 0, 190), (60, 60, 60))]
# Handheld omni lamp on a pole ("Light On A Stick", objectKey HOLLYWOODLIGHT)
_STICK_FIXTURE = {
    "parts": [_p(CYL, (0, 0, 90), (4, 4, 180)), _p(CUBE, (0, 0, 190), (15, 15, 15))],
    "emit": (0, 0, 190),
    "cls": "point",
}

LIGHT_FIXTURES: list[tuple[str, dict]] = [
    # (substring of kind, fixture) — checked in order, first match wins, so
    # more specific substrings come first (SOFTBOX before SOFT).
    ("SUN", {"parts": [], "emit": (0, 0, 0), "cls": "directional"}),  # sky: no rig geo
    ("SPEEDRAIL", {  # rigging only, no light (cls unused)
        "parts": [
            _p(CYL, (-100, 0, 120), (5, 5, 240)),
            _p(CYL, (100, 0, 120), (5, 5, 240)),
            _p(CYL, (0, 0, 240), (5, 5, 210), rot=(90, 0, 0)),
        ],
        "emit": None,
        "cls": "spot",
    }),
    ("CHINA", {"parts": _HUNG_BALL_PARTS, "emit": (0, 0, 190), "cls": "point"}),
    ("LANTERN", {"parts": _HUNG_BALL_PARTS, "emit": (0, 0, 190), "cls": "point"}),
    ("BULB", {"parts": _HUNG_BALL_PARTS, "emit": (0, 0, 190), "cls": "point"}),
    ("BALLOON", {
        "parts": [_p(CYL, (0, 0, 260), (2, 2, 80)), _p(SPHERE, (0, 0, 320), (120, 120, 120))],
        "emit": (0, 0, 320),
        "cls": "point",
    }),
    ("PRACTICAL", {  # in-scene floor lamp
        "parts": [
            _p(CYL, (0, 0, 2), (40, 40, 4)),
            _p(CYL, (0, 0, 72), (4, 4, 140)),
            _p(CYL, (0, 0, 160), (40, 40, 35)),
        ],
        "emit": (0, 0, 150),
        "cls": "point",
    }),
    # "Light On A Stick": the app's real objectKey is HOLLYWOODLIGHT.
    ("HOLLYWOOD", _STICK_FIXTURE),
    ("STICK", _STICK_FIXTURE),
    ("SILK", {"parts": _FRAME_PARTS, "emit": (0, 10, 120), "cls": "rect"}),
    ("BOUNCE", {"parts": _FRAME_PARTS, "emit": (0, 10, 120), "cls": "rect"}),
    ("FRAME", {"parts": _FRAME_PARTS, "emit": (0, 10, 120), "cls": "rect"}),
    ("SOFTBOX", {"parts": _SOFTBOX_PARTS, "emit": (0, 45, 165), "cls": "rect"}),
    ("SOFT", {"parts": _SOFTBOX_PARTS, "emit": (0, 45, 165), "cls": "rect"}),
    ("FLO", {"parts": _SLAB_PARTS, "emit": (0, 14, 155), "cls": "rect"}),
    ("PANEL", {"parts": _SLAB_PARTS, "emit": (0, 14, 155), "cls": "rect"}),
    ("LED", {
        "parts": [_STAND_BASE, _STAND_POLE, _p(CUBE, (0, 6, 155), (35, 10, 35))],
        "emit": (0, 14, 155),
        "cls": "rect",
    }),
]

# Anything else (fresnels, open face, ellipsoidal, PAR, scoop, cyc, unknown):
# a classic stand with a boxy head, spotlight at the lens.
LIGHT_FIXTURE_DEFAULT: dict = {
    "parts": [_STAND_BASE, _STAND_POLE, _p(CUBE, (0, 8, 170), (40, 35, 40))],
    "emit": (0, 28, 170),
    "cls": "spot",
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
