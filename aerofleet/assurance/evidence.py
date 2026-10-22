"""Evidence timeline for a flight review: what the log shows, and when — for a person to judge.

AeroFleet does not name a cause. The measured reason (research/results/px4_log_study/): on public PX4 crash
logs a fixed rule could not tell a pilot-caused crash from an aircraft fault (balanced accuracy 0.47 on
held-out crashes), and five small language models lost to a plain rule on generated cases. What the code can
do reliably is put the facts in order, so the person reviewing sees them at once instead of opening plots.

Every event is a number from the log at a time; times are seconds from the start of the track, the same clock
as the plan-deviation episodes.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from aerofleet.assurance.drift import CRITICAL, HIGH, severity_of
from aerofleet.assurance.reconcile import PILOT_MODES

AUTO_MODES = {"AUTO", "MISSION", "RTL", "SMART_RTL", "LAND", "GUIDED", "HOLD", "TAKEOFF", "PRECLAND", "DESCEND"}
LOW_BATTERY_PCT, CRITICAL_BATTERY_PCT = 20.0, 10.0
MIN_SATS, MAX_HDOP = 6, 2.5
LOOKBACK_S = 30.0          # events this long before an episode count as "around it"


def _event(t: float, kind: str, level: str, text: str, **data: Any) -> Dict[str, Any]:
    return {"t_s": round(t, 1), "kind": kind, "level": level, "text": text, **data}


def _spans(samples: Sequence[Tuple[float, bool]], t0: float) -> List[Tuple[float, float]]:
    """(start, end) of runs where the flag is true, in track time."""
    out, start, last = [], None, None
    for t, bad in samples:
        if bad and start is None:
            start = t
        if not bad and start is not None:
            out.append((start - t0, t - t0))
            start = None
        last = t
    if start is not None and last is not None:
        out.append((start - t0, last - t0))
    return out


def timeline(report: Dict[str, Any], track, modes, battery=(), gps=(), param_changes=()) -> List[Dict[str, Any]]:
    """All notable events in the flight, in time order."""
    if not track:
        return []
    t0, t_end = track[0][0], track[-1][0] - track[0][0]
    ev: List[Dict[str, Any]] = []

    prev: Optional[str] = None
    for t, mode in modes:
        name = mode.upper()
        if prev is not None and t - t0 >= -1.0:
            pilot_after_auto = name in PILOT_MODES and prev in AUTO_MODES
            ev.append(_event(t - t0, "mode", "notice" if pilot_after_auto else "info",
                             f"Flight mode {prev} → {name}" + (" (pilot took control)" if pilot_after_auto else ""),
                             mode=name))
        prev = name

    for t, name, old, new in param_changes:
        sev = severity_of(name)
        if sev in (CRITICAL, HIGH):
            ev.append(_event(t - t0, "setting", "warning" if sev == CRITICAL else "notice",
                             f"Setting {name} changed {old:g} → {new:g} in flight ({'safety-critical' if sev == CRITICAL else 'flight limit'})",
                             name=name, old=old, new=new))

    for threshold, level in ((LOW_BATTERY_PCT, "notice"), (CRITICAL_BATTERY_PCT, "warning")):
        hit = next(((t, v, r) for t, v, r in battery if r is not None and r < threshold), None)
        if hit:
            ev.append(_event(hit[0] - t0, "battery", level, f"Battery below {threshold:g}% ({hit[2]:.0f}%, {hit[1]:.1f} V)",
                             percent=hit[2], volts=hit[1]))
    if battery:
        v_start = max(v for t, v, _ in battery[: max(1, len(battery) // 20)])
        t_min, v_min, _ = min(battery, key=lambda b: b[1])
        if v_start > 0 and (v_start - v_min) / v_start > 0.25:
            ev.append(_event(t_min - t0, "battery", "notice", f"Battery voltage fell {100 * (v_start - v_min) / v_start:.0f}% "
                             f"({v_start:.1f} → {v_min:.1f} V)", volts=v_min))

    poor = [(t, fix < 3 or sats < MIN_SATS or (hdop is not None and hdop > MAX_HDOP)) for t, sats, hdop, fix in gps]
    for a, b in _spans(poor, t0):
        if b - a >= 2.0 and b >= 0:
            ev.append(_event(a, "gps", "warning", f"Poor GPS for {b - a:.0f} s (fewer than {MIN_SATS} satellites, no 3D fix, "
                             f"or HDOP above {MAX_HDOP:g})", end_s=round(b, 1)))

    labels = {"off_route": "Off the planned route", "off_altitude": "Off the planned height", "in_no_fly_zone": "Inside a no-fly zone"}
    for i, e in enumerate(report.get("episodes", [])):
        extra = f", up to {e['max_m']:.0f} m" if e.get("max_m") else ""
        ev.append(_event(e["start_s"], "plan", "warning", f"{labels.get(e['kind'], e['kind'])} for {e['duration_s']:.0f} s{extra}",
                         episode=i, end_s=round(e["start_s"] + e["duration_s"], 1)))
    ev.append(_event(t_end, "end", "info", "End of the recorded track"))
    ev.sort(key=lambda x: (x["t_s"], x["kind"] != "plan"))
    return ev


def around_episodes(report: Dict[str, Any], events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """For each plan-deviation episode, the other events from LOOKBACK_S before it to its end."""
    out = []
    for i, e in enumerate(report.get("episodes", [])):
        a, b = e["start_s"] - LOOKBACK_S, e["start_s"] + e["duration_s"]
        near = [x for x in events if x["kind"] not in ("plan", "end") and a <= x["t_s"] <= b]
        out.append({"episode": i, "kind": e["kind"], "start_s": e["start_s"], "events": near,
                    "summary": "; ".join(x["text"] for x in near) or "Nothing else in the log stands out around it"})
    return out
