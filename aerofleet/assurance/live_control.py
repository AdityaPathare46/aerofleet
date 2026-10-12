"""One switch for commanding real aircraft — off by default.

AeroFleet 2.0 is a ground-side assurance tool: it reads files and plans, it does not fly drones.
The older live path (arm, take-off and go-to after a dispatch, the bench motor test) is kept in the
code but refused unless the operator of the install deliberately sets

    AEROFLEET_LIVE_CONTROL=on

Commands that make an aircraft *safe* are never behind this switch: disarm, the emergency stop and
the return-to-home / hold fallbacks stay available whatever it says — stopping must not be blocked.
"""
from __future__ import annotations

import os

from fastapi import HTTPException

ENV = "AEROFLEET_LIVE_CONTROL"
REFUSAL = ("Commanding a real drone is switched off. AeroFleet 2.0 checks plans, settings and logs on the ground; "
           f"it does not fly aircraft. An administrator can enable the legacy live path with {ENV}=on.")


def live_control_enabled() -> bool:
    return os.environ.get(ENV, "off").strip().lower() in ("1", "on", "true", "yes")


def require_live_control() -> None:
    """FastAPI dependency for endpoints that start or move a real aircraft."""
    if not live_control_enabled():
        raise HTTPException(status_code=403, detail=REFUSAL)
