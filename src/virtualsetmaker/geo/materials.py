"""Flat previz color palette for the shipped prop models.

Names are the OBJ/MTL material names AND the UE material-instance keys: the
generated script creates ``MI_VSM_<name>`` instances (parented to the engine's
BasicShapeMaterial) with these colors, so the look is deterministic even when
the OBJ importer ignores the .mtl. Values are linear RGB 0-1.
"""

MATERIALS: dict[str, tuple[float, float, float]] = {
    "wood": (0.45, 0.29, 0.14),
    "wood_dark": (0.23, 0.13, 0.06),
    "fabric": (0.36, 0.38, 0.44),      # cool upholstery gray-blue
    "fabric_warm": (0.52, 0.36, 0.24), # tan/camel upholstery
    "leather": (0.30, 0.16, 0.09),
    "mattress": (0.85, 0.83, 0.78),
    "pillow": (0.92, 0.91, 0.88),
    "porcelain": (0.92, 0.93, 0.94),
    "metal": (0.62, 0.64, 0.68),
    "metal_dark": (0.18, 0.19, 0.21),
    "glass": (0.45, 0.62, 0.68),
    "screen": (0.05, 0.09, 0.12),
    "foliage": (0.15, 0.38, 0.12),
    "bark": (0.28, 0.19, 0.11),
    "rubber": (0.09, 0.09, 0.10),
    "plastic_dark": (0.15, 0.15, 0.17),
    "plastic_light": (0.68, 0.68, 0.66),
    "paper": (0.95, 0.94, 0.90),
    "clay": (0.62, 0.34, 0.22),
    "paint_red": (0.60, 0.12, 0.10),
    "paint_blue": (0.14, 0.25, 0.48),
    "paint_white": (0.88, 0.89, 0.90),
    "paint_olive": (0.28, 0.30, 0.18),
    "paint_yellow": (0.80, 0.65, 0.10),
}
