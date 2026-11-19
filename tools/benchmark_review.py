"""How long a flight review takes on real PX4 logs, on this computer.

    AEROFLEET_PX4_DATA="/Volumes/One Touch/AeroFleet_px4_data" python tools/benchmark_review.py

Takes N real public logs spread over the size range (every k-th by size across the study's downloaded log folders), and times
the work the API does for a log-only review: reading the log, vibration, the evidence timeline, the comparison with
public flights. Database write and signing are excluded (a few milliseconds). Writes docs/measurements/review_speed.md.
A measurement of this machine, not a claim about others.
"""
from __future__ import annotations

import os
import platform
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.environ.get("AEROFLEET_PX4_DATA", "/Volumes/One Touch/AeroFleet_px4_data")
N = 40
FOLDERS = ("screen_ref", "within", "rough", "newer", "control")   # every downloaded public log folder
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "measurements", "review_speed.md")


def main() -> None:
    from aerofleet.assurance.evidence import timeline
    from aerofleet.assurance.flightlog import FlightLogError, read_flight_log
    from aerofleet.assurance.public_reference import vibration_position
    from aerofleet.assurance.vibration import flight_vibration

    logs = sorted((os.path.join(DATA, d, f) for d in FOLDERS if os.path.isdir(os.path.join(DATA, d))
                   for f in os.listdir(os.path.join(DATA, d)) if f.endswith(".ulg") and not f.startswith("._")), key=os.path.getsize)
    pick = logs[:: max(1, len(logs) // N)][:N]
    rows, failed = [], 0
    for p in pick:
        mb = os.path.getsize(p) / 1e6
        t0 = time.perf_counter()
        try:
            f = read_flight_log(p)
            v = flight_vibration(f)
            timeline({"episodes": []}, f.track, f.modes, f.battery, f.gps, f.param_changes, f.health)
            vibration_position(v and v["source"], f.vehicle, v and v["p95"])
        except FlightLogError:
            failed += 1
            continue
        rows.append((mb, time.perf_counter() - t0, f.duration_s / 60))
    secs = [s for _, s, _ in rows]
    rate = sum(m for m, _, _ in rows) / sum(secs)
    big = max(rows)
    lines = ["# Flight review speed on real PX4 logs", "",
             f"Measured {time.strftime('%d %B %Y')} on {platform.machine()} {platform.system()} {platform.release()}, Python "
             f"{platform.python_version()}. {len(rows)} real public PX4 logs from the study's downloaded folders, spread over the "
             f"size range; {failed} could not be read and were skipped. Times cover reading the log, vibration, the evidence "
             "timeline and the public comparison (not the database write). Script: `tools/benchmark_review.py`.", "",
             "| | Value |", "|---|---|",
             f"| Log sizes | {min(m for m, _, _ in rows):.1f} to {big[0]:.1f} MB (median {statistics.median(m for m, _, _ in rows):.1f} MB) |",
             f"| Flight lengths | {min(d for _, _, d in rows):.1f} to {max(d for _, _, d in rows):.1f} min |",
             f"| Time per review | median {statistics.median(secs):.2f} s, slowest {max(secs):.2f} s |",
             f"| Largest log | {big[0]:.1f} MB in {big[1]:.2f} s |",
             f"| Throughput | {rate:.1f} MB/s |", ""]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w").write("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
