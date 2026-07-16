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
    # production equipment
    ("BOOM", "BOOM"),
    ("CRANE", "CRANE"),
    ("MICROPHONE", "MICROPHONE"),
    ("MIC", "MICROPHONE"),
    ("MONITORV", "MONITORVILLAGE"),
    ("EQUIPMENT", "EQUIPMENT"),
    ("ARROW", "ARROW"),
]

# Fallback for anything unrecognized: an obvious placeholder cube.
GENERIC = [_p(CUBE, (0, 0, 50), (100, 100, 100))]


# ---------------------------------------------------------------------------
# Light fixture blockouts
# ---------------------------------------------------------------------------
# Every Shot Designer light spawns placeholder rig geometry plus an actual
# Unreal light attached at the fixture's emit point. ``emit`` is the offset of
# that emit point (cm, same local frame as prop parts); ``emit: None`` means
# the item is rigging only and no light is spawned (e.g. speed rail).

_STAND_BASE = _p(CYL, (0, 0, 2), (60, 60, 4))
_STAND_POLE = _p(CYL, (0, 0, 82), (5, 5, 160))

LIGHT_FIXTURES: list[tuple[str, dict]] = [
    # (substring of kind, fixture) — checked in order, first match wins.
    ("SUN", {"parts": [], "emit": (0, 0, 0)}),  # sky light: no rig geo
    ("SPEEDRAIL", {  # rigging only, no light
        "parts": [
            _p(CYL, (-100, 0, 120), (5, 5, 240)),
            _p(CYL, (100, 0, 120), (5, 5, 240)),
            _p(CYL, (0, 0, 240), (5, 5, 210), rot=(90, 0, 0)),
        ],
        "emit": None,
    }),
    ("CHINA", {  # hanging paper ball
        "parts": [_p(CYL, (0, 0, 250), (2, 2, 60)), _p(SPHERE, (0, 0, 190), (60, 60, 60))],
        "emit": (0, 0, 190),
    }),
    ("BALLOON", {
        "parts": [_p(CYL, (0, 0, 260), (2, 2, 80)), _p(SPHERE, (0, 0, 320), (120, 120, 120))],
        "emit": (0, 0, 320),
    }),
    ("PRACTICAL", {  # in-scene floor lamp
        "parts": [
            _p(CYL, (0, 0, 2), (40, 40, 4)),
            _p(CYL, (0, 0, 72), (4, 4, 140)),
            _p(CYL, (0, 0, 160), (40, 40, 35)),
        ],
        "emit": (0, 0, 150),
    }),
    ("STICK", {  # handheld lamp on a pole
        "parts": [_p(CYL, (0, 0, 90), (4, 4, 180)), _p(CUBE, (0, 0, 190), (15, 15, 15))],
        "emit": (0, 0, 190),
    }),
    ("SILK", {  # frame on two stands, light on the face
        "parts": [
            _p(CYL, (-65, 0, 60), (5, 5, 120)),
            _p(CYL, (65, 0, 60), (5, 5, 120)),
            _p(CUBE, (0, 0, 120), (120, 6, 120)),
        ],
        "emit": (0, 10, 120),
    }),
    ("BOUNCE", {
        "parts": [
            _p(CYL, (-65, 0, 60), (5, 5, 120)),
            _p(CYL, (65, 0, 60), (5, 5, 120)),
            _p(CUBE, (0, 0, 120), (120, 6, 120)),
        ],
        "emit": (0, 10, 120),
    }),
    ("SOFTBOX", {
        "parts": [_STAND_BASE, _STAND_POLE, _p(CUBE, (0, 12, 165), (90, 60, 90))],
        "emit": (0, 45, 165),
    }),
    ("FLO", {  # tube banks: vertical slab head on a stand
        "parts": [_STAND_BASE, _STAND_POLE, _p(CUBE, (0, 6, 155), (100, 10, 60))],
        "emit": (0, 14, 155),
    }),
    ("PANEL", {
        "parts": [_STAND_BASE, _STAND_POLE, _p(CUBE, (0, 6, 155), (100, 10, 60))],
        "emit": (0, 14, 155),
    }),
    ("LED", {
        "parts": [_STAND_BASE, _STAND_POLE, _p(CUBE, (0, 6, 155), (35, 10, 35))],
        "emit": (0, 14, 155),
    }),
]

# Anything else (fresnels, open face, ellipsoidal, PAR, scoop, cyc, unknown):
# a classic stand with a boxy head, light at the lens.
LIGHT_FIXTURE_DEFAULT: dict = {
    "parts": [_STAND_BASE, _STAND_POLE, _p(CUBE, (0, 8, 170), (40, 35, 40))],
    "emit": (0, 28, 170),
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
