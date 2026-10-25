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
    # Fixed subset of flights with duration >= 40 s present across all margins m in [0, 2, 5, 10, 20, 30] s
    # 89 crashes and 124 normal flights (n = 213 total logs across all cut-offs)
    fixed_data = [
        (0, 0.895, 0.007, 0.450, 0.015),
        (2, 0.876, 0.007, 0.449, 0.024),
        (5, 0.873, 0.006, 0.451, 0.023),
        (10, 0.868, 0.007, 0.449, 0.022),
        (20, 0.862, 0.008, 0.464, 0.025),
        (30, 0.864, 0.006, 0.458, 0.034),
    ]
    m_, a, asd, b, bsd = (np.array(c) for c in zip(*fixed_data))
    fig, ax = plt.subplots(figsize=(4.4, 2.9))
    ax.errorbar(m_, a, yerr=asd, marker="o", color=BLUE, capsize=3, label="Crash vs normal (n=213)")
    ax.errorbar(m_, b, yerr=bsd, marker="s", color=RED, capsize=3, label="Pilot vs aircraft (n=89)")
    ax.axhline(0.5, color=GREY, lw=0.8, ls="--")
    ax.text(30, 0.515, "chance", color=GREY, ha="right", fontsize=8)
    ax.set_xlabel("Seconds removed before the crash moment")
    ax.set_ylabel("Cross-validated ROC AUC")
    ax.set_ylim(0.35, 1.0)
    ax.legend(frameon=False, loc="center right", fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=300, bbox_inches="tight", pad_inches=0.1)
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
    fig, ax = plt.subplots(figsize=(5.0, 2.8))
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
    fig.savefig(out, dpi=300, bbox_inches="tight", pad_inches=0.1)
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
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)


def study_flow(out):
    """Sample flow from the archive to each analysis with explicit exclusions and attrition."""
    fig, ax = plt.subplots(figsize=(7.8, 4.6))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    def box(x, y, w, h, text, fc="#EEF3F8", fs=6.2, bold=False):
        ax.add_patch(plt.Rectangle((x, y), w, h, fc=fc, ec=BLUE, lw=0.8))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=INK, fontweight="bold" if bold else "normal",
                linespacing=1.2)

    def arrow(x0, y0, x1, y1, col=GREY):
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle="->", color=col, lw=0.7))

    box(0.28, 0.85, 0.44, 0.12, "PX4 Flight Review public archive index\n479,547 logs (442,929 real hardware; 38,320 vehicles)", fc="#DCE7F2", bold=True, fs=6.8)
    box(0.01, 0.60, 0.31, 0.14, "Uploader crash ratings\n590 logs: 402 aircraft, 188 pilot\n(520 real hardware, duration >= 10s)", fs=6.3)
    box(0.35, 0.60, 0.29, 0.14, "Normal-flight comparison pool\nRatings 'good' or 'great'\n(477 selected for exposure baselines)", fs=6.3)
    box(0.67, 0.60, 0.32, 0.14, "PX4 forum threads linking a log\n443 found, 410 with link, 161 diagnosed\n(148 real crash threads; 94 aircraft, 9 pilot)", fs=6.3)

    for x in (0.165, 0.495, 0.83):
        arrow(0.50, 0.85, x, 0.74)

    w, gap = 0.153, 0.012
    items = [
        "Q1 Settings\n100 crash, 477 normal\nExclusion: 43% lack defaults\n-> 57 crash, 113 normal",
        "Q2 Rule\n205 crashes, 143 normal\n(93 dev + 112 held-out)\nNo feature exclusions\n-> 205 crashes evaluated",
        "Q2/Q3a Model\n205 crashes -> 57 dropped\n(unreadable or duration < 10s)\n-> 148 crash, 139 normal (m=0)\n-> 89 crash, 124 normal (m=30)",
        "Q3b Within-drone\n101 crashed drones\n34 dropped (<10s / 1 flight)\n-> 67 multi-flight drones (372 fl.)\n-> 61 vib., 46 tracking sets",
        "Q3c Between-drone\n66 matched sets (101 cases)\n6 dropped (unmatched source)\n-> 60 vibration sets (48 old, 12 new)\n-> 47 tracking sets",
        "Q4 Experts\n148 real crash threads\n110 logs broken / expired\n-> 38 downloadable logs (all ac.)\n-> 30 with complete features"
    ]
    xs = [0.01 + i * (w + gap) for i in range(6)]
    for x, t in zip(xs, items):
        box(x, 0.13, w, 0.35, t, fc="white", fs=5.6)

    for x in xs[:5]:
        arrow(0.165, 0.60, x + w * 0.35, 0.48, BLUE)
    for x in xs[:3]:
        arrow(0.495, 0.60, x + w * 0.65, 0.48)
    arrow(0.83, 0.60, xs[5] + w / 2, 0.48)

    ax.text(0.5, 0.04, "Sample flow with explicit exclusions and attrition across confirmatory analyses. Declared protocols committed to version control in advance.",
            ha="center", fontsize=6.3, color=GREY, style="italic")
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)


def sign_rates(out):
    rows = []
    for line in open(os.path.join(RES, "holdout.md")):
        m = re.match(r"\| (D_\w+) \| (\d+) of (\d+) .*?\| (\d+) of (\d+) .*?\| (\d+) of (\d+)", line)
        if m:
            g = m.groups()
            rows.append((g[0], *(int(a) / max(1, int(b)) * 100 for a, b in ((g[1], g[2]), (g[3], g[4]), (g[5], g[6])))))
    names = {"D_BATT": "Battery warning", "D_MOTOR": "Motor at ≥95%", "D_CLIP": "Accel. clipping", "D_GPS": "Poor GPS",
             "D_FD": "Failure detector", "D_ERR": "Error message", "D_CPU": "CPU overload", "D_FAILSAFE": "Failsafe"}
    rows = [r for r in rows if r[0] not in ("D_FD", "D_CPU")]
    y = np.arange(len(rows))
    fig, ax = plt.subplots(figsize=(4.6, 2.9))
    for k, (lab, col) in enumerate((("Aircraft-caused crashes", BLUE), ("Pilot-caused crashes", RED), ("Normal flights", GREY))):
        ax.barh(y + (k - 1) * 0.26, [r[k + 1] for r in rows], height=0.25, color=col, label=lab)
    ax.set_yticks(y)
    ax.set_yticklabels([names[r[0]] for r in rows], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("Share of logs in which the sign fired (%)")
    ax.legend(frameon=False, fontsize=7.5, loc="upper center", bbox_to_anchor=(0.45, -0.22), ncol=3)
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)


def robustness(out):
    rows = []
    for line in open(os.path.join(RES, "sensitivity.md")):
        m = re.match(r"\| (As declared.*?|S\d .*?) \| (\d+) \| ([\d.]+) \| ([\d.]+) \|", line)
        if m:
            rows.append((m.group(1), int(m.group(2)), float(m.group(3)), float(m.group(4))))
        m2 = re.search(r"(\d+) matched sets, mean scaled rank ([\d.]+), one-sided p = (\d+\.\d+)", line)
        if m2:
            rows.append(("S8 vibration adjusted for flight duration", int(m2.group(1)), float(m2.group(2)), float(m2.group(3))))
    y = np.arange(len(rows))
    fig, ax = plt.subplots(figsize=(5.0, 2.6))
    ax.scatter([r[2] for r in rows], y, color=[BLUE if r[3] < 0.025 else GREY for r in rows], zorder=3)
    for i, r in enumerate(rows):
        ptxt = "p<0.001" if r[3] < 0.001 else f"p={r[3]:.3f}"
        ax.text(r[2] + 0.015, i, f"n={r[1]}, {ptxt}", va="center", fontsize=7)
    ax.axvline(0.5, color=GREY, lw=0.8, ls="--")
    ax.set_yticks(y)
    ax.set_yticklabels([r[0].replace("As declared (all controls, all sources)", "Declared test") for r in rows], fontsize=7)
    ax.invert_yaxis()
    ax.set_xlim(0.4, 1.0)
    ax.set_xlabel("Mean scaled rank of the crashed drone (vibration; 0.5 = no difference)", fontsize=8)
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    out_dir = sys.argv[1]
    os.makedirs(out_dir, exist_ok=True)
    leak_curve(os.path.join(out_dir, "fig_leak_curve.png"))
    within_between(os.path.join(out_dir, "fig_within_between.png"))
    forum_causes(os.path.join(out_dir, "fig_forum_causes.png"))
    study_flow(os.path.join(out_dir, "fig_study_flow.png"))
    sign_rates(os.path.join(out_dir, "fig_sign_rates.png"))
    robustness(os.path.join(out_dir, "fig_robustness.png"))
    for f, fn in (("vib_p95", _within_ranks), ("tune_rms", _within_ranks)):
        print("within", f, np.round(_ci(fn(f)), 3), len(fn(f)))
    for f in ("vib_p95", "tune_rms"):
        print("between", f, np.round(_ci(_between_ranks(f)), 3), len(_between_ranks(f)))
