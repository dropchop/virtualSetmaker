"""The single source of truth for converting IR coordinates into Unreal's frame.

Keeping this in one small module means the whole screen->Unreal orientation
question is decided in exactly one place. If the live-editor calibration pass
reveals that an axis or a sign is flipped, this is the only file to touch.

Frames
------
* **IR**: meters, Shot Designer screen orientation (X right, Y down), Z up,
  yaw in degrees measured from +X (Shot Designer's ``angle``, converted to deg).
* **Unreal**: centimeters, X forward, Y right, Z up, left-handed. Yaw is a
  rotation about Z.

The conversion is a pure metres->cm scale: axes and yaw map across UNCHANGED.
Shot Designer's floor-plan frame (x right, y down, z implicitly up) and
Unreal's frame are BOTH left-handed, so the identity is the proper
(chirality-preserving) map between them. An earlier version negated Y "so
screen-down becomes -Y" — that map has determinant -1, i.e. it reflected the
whole scene: every through-camera shot came out mirrored left/right versus the
Shot Designer plan, and users saw props "on the other side of the room".
Verified against a real scene: an actor on the camera's screen-left in Shot
Designer must land on the camera's left in Unreal.
"""

from __future__ import annotations

from .ir import Vec3

M_TO_CM = 100.0


def ir_to_ue_location(v: Vec3, m_to_cm: float = M_TO_CM) -> tuple[float, float, float]:
    """IR meters (screen-oriented) -> Unreal centimeters (X, Y, Z)."""
    return (v.x * m_to_cm, v.y * m_to_cm, v.z * m_to_cm)


def ir_to_ue_yaw(yaw_deg: float) -> float:
    """IR yaw (deg, from +X) -> Unreal yaw. Same handedness, no sign change."""
    return yaw_deg


def ir_to_ue_rotation(
    pitch_deg: float, yaw_deg: float, roll_deg: float
) -> tuple[float, float, float]:
    """Return an Unreal (pitch, yaw, roll) triple in degrees.

    Ordered to match ``unreal.Rotator(pitch, yaw, roll)``.
    """
    return (pitch_deg, ir_to_ue_yaw(yaw_deg), roll_deg)
