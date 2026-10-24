"""Planned-versus-flown check on real missions: how often does it report a deviation on an ordinary mission flight?

DECLARED before running (25 Oct 2026). Answers the open question left by injection_reconcile.py, whose plans were
built from the flown track (22% false alarms, mostly corner-cutting on plans that had no waypoints at the turns).

Logs: every locally downloaded PX4 log (h/normal, rough, newer, within, crash) that records the mission it flew
(at least 3 navigator_mission_item messages with waypoint, takeoff or land commands), multirotor, with an estimator
position, rated good or great or unrated, not crash-rated.
Plan: the mission items in the order the vehicle activated them (nav_cmd 22 takeoff, 16 waypoint, 21 land;
consecutive duplicates removed), heights relative to home (absolute items converted with home_position.alt),
written as a QGC WPL file and parsed by the same parser operators use.
Track: the flown positions from the first to the last mission item activation, plus 30 s.
Check: reconcile() with its defaults (30 m sideways, 15 m height, at least 3 s).
Report: the share of missions with any reported deviation (95% Wilson interval), and for each reported episode
its kind, size and duration, so that a reader can judge whether it looks like a real deviation (the logs are not
known to be deviation-free, so the share is an upper bound on false alarms).

    python research/px4_log_study/real_mission_reconcile.py LOG_ROOT OUT_MD
"""
import glob
import math
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, ROOT)

from aerofleet.assurance.flightlog import read_flight_log  # noqa: E402
from aerofleet.assurance.reconcile import parse_waypoints, reconcile  # noqa: E402

CMDS = {22, 16, 21}
DIRS = ("h/normal", "rough", "newer", "within", "crash")


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"),) * 3
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def mission(path):
    from pyulog import ULog
    u = ULog(path, ["navigator_mission_item", "home_position", "vehicle_status"])
    ds = {d.name: d.data for d in u.data_list}
    m = ds.get("navigator_mission_item")
    if m is None:
        return None
    home = ds.get("home_position")
    home_alt = float(home["alt"][0]) if home is not None and len(home["timestamp"]) else None
    items, times = [], []
    for k in range(len(m["timestamp"])):
        if int(m["nav_cmd"][k]) not in CMDS:
            continue
        alt = float(m["altitude"][k])
        if not int(m["altitude_is_relative"][k]):
            if home_alt is None:
                continue
            alt -= home_alt
        it = (int(m["nav_cmd"][k]), round(float(m["latitude"][k]), 7), round(float(m["longitude"][k]), 7), round(alt, 1))
        if not items or it[1:] != items[-1][1:]:
            items.append(it)
            times.append(m["timestamp"][k] / 1e6)
    return (items, times[0], times[-1]) if len(items) >= 3 else None


def plan_text(items, home):
    lines = ["QGC WPL 110", f"0\t1\t0\t16\t0\t0\t0\t0\t{home[0]:.8f}\t{home[1]:.8f}\t0\t1"]
    for i, (cmd, la, lo, alt) in enumerate(items, 1):
        lines.append(f"{i}\t0\t3\t{cmd}\t0\t0\t0\t0\t{la:.8f}\t{lo:.8f}\t{max(0.0, alt):.2f}\t1")
    return "\n".join(lines) + "\n"


def main(root, out_md):
    seen, results = set(), []
    for d in DIRS:
        for path in sorted(glob.glob(os.path.join(root, d, "*.ulg"))):
            name = os.path.basename(path)
            if name in seen:
                continue
            seen.add(name)
            try:
                mi = mission(path)
                if not mi:
                    continue
                f = read_flight_log(path)
            except Exception:  # noqa: BLE001
                continue
            if f.vehicle not in (None, "quadcopter", "hexacopter", "octocopter") or f.position_source != "vehicle_global_position":
                continue
            items, t_first, t_last = mi
            track = [p for p in f.track if t_first <= p[0] <= t_last + 30.0]
            if len(track) < 20:
                continue
            try:
                plan = parse_waypoints(plan_text(items, (track[0][1], track[0][2])))
                r = reconcile(plan, track, ())
            except Exception:  # noqa: BLE001
                continue
            results.append((name, len(items), track[-1][0] - track[0][0], r["episodes"]))
    n = len(results)
    k = sum(1 for r in results if r[3])
    p, lo, hi = wilson(k, n)
    L = ["# Planned-versus-flown check on real PX4 missions", "",
         f"Declared in `real_mission_reconcile.py`. Missions: {n} logs that record the mission they flew. Check run with its "
         "defaults (30 m sideways, 15 m height, at least 3 s).", "",
         f"**Missions with any reported deviation:** {k} of {n} ({100 * p:.0f}%, 95% CI {100 * lo:.0f}-{100 * hi:.0f}%). "
         "An upper bound on false alarms: some may be real deviations.", "",
         "| Log | Mission items | Seconds compared | Reported episodes (kind, max m, s) |", "|---|---|---|---|"]
    for name, items, secs, eps in results:
        desc = "; ".join(f"{e['kind']} {e.get('max_m', 0):.0f} m {e['duration_s']:.0f} s" for e in eps) or "none"
        L.append(f"| {name[:8]} | {items} | {secs:.0f} | {desc} |")
    open(out_md, "w").write("\n".join(L) + "\n")
    print("\n".join(L[:8]))


if __name__ == "__main__":
    main(*sys.argv[1:3])
