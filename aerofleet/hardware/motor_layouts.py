"""ArduCopter motor layouts used by the flight-controller motor test.

Every row below is transcribed from ArduPilot's own motor matrix, not from
a picture: ``libraries/AP_Motors/AP_MotorsMatrix.cpp`` on the ``Copter-4.5``
branch, ``setup_quad_matrix()`` / ``setup_hexa_matrix()``. Each ArduPilot
``MotorDef`` is ``{angle_degrees, yaw_factor, testing_order}`` where

* ``angle_degrees`` is measured from the nose, positive clockwise (to the
  right) — ``add_motor()`` turns it into a roll factor of
  ``cos(angle + 90)``, so +45 is front-right and -135 is rear-left;
* ``yaw_factor`` is ``AP_MOTORS_MATRIX_YAW_FACTOR_CW`` (-1) or ``_CCW`` (+1),
  the propeller's spin direction seen from above;
* ``testing_order`` is the 1-based position in the motor-test *sequence* —
  the letter Mission Planner's Motor Test page shows (1 = A, 2 = B, ...).

The array index + 1 is the motor *number* (the ``SERVOn_FUNCTION`` value
``Motor1``..``MotorN`` = 33..40), which is what ESC telemetry is indexed by.

ArduCopter's ``MAV_CMD_DO_MOTOR_TEST`` handler (``ArduCopter/GCS_Mavlink.cpp``
+ ``motor_test.cpp``) always treats param1 as this *testing order*
(``motors->output_test_seq(motor_test_seq, pwm)``), which is why the letter
sequence runs clockwise from the first motor right of the nose (X frames)
or from the nose motor (+ frames) — see
https://ardupilot.org/copter/docs/connect-escs-and-motors.html
("The motor test will then proceed in a clockwise rotation").
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Tuple

SOURCE_URL = (
    "https://github.com/ArduPilot/ardupilot/blob/Copter-4.5/libraries/AP_Motors/AP_MotorsMatrix.cpp"
)
DOCS_URL = "https://ardupilot.org/copter/docs/connect-escs-and-motors.html"


@dataclass(frozen=True)
class MotorPosition:
    motor_number: int      # SERVOn_FUNCTION MotorN, ESC telemetry index N
    angle_deg: float       # from the nose, +clockwise
    direction: str         # "CW" | "CCW" (propeller rotation seen from above)
    test_order: int        # 1-based position in the motor-test sequence

    @property
    def letter(self) -> str:
        return chr(ord("A") + self.test_order - 1)

    @property
    def position_label(self) -> str:
        return _angle_label(self.angle_deg)

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["letter"] = self.letter
        d["position"] = self.position_label
        return d


@dataclass(frozen=True)
class MotorLayout:
    key: str
    name: str
    frame_class: int
    frame_type: int
    motors: Tuple[MotorPosition, ...]

    @property
    def motor_count(self) -> int:
        return len(self.motors)

    def by_letter(self, letter: str) -> Optional[MotorPosition]:
        letter = letter.strip().upper()
        return next((m for m in self.motors if m.letter == letter), None)

    def by_test_order(self, seq: int) -> Optional[MotorPosition]:
        return next((m for m in self.motors if m.test_order == seq), None)

    def to_dict(self) -> Dict:
        return {
            "key": self.key,
            "name": self.name,
            "frame_class": self.frame_class,
            "frame_type": self.frame_type,
            "motor_count": self.motor_count,
            # Sorted by test letter so a UI can walk A, B, C ... directly.
            "motors": [m.to_dict() for m in sorted(self.motors, key=lambda m: m.test_order)],
            "source": SOURCE_URL,
            "docs": DOCS_URL,
        }


def _angle_label(angle: float) -> str:
    a = ((angle + 180.0) % 360.0) - 180.0
    labels = {
        0: "front", 30: "front-right", 45: "front-right", 60: "front-right",
        90: "right", 120: "rear-right", 135: "rear-right", 150: "rear-right",
        180: "rear", -180: "rear", -30: "front-left", -45: "front-left", -60: "front-left",
        -90: "left", -120: "rear-left", -135: "rear-left", -150: "rear-left",
    }
    return labels.get(int(round(a)), f"{a:.0f} deg")


def _m(number: int, angle: float, direction: str, order: int) -> MotorPosition:
    return MotorPosition(motor_number=number, angle_deg=angle, direction=direction, test_order=order)


# AP_MotorsMatrix.cpp (Copter-4.5), MOTOR_FRAME_QUAD / MOTOR_FRAME_TYPE_X:
#   {   45, CCW, 1 }, { -135, CCW, 3 }, {  -45, CW, 4 }, {  135, CW, 2 }
QUAD_X = MotorLayout("quad_x", "Quad X", 1, 1, (
    _m(1, 45, "CCW", 1),
    _m(2, -135, "CCW", 3),
    _m(3, -45, "CW", 4),
    _m(4, 135, "CW", 2),
))

# MOTOR_FRAME_QUAD / MOTOR_FRAME_TYPE_PLUS:
#   {  90, CCW, 2 }, { -90, CCW, 4 }, {   0, CW, 1 }, { 180, CW, 3 }
QUAD_PLUS = MotorLayout("quad_plus", "Quad +", 1, 0, (
    _m(1, 90, "CCW", 2),
    _m(2, -90, "CCW", 4),
    _m(3, 0, "CW", 1),
    _m(4, 180, "CW", 3),
))

# MOTOR_FRAME_HEXA / MOTOR_FRAME_TYPE_X:
#   {  90, CW, 2 }, { -90, CCW, 5 }, { -30, CW, 6 }, { 150, CCW, 3 },
#   {  30, CCW, 1 }, { -150, CW, 4 }
HEXA_X = MotorLayout("hexa_x", "Hexa X", 2, 1, (
    _m(1, 90, "CW", 2),
    _m(2, -90, "CCW", 5),
    _m(3, -30, "CW", 6),
    _m(4, 150, "CCW", 3),
    _m(5, 30, "CCW", 1),
    _m(6, -150, "CW", 4),
))

LAYOUTS: Dict[str, MotorLayout] = {l.key: l for l in (QUAD_X, QUAD_PLUS, HEXA_X)}

# FRAME_CLASS -> motor count, for output-mapping checks on frames we don't
# carry a full diagram for (FRAME_CLASS values from the ArduCopter 4.5
# parameter reference: 1 Quad, 2 Hexa, 3 Octa, 4 OctaQuad, 5 Y6, 7 Tri,
# 12 DodecaHexa, 14 Deca).
FRAME_CLASS_MOTOR_COUNT: Dict[int, int] = {1: 4, 2: 6, 3: 8, 4: 8, 5: 6, 7: 3, 12: 12, 14: 10}
FRAME_CLASS_NAMES: Dict[int, str] = {
    0: "Undefined", 1: "Quad", 2: "Hexa", 3: "Octa", 4: "OctaQuad", 5: "Y6", 6: "Heli",
    7: "Tri", 8: "SingleCopter", 9: "CoaxCopter", 10: "BiCopter", 11: "Heli_Dual",
    12: "DodecaHexa", 13: "HeliQuad", 14: "Deca", 15: "Scripting Matrix", 16: "6DoF Scripting",
    17: "Dynamic Scripting Matrix",
}
FRAME_TYPE_NAMES: Dict[int, str] = {
    0: "Plus", 1: "X", 2: "V", 3: "H", 4: "V-Tail", 5: "A-Tail", 10: "Y6B", 11: "Y6F",
    12: "BetaFlightX", 13: "DJIX", 14: "ClockwiseX", 15: "I", 18: "BetaFlightXReversed", 19: "Y4",
}


def layout_for_frame(frame_class: Optional[float], frame_type: Optional[float]) -> Optional[MotorLayout]:
    if frame_class is None or frame_type is None:
        return None
    for layout in LAYOUTS.values():
        if layout.frame_class == int(frame_class) and layout.frame_type == int(frame_type):
            return layout
    return None


def all_layouts() -> List[Dict]:
    return [l.to_dict() for l in LAYOUTS.values()]
