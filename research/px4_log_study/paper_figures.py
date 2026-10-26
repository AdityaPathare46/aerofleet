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
    # Replace SD bars with 95% bootstrap confidence intervals (1.96 * SE)
    a_ci = 1.96 * asd
    b_ci = 1.96 * bsd
    fig, ax = plt.subplots(figsize=(4.4, 2.9))
    ax.errorbar(m_, a, yerr=a_ci, marker="o", color=BLUE, capsize=3, label="Crash vs normal (n=213)")
    ax.errorbar(m_, b, yerr=b_ci, marker="s", color=RED, capsize=3, label="Pilot vs aircraft (n=89)")
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
    fig, ax = plt.subplots(figsize=(5.6, 3.1))
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
    ax.set_xlabel("Mean scaled rank of the crashed drone\n(0.5 = no difference; bars: 95% bootstrap CI)", fontsize=8.0)
    fig.tight_layout()
    fig.savefig(out, dpi=300, bbox_inches="tight", pad_inches=0.25)
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
    fig = plt.figure(figsize=(9.8, 6.4), dpi=300)
    gs = fig.add_gridspec(2, 1, height_ratios=[1.05, 1.25], hspace=0.18)
    ax_flow = fig.add_subplot(gs[0])
    ax_tab = fig.add_subplot(gs[1])

    ax_flow.set_xlim(0, 1)
    ax_flow.set_ylim(0, 1)
    ax_flow.axis("off")
    ax_tab.axis("off")

    def draw_box(ax, x, y, w, h, title, subtext, fc="#F0F5FA", ec=BLUE, lw=1.0, bold_title=True):
        ax.add_patch(plt.Rectangle((x, y), w, h, fc=fc, ec=ec, lw=lw, zorder=2))
        ax.text(x + w / 2, y + h * 0.62, title, ha="center", va="center", fontsize=7.5, color=INK,
                fontweight="bold" if bold_title else "normal", zorder=3)
        ax.text(x + w / 2, y + h * 0.28, subtext, ha="center", va="center", fontsize=6.2, color="#334155",
                linespacing=1.15, zorder=3)

    def draw_arrow(ax, x0, y0, x1, y1, col=GREY):
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="->", color=col, lw=0.9, shrinkA=0, shrinkB=0), zorder=1)

    draw_box(ax_flow, 0.22, 0.72, 0.56, 0.26,
             "PX4 Flight Review Public Archive Index",
             "479,547 total logs | 442,929 real hardware | 38,320 distinct vehicles",
             fc="#DCE8F5", ec=BLUE, lw=1.2)

    draw_box(ax_flow, 0.02, 0.15, 0.30, 0.40,
             "Crash-Rated Flight Logs",
             "590 rated logs (402 aircraft, 188 pilot)\n520 real hardware with duration \u2265 10 s\n(from 284 distinct airframes)",
             fc="#F0F5FA", ec=BLUE)

    draw_box(ax_flow, 0.35, 0.15, 0.30, 0.40,
             "Normal Comparison Flights",
             "21,112 logs rated good/great\n477 selected for exposure baselines\nMatched on firmware, controller & airframe",
             fc="#F0F5FA", ec=BLUE)

    draw_box(ax_flow, 0.68, 0.15, 0.30, 0.40,
             "PX4 Forum Crash Threads",
             "443 candidate threads found\n161 diagnosed | 148 real crash discussions\n(94 aircraft-fault, 9 pilot-fault)",
             fc="#F0F5FA", ec=BLUE)

    draw_arrow(ax_flow, 0.36, 0.72, 0.17, 0.55)
    draw_arrow(ax_flow, 0.50, 0.72, 0.50, 0.55)
    draw_arrow(ax_flow, 0.64, 0.72, 0.83, 0.55)

    table_data = [
        ["Q1: Parameters", "100 crash, 477 normal", "43% crash logs lack factory defaults", "57 crash, 113 normal"],
        ["Q2: Fixed Rule", "205 crashes, 143 normal", "None (evaluates 93 dev + 112 held-out)", "205 crashes, 143 normal"],
        ["Q2/Q3a: Leak Curve", "205 crashes, 143 normal", "57 dropped (missing topics / dur. < 10 s)", "148 crash, 139 normal (m=0 s)\n89 crash, 124 normal (m=30 s)"],
        ["Q3b: Within-Drone", "101 crashed drones", "34 dropped (single flight / dur. < 10 s)", "67 multi-flight drones (372 fl.)\n61 vibration, 46 tracking"],
        ["Q3c: Between-Drone", "66 matched sets (101 cases)", "6 sets dropped (unmatched sensor metric)", "60 vibration sets (124 ctrl, 372 fl.)\n47 rate-tracking sets"],
        ["Q4: Expert Cases", "148 real crash threads", "105 logs unhosted or expired links", "43 downloadable (38 aircraft, 5 pilot)\n35 aircraft with fault categories"],
    ]

    headers = ["Analysis Stream", "Initial Candidate Pool", "Exclusions & Attrition", "Analyzed Sample Size"]
    col_widths = [0.20, 0.22, 0.32, 0.26]
    tab = ax_tab.table(cellText=table_data, colLabels=headers, colWidths=col_widths, bbox=[0.02, 0.02, 0.96, 0.96], cellLoc="left")
    tab.auto_set_font_size(False)
    tab.set_fontsize(6.3)

    for (row, col), cell in tab.get_celld().items():
        cell.set_edgecolor("#CBD5E1")
        cell.set_linewidth(0.6)
        if row == 0:
            cell.set_facecolor("#E2E8F0")
            cell.set_text_props(weight="bold", color=INK, ha="left")
            cell.set_height(0.12)
        else:
            cell.set_height(0.14)
            if row % 2 == 1:
                cell.set_facecolor("#FFFFFF")
            else:
                cell.set_facecolor("#F8FAFC")
            if col == 0:
                cell.set_text_props(weight="semibold", color="#1E3A8A")

    fig.savefig(out, dpi=300, bbox_inches="tight", pad_inches=0.25)
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
    rows = [
        ("Declared test (all controls, all sources)", 60, 0.67, 0.0023),
        ("S1 controls with same airframe", 39, 0.69, 0.0079),
        ("S2 no case flights from crash day", 25, 0.76, 0.0027),
        ("S3 older-firmware estimator metric only", 48, 0.68, 0.0047),
        ("S3 newer accel. metric (exploratory subset)", 12, 0.62, 0.1914),
        ("S8 vibration adjusted for flight duration", 57, 0.69, 0.0005),
        ("Newer accel. metric replication (all usable)", 19, 0.58, 0.2512),
        ("Newer accel. metric replication (new cases)", 10, 0.50, 0.5760),
    ]
    y = np.arange(len(rows))
    fig, ax = plt.subplots(figsize=(6.0, 3.6), dpi=300)
    colors = [BLUE if r[3] < 0.025 else GREY for r in rows]
    ax.scatter([r[2] for r in rows], y, color=colors, s=35, zorder=3)
    for i, r in enumerate(rows):
        ptxt = "p<0.001" if r[3] < 0.001 else f"p={r[3]:.3f}"
        ax.text(r[2] + 0.012, i, f"n={r[1]}, {ptxt}", va="center", fontsize=7.2, color=INK)
    ax.axvline(0.5, color=GREY, lw=0.8, ls="--")
    ax.text(0.503, -0.4, "chance (0.50)", color=GREY, fontsize=7.2, ha="left", va="bottom")
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=7.2)
    ax.invert_yaxis()
    ax.set_ylim(len(rows) - 0.4, -0.8)
    ax.set_xlim(0.40, 0.95)
    ax.set_xlabel("Mean scaled rank of the crashed drone (vibration; 0.5 = no difference)", fontsize=8.0)
    fig.tight_layout()
    fig.savefig(out, dpi=300, bbox_inches="tight", pad_inches=0.20)
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
