"""Second, untouched sample for the PX4 crash benchmark.

Every usable crash log NOT in the first selection (the held-out crashes), and 200 full normal flights rated
good/great, matched to them on vehicle type, from vehicles not in any crash set. Seed 2.

    python research/px4_log_study/select_holdout.py DBINFO_JSON FIRST_SELECTION_CSV OUT_CSV
"""
import csv
import gzip
import json
import random
import sys
from collections import Counter, defaultdict

from select_logs import CRASH, GOOD, usable


def main(src, first_csv, out, n_normal=200, seed=2):
    raw = open(src, "rb").read()
    rows = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
    pool = [x for x in rows if usable(x)]
    used = {r["log_id"] for r in csv.DictReader(open(first_csv))}
    crashes = [x for x in pool if x["rating"] in CRASH]
    held = [x for x in crashes if x["log_id"] not in used]
    crash_vehicles = {x["vehicle_uuid"] for x in crashes}
    by_type = defaultdict(list)
    for x in pool:
        if x["rating"] in GOOD and x["log_id"] not in used and x["vehicle_uuid"] not in crash_vehicles:
            by_type[x["mav_type"]].append(x)
    rng = random.Random(seed)
    types = Counter(x["mav_type"] for x in held)
    normal = []
    for t, k in types.items():
        want = round(n_normal * k / len(held))
        normal += rng.sample(by_type[t], min(want, len(by_type[t])))
    print(f"held-out crashes {len(held)} {Counter(x['rating'] for x in held)}; normal flights {len(normal)}")
    with open(out, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["group", "rating", "log_id", "mav_type", "sys_hw", "ver_sw_release", "duration_s", "vehicle_uuid",
                    "download_url"])
        for g, xs in (("crash", held), ("normal", normal)):
            for x in xs:
                w.writerow([g, x["rating"], x["log_id"], x["mav_type"], x["sys_hw"], x["ver_sw_release"], x["duration_s"],
                            x["vehicle_uuid"], x["download_url"]])


if __name__ == "__main__":
    main(*sys.argv[1:4])
