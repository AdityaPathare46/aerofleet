"""Figures for the paper, from the committed result files only (no logs needed).

    python3 research/px4_log_study/paper_figures.py OUT_DIR
"""
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "results", "px4_log_study")
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
INK, BLUE, RED, GREY = "#13202E", "#0E5A9C", "#B42318", "#8A97A8"


def leak_curve(out):
    rows = []
    for line in open(os.path.join(RES, "leak_curve.md")):
        m = re.match(r"\| (\d+) \| .*? \| ([\d.]+) ± ([\d.]+) \| .*? \| ([\d.]+) ± ([\d.]+) \|", line)
        if m:
            rows.append(tuple(float(x) for x in m.groups()))
    m_, a, asd, b, bsd = (np.array(c) for c in zip(*rows))
    fig, ax = plt.subplots(figsize=(4.2, 2.8))
    ax.errorbar(m_, a, yerr=asd, marker="o", color=BLUE, capsize=3, label="Crash vs normal flight")
    ax.errorbar(m_, b, yerr=bsd, marker="s", color=RED, capsize=3, label="Pilot- vs drone-blamed crash")
    ax.axhline(0.5, color=GREY, lw=0.8, ls="--")
    ax.text(30, 0.515, "chance", color=GREY, ha="right", fontsize=8)
    ax.set_xlabel("Seconds removed before the crash moment")
    ax.set_ylabel("Cross-validated ROC AUC")
    ax.set_ylim(0.35, 1.0)
    ax.legend(frameon=False, loc="center right", fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=300)
    plt.close(fig)


def _within_ranks(feature):
    rows = [json.loads(line) for line in open(os.path.join(RES, "within_drone_features.jsonl"))]
    src = {"vib_p95": "src_vib", "tune_rms": "src_tune"}[feature]
    crash = {r["crash_id"]: r for r in rows if r["role"] == "crash" and r["features"]}
    ranks = []
    for cid, c in crash.items():
        cv = c["features"].get(feature)
        ev = [r["features"][feature] for r in rows if r["role"] == "earlier" and r["crash_id"] == cid and r["features"]
              and r["features"].get(feature) is not None and r["features"].get(src) == c["features"].get(src)]
        if cv is not None and len(ev) >= 3:
            ranks.append(sum(v < cv for v in ev) / len(ev))
    return np.array(ranks)


def _between_ranks(feature):
    rows = [json.loads(line) for line in open(os.path.join(RES, "rough_drone_features.jsonl"))]
    src = {"vib_p95": "src_vib", "tune_rms": "src_tune"}[feature]
    sets = defaultdict(lambda: defaultdict(list))
    role = {}
    for r in rows:
        sets[r["set_id"]][r["vehicle"]].append(r)
        role[(r["set_id"], r["vehicle"])] = r["role"]

    def value(rs):
        vals = defaultdict(list)
        for r in rs:
            f = r["features"]
            if f and f.get(feature) is not None:
                vals[f.get(src)].append(f[feature])
        return {s: float(np.median(v)) for s, v in vals.items() if len(v) >= 2}

    ranks = []
    for sid, vehicles in sets.items():
        case = [v for v in vehicles if role[(sid, v)] == "case"]
        if not case:
            continue
        for s, cv in value(vehicles[case[0]]).items():
            ctrl = [value(vehicles[v]).get(s) for v in vehicles if role[(sid, v)] == "control"]
            ctrl = [x for x in ctrl if x is not None]
            if ctrl:
                ranks.append(sum(x < cv for x in ctrl) / len(ctrl))
            break
    return np.array(ranks)


def _ci(x, rng=np.random.default_rng(0), n=10000):
    boots = rng.choice(x, (n, len(x))).mean(1)
    return x.mean(), np.percentile(boots, 2.5), np.percentile(boots, 97.5)


def within_between(out):
    fig, ax = plt.subplots(figsize=(4.4, 2.8))
    labels, ys = [], []
    for i, (design, fn) in enumerate((("Same drone, earlier flights", _within_ranks), ("Matched drones that did not crash", _between_ranks))):
        for j, (feat, name) in enumerate((("vib_p95", "Vibration"), ("tune_rms", "Rate-tracking error"))):
            r = fn(feat)
            m, lo, hi = _ci(r)
            y = i * 2.6 + j
            ax.errorbar(m, y, xerr=[[m - lo], [hi - m]], fmt="o", color=BLUE if j == 0 else RED, capsize=3)
            ax.text(1.0, y, f"n={len(r)}", va="center", ha="right", fontsize=8, color=GREY)
            labels.append(f"{name}\nvs {design.lower()}")
            ys.append(y)
    ax.axvline(0.5, color=GREY, lw=0.8, ls="--")
    ax.set_yticks(ys)
    ax.set_yticklabels(labels, fontsize=7.5)
    ax.set_xlim(0, 1.0)
    ax.invert_yaxis()
    ax.set_xlabel("Mean scaled rank of the crashed drone\n(0.5 = no difference; bars: 95% bootstrap CI)")
    fig.tight_layout()
    fig.savefig(out, dpi=300)
    plt.close(fig)


def forum_causes(out):
    rows = list(csv.DictReader(open(os.path.join(RES, "forum_expert_labels.csv"))))
    drone = [r for r in rows if r["is_crash"] == "yes" and r["expert_conclusion"] == "drone"]
    allc, conf = Counter(r["cause"] for r in drone), Counter(r["cause"] for r in drone if r["poster_confirmed"] == "yes")
    causes = [c for c, _ in allc.most_common()]
    y = np.arange(len(causes))
    fig, ax = plt.subplots(figsize=(4.4, 2.8))
    ax.barh(y, [allc[c] for c in causes], color="#C9D7E6", label=f"All aircraft-fault diagnoses (n={len(drone)})")
    ax.barh(y, [conf[c] for c in causes], color=BLUE, label=f"Confirmed by the poster (n={sum(conf.values())})")
    ax.set_yticks(y)
    ax.set_yticklabels(causes, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("PX4 forum crash threads")
    ax.legend(frameon=False, fontsize=7.5, loc="lower right")
    fig.tight_layout()
    fig.savefig(out, dpi=300)
    plt.close(fig)


if __name__ == "__main__":
    out_dir = sys.argv[1]
    os.makedirs(out_dir, exist_ok=True)
    leak_curve(os.path.join(out_dir, "fig_leak_curve.png"))
    within_between(os.path.join(out_dir, "fig_within_between.png"))
    forum_causes(os.path.join(out_dir, "fig_forum_causes.png"))
    for f, fn in (("vib_p95", _within_ranks), ("tune_rms", _within_ranks)):
        print("within", f, np.round(_ci(fn(f)), 3), len(fn(f)))
    for f in ("vib_p95", "tune_rms"):
        print("between", f, np.round(_ci(_between_ranks(f)), 3), len(_between_ranks(f)))
