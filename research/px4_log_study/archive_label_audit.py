"""Archive-wide label audit: how many crash-rated logs in the public PX4 archive contain the crash?

PRE-DECLARED (committed and pushed before the 212 missing logs are downloaded and before this script is run).
Status: exploratory (dagger), declared after the sixteenth internal review and the crash-moment review, not blind.

Why: in the modelled sample only 72 of 148 crash logs show tilt above 60 deg, and one author's reading of 50 traces
found that 18 of 24 logs without a tilt event show no crash at all. If that holds across the archive, the crash
rating describes a flight session rather than the log, which matters to anyone who trains or evaluates on these
labels.

POPULATION: every log in dbinfo.json rated crash_sw_hw or crash_pilot from real hardware (sys_hw without "SITL"):
520 logs, 308 already on disk, 212 downloaded by `fetch` into DATA_ROOT/archive_crash/ (1.53 GB measured by HEAD
requests). A log that cannot be downloaded or read is counted as unreadable, not dropped silently.

PER LOG: crash status exactly as r16_audit.crash_status - confirmed (tilt > 60 deg, then disarm or landed/ground
contact within 10 s), tilt_unconfirmed, fallback (no tilt > 60 deg), unreadable; vehicle type (rotary or not, from
vehicle_status); armed duration; dbinfo rating, log_date year, ver_sw_release major.minor.

REPORTED (descriptive; reported whatever the result):
  R1 Counts and shares of each status over all 520, and over rotary-wing logs only (fixed-wing logs always fall back
     because the crash moment is defined by multicopter tilt).
  R2 The same by uploader rating (crash_pilot vs crash_sw_hw) with a two-sided Fisher exact test on tilt-defined
     (confirmed + tilt_unconfirmed) vs fallback; by year band (<= 2019, 2020-2022, >= 2023); by PX4 version (< 1.12,
     >= 1.12, unknown).
  R3 Estimated share of crash-rated logs that contain the crash. From the crash-moment review (one author, 50 logs,
     crash_moment_review.csv, reviewer_2): a log contains the crash if labelled correct, too early or too late; "no
     crash visible" means it does not; "can't tell" is excluded. Estimate = share_tilt x P(contains | tilt-defined)
     + share_fallback x P(contains | fallback), over readable rotary-wing logs. 95% interval by bootstrap (2,000
     resamples, seed 2045) resampling archive logs and review labels within status. Stated limits: one reviewer, not
     blind, 50 reviewed logs drawn from the modelled sample, and the review rates are assumed to carry over.
  R4 Selection check: tilt-defined share in the 148 modelled crashes vs the other crash-rated logs (Fisher, two-sided).

    python research/px4_log_study/archive_label_audit.py fetch DATA_ROOT
    python research/px4_log_study/archive_label_audit.py analyze DATA_ROOT
"""
import csv
import gzip
import json
import os
import sys
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from math import comb

import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)
import postcrash_audit as pca
from r16_audit import crash_status

RESULTS_DIR = os.path.join(SCRIPT_DIR, "..", "results", "px4_log_study")
CRASH = ("crash_sw_hw", "crash_pilot")


def population(root):
    raw = open(os.path.join(root, "dbinfo.json"), "rb").read()
    db = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
    return [x for x in db if x.get("rating") in CRASH and "SITL" not in str(x.get("sys_hw"))]


def fetch(root):
    pop = population(root)
    have = set(pca.ulg_paths(root))
    todo = [x for x in pop if x["log_id"] not in have]
    out_dir = os.path.join(root, "archive_crash")
    os.makedirs(out_dir, exist_ok=True)

    def get(x):
        dest = os.path.join(out_dir, x["log_id"] + ".ulg")
        for _ in range(3):
            try:
                urllib.request.urlretrieve(x["download_url"], dest + ".part")
                os.replace(dest + ".part", dest)
                return True
            except Exception:
                pass
        return False

    with ThreadPoolExecutor(6) as ex:
        ok = list(ex.map(get, todo))
    print(f"downloaded {sum(ok)} of {len(todo)}")


def fisher_two_sided(a, b, c, d):
    """2x2 [[a, b], [c, d]]; sum of probabilities <= observed (hypergeometric)."""
    n1, n2, k, n = a + b, c + d, a + c, a + b + c + d
    pr = lambda x: comb(n1, x) * comb(n2, k - x) / comb(n, k)
    obs = pr(a)
    return float(sum(pr(x) for x in range(max(0, k - n2), min(n1, k) + 1) if pr(x) <= obs * (1 + 1e-9)))


def rotary_flag(path):
    from pyulog import ULog
    from pilot_vs_drone import topic
    try:
        st = topic(ULog(path, message_name_filter_list=["vehicle_status"]), "vehicle_status")
        return bool(st["is_rotary_wing"][-1]) if st is not None and "is_rotary_wing" in st else None
    except Exception:
        return None


def analyze(root):
    pop = population(root)
    paths = pca.ulg_paths(root)
    ids = [x["log_id"] for x in pop]
    status = crash_status(paths, [i for i in ids if i in paths])
    for i in ids:
        status.setdefault(i, "unreadable")
    rotary = {i: rotary_flag(paths[i]) if i in paths else None for i in ids}
    meta = {x["log_id"]: x for x in pop}
    tilt = lambda i: status[i] in ("confirmed", "tilt_unconfirmed")

    def shares(sel):
        c = Counter(status[i] for i in sel)
        return {"n": len(sel), **dict(c)}

    rot = [i for i in ids if rotary[i]]
    out = {"population": len(ids), "on_disk": sum(i in paths for i in ids), "R1_all": shares(ids), "R1_rotary": shares(rot)}

    def split(groups):
        res = {g: shares(sel) for g, sel in groups.items()}
        if len(groups) == 2:
            (g1, s1), (g2, s2) = groups.items()
            s1 = [i for i in s1 if status[i] != "unreadable"]
            s2 = [i for i in s2 if status[i] != "unreadable"]
            a, b = sum(map(tilt, s1)), sum(not tilt(i) for i in s1)
            c, d = sum(map(tilt, s2)), sum(not tilt(i) for i in s2)
            res["fisher_p_tilt"] = fisher_two_sided(a, b, c, d)
        return res

    out["R2_rating"] = split({r: [i for i in rot if meta[i]["rating"] == r] for r in CRASH})
    year = lambda i: int(str(meta[i].get("log_date") or "0")[:4] or 0)
    out["R2_year"] = split({"<=2019": [i for i in rot if year(i) <= 2019], "2020-2022": [i for i in rot if 2020 <= year(i) <= 2022],
                            ">=2023": [i for i in rot if year(i) >= 2023]})

    def ver(i):
        rel = (meta[i].get("ver_sw_release") or "").split(" ")[0].lstrip("v").split(".")
        try:
            return "<1.12" if (int(rel[0]), int(rel[1])) < (1, 12) else ">=1.12"
        except (ValueError, IndexError):
            return "unknown"

    out["R2_version"] = split({v: [i for i in rot if ver(i) == v] for v in ("<1.12", ">=1.12", "unknown")})
    # R3
    review = list(csv.DictReader(open(os.path.join(RESULTS_DIR, "crash_moment_review.csv"))))
    rstat = crash_status(paths, [r["log_id"] for r in review])
    contains = {"correct": 1, "too early": 1, "too late": 1, "no crash visible": 0}
    lab = {"tilt": [], "fallback": []}
    for r in review:
        v = contains.get(r["reviewer_2"].strip())
        if v is None or rstat[r["log_id"]] == "unreadable":
            continue
        lab["tilt" if rstat[r["log_id"]] in ("confirmed", "tilt_unconfirmed") else "fallback"].append(v)
    readable = [i for i in rot if status[i] != "unreadable"]
    arch = np.array([1 if tilt(i) else 0 for i in readable])
    est = lambda a, lt, lf: a.mean() * np.mean(lt) + (1 - a.mean()) * np.mean(lf)
    point = est(arch, lab["tilt"], lab["fallback"])
    rng = np.random.default_rng(2045)
    boot = [est(rng.choice(arch, len(arch)), rng.choice(lab["tilt"], len(lab["tilt"])), rng.choice(lab["fallback"], len(lab["fallback"])))
            for _ in range(2000)]
    out["R3"] = {"readable_rotary": len(readable), "share_tilt": float(arch.mean()),
                 "review_contains_given_tilt": [int(sum(lab["tilt"])), len(lab["tilt"])],
                 "review_contains_given_fallback": [int(sum(lab["fallback"])), len(lab["fallback"])],
                 "estimated_share_containing_crash": float(point),
                 "ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]}
    # R4
    leak = {json.loads(l)["log"] for l in open(os.path.join(RESULTS_DIR, "leak_curve_features.jsonl")) if json.loads(l)["group"] == "crash"}
    out["R4_selection"] = split({"modelled": [i for i in rot if i in leak], "other": [i for i in rot if i not in leak]})
    json.dump(out, open(os.path.join(RESULTS_DIR, "archive_label_audit.json"), "w"), indent=1, default=float)
    open(os.path.join(RESULTS_DIR, "archive_label_audit.md"), "w").write(
        "# Archive-wide label audit\n\nDeclared in `research/px4_log_study/archive_label_audit.py`. Exploratory (dagger).\n\n```\n"
        + json.dumps(out, indent=1, default=float) + "\n```\n")
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    {"fetch": fetch, "analyze": analyze}[sys.argv[1]](sys.argv[2] if len(sys.argv) > 2 else "/Volumes/One Touch/AeroFleet_px4_data")
