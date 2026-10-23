"""Ground truth for the planned-versus-flown check: inject known deviations into real PX4 flights.

DECLARED before running (Atharv's review, experiment E1). Engineering validation, not a hypothesis test.

Logs: the full normal flights downloaded for the crash study (h/normal), rotary wing, with an estimator position
and at least 120 s airborne; up to 40 logs.
Plan: built from the flight itself, one waypoint every 10 s of airborne track at the flown height, so the
unmodified flight should conform. Any deviation reported on it is a false alarm (GPS noise, corners cut between
waypoints, plan-building error).
Injection: in a 30 s window centred in the airborne part, the track is moved sideways (perpendicular to the
direction of travel) by d metres, or up by h metres, with 3 s ramps in and out.
  sideways d in {5, 10, 20, 25, 35, 50, 75, 100} m;  height h in {5, 10, 14, 20, 30, 50} m
Check: reconcile() with its defaults (corridor 30 m, height 15 m, minimum 3 s).
Detected = an episode of the injected kind that overlaps the window.
Report: detection rate per size with 95% Wilson intervals, and the false-alarm rate on unmodified flights.
Expected if the check works as specified: near 0 below the tolerance, near 1 clearly above it.

    python research/px4_log_study/injection_reconcile.py LOG_DIR OUT_MD
"""
import math
import os
import sys
from glob import glob

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, ROOT)

from aerofleet.assurance.flightlog import FlightLogError, read_flight_log  # noqa: E402
from aerofleet.assurance.reconcile import parse_waypoints, reconcile  # noqa: E402

M_PER_DEG = 111_320.0
SIDEWAYS = [5, 10, 20, 25, 35, 50, 75, 100]
UPWARD = [5, 10, 14, 20, 30, 50]
WINDOW_S, RAMP_S, WP_EVERY_S = 30.0, 3.0, 10.0


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"),) * 3
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def plan_from(track):
    t0 = track[0][0]
    pts, next_t = [], t0
    for t, la, lo, h in track:
        if t >= next_t:
            pts.append((la, lo, h))
            next_t = t + WP_EVERY_S
    if pts[-1] != (track[-1][1], track[-1][2], track[-1][3]):
        pts.append((track[-1][1], track[-1][2], track[-1][3]))
    home = track[0]
    lines = ["QGC WPL 110", f"0\t1\t0\t16\t0\t0\t0\t0\t{home[1]:.8f}\t{home[2]:.8f}\t0\t1",
             f"1\t0\t3\t22\t0\t0\t0\t0\t{pts[0][0]:.8f}\t{pts[0][1]:.8f}\t{max(1.0, pts[0][2]):.2f}\t1"]
    lines += [f"{i}\t0\t3\t16\t0\t0\t0\t0\t{la:.8f}\t{lo:.8f}\t{max(1.0, h):.2f}\t1" for i, (la, lo, h) in enumerate(pts[1:], 2)]
    return parse_waypoints("\n".join(lines) + "\n")


def weight(t, a, b):
    if t < a or t > b:
        return 0.0
    return min(1.0, (t - a) / RAMP_S, (b - t) / RAMP_S)


def inject(track, a, b, sideways=0.0, up=0.0):
    out = []
    for i, (t, la, lo, h) in enumerate(track):
        w = weight(t, a, b)
        if w == 0:
            out.append((t, la, lo, h))
            continue
        j0, j1 = max(0, i - 3), min(len(track) - 1, i + 3)
        de = (track[j1][2] - track[j0][2]) * M_PER_DEG * math.cos(math.radians(la))
        dn = (track[j1][1] - track[j0][1]) * M_PER_DEG
        norm = math.hypot(de, dn) or 1.0
        pe, pn = -dn / norm, de / norm                       # unit vector to the left of travel
        la2 = la + w * sideways * pn / M_PER_DEG
        lo2 = lo + w * sideways * pe / (M_PER_DEG * math.cos(math.radians(la)))
        out.append((t, la2, lo2, h + w * up))
    return out


def detected(report, kind, a, b, t0):
    return any(e["kind"] == kind and e["start_s"] + t0 <= b and e["start_s"] + e["duration_s"] + t0 >= a for e in report["episodes"])


def main(log_dir, out_md):
    flights = []
    for path in sorted(glob(os.path.join(log_dir, "*.ulg"))):
        try:
            f = read_flight_log(path)
        except (FlightLogError, Exception):  # noqa: BLE001
            continue
        if f.vehicle not in (None, "quadcopter", "hexacopter", "octocopter") or f.position_source != "vehicle_global_position":
            continue
        air = [p for p in f.track if p[3] > 2.0]
        if len(air) < 50 or air[-1][0] - air[0][0] < 120:
            continue
        flights.append((os.path.basename(path), air, f.modes))
        if len(flights) >= 40:
            break
    base_alarms, rows = 0, {}
    for name, air, modes in flights:
        plan = plan_from(air)
        t0 = air[0][0]
        mid = (air[0][0] + air[-1][0]) / 2
        a, b = mid - WINDOW_S / 2, mid + WINDOW_S / 2
        base = reconcile(plan, air, ())
        base_alarms += bool(base["episodes"])
        for d in SIDEWAYS:
            r = reconcile(plan, inject(air, a, b, sideways=d), ())
            rows.setdefault(("sideways", d), []).append(detected(r, "off_route", a, b, t0))
        for h in UPWARD:
            r = reconcile(plan, inject(air, a, b, up=h), ())
            rows.setdefault(("height", h), []).append(detected(r, "off_altitude", a, b, t0))
    n = len(flights)
    p, lo, hi = wilson(base_alarms, n)
    L = ["# Injected deviations in real PX4 flights (planned-versus-flown check)", "",
         f"Flights: {n} real PX4 multirotor logs (rated good or great), each at least 120 s airborne. Plan built from the "
         f"flight itself (a waypoint every {WP_EVERY_S:g} s). Deviation injected for {WINDOW_S:g} s with {RAMP_S:g} s ramps. "
         "Check run with its defaults: 30 m sideways, 15 m height, at least 3 s. Declared in `injection_reconcile.py`.", "",
         f"**False alarms on the unmodified flights:** {base_alarms} of {n} ({100 * p:.0f}%, 95% CI {100 * lo:.0f}-{100 * hi:.0f}%).", "",
         "| Injected | Size | Detected | Rate | 95% CI |", "|---|---|---|---|---|"]
    for (kind, size), hits in rows.items():
        k = sum(hits)
        p, lo, hi = wilson(k, len(hits))
        L.append(f"| {'sideways' if kind == 'sideways' else 'upwards'} | {size} m | {k} of {len(hits)} | {100 * p:.0f}% | {100 * lo:.0f}-{100 * hi:.0f}% |")
    L += ["", "A false alarm here means the check reported a deviation on a flight that followed a plan made from itself; "
          "a miss below the tolerance is the intended behaviour, not an error."]
    open(out_md, "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main(*sys.argv[1:3])
