"""Pick the logs for the PX4 crash study from the public Flight Review index.

Crashes: logs the uploader rated crash_sw_hw ("the drone") or crash_pilot ("the pilot").
Controls: logs rated good/great, matched 5:1 to the crashes on vehicle type.
Only real hardware (no SITL), at least 5 s long (crashes are often short), PX4 v1.10 or newer. Fixed seed, so the pick repeats.

    python research/px4_log_study/select_logs.py DBINFO_JSON(.gz) OUT_CSV [N_CRASH] [CONTROLS_PER_CRASH]
"""
import csv
import gzip
import json
import random
import sys
from collections import Counter, defaultdict

CRASH = ("crash_sw_hw", "crash_pilot")
GOOD = ("good", "great")


def usable(x):
    rel = (x.get("ver_sw_release") or "").split(" ")[0]
    try:
        major, minor = (int(p) for p in rel.lstrip("v").split(".")[:2])
    except ValueError:
        return False
    return ("SITL" not in str(x.get("sys_hw"))) and (x.get("duration_s") or 0) >= 5 and (major, minor) >= (1, 10)


def main(src, out, n_crash=100, per=5, seed=1):
    raw = open(src, "rb").read()
    rows = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
    pool = [x for x in rows if usable(x)]
    crashes = [x for x in pool if x["rating"] in CRASH]
    rng = random.Random(seed)
    pick = rng.sample(crashes, min(n_crash, len(crashes)))
    crash_vehicles = {x["vehicle_uuid"] for x in pick}
    by_type = defaultdict(list)
    for x in pool:
        if x["rating"] in GOOD and x["vehicle_uuid"] not in crash_vehicles:
            by_type[x["mav_type"]].append(x)
    controls = []
    for t, k in Counter(x["mav_type"] for x in pick).items():
        controls += rng.sample(by_type[t], min(per * k, len(by_type[t])))
    print(f"usable logs {len(pool)}; crashes available {len(crashes)} {Counter(x['rating'] for x in crashes)}; "
          f"picked {len(pick)} crashes {Counter(x['rating'] for x in pick)} and {len(controls)} controls")
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["group", "rating", "log_id", "mav_type", "sys_hw", "ver_sw_release", "duration_s", "vehicle_uuid", "download_url"])
        for g, xs in (("crash", pick), ("control", controls)):
            for x in xs:
                w.writerow([g, x["rating"], x["log_id"], x["mav_type"], x["sys_hw"], x["ver_sw_release"], x["duration_s"],
                            x["vehicle_uuid"], x["download_url"]])


if __name__ == "__main__":
    a = sys.argv
    main(a[1], a[2], *(int(v) for v in a[3:5]))
