"""Round 21 audit: re-evaluation of a published trained fault detector, two more reports on the injected-fault control,
the third rater by aircraft type, and the rule on decided multicopter crashes.

PRE-DECLARED (committed and pushed before this script is run). Status: exploratory (dagger), declared after the
twenty-first internal review; not blind: all earlier results are known. No model below has been trained or scored.

PART A - A published trained detector under this study's protocol (the review's open originality item)
  The detector: the RflyMAD authors' fault-diagnosis network (Le et al., IJRR 2025, and the dataset site's "supplementary
  experiments based on transfer learning"): an improved LeNet-5 convolutional network on 12 flight signals (velocity,
  angular velocity, acceleration and Euler angles, three axes each), trained for 10 epochs; the authors report 98.2%
  accuracy on real single-motor faults in hover (SIL + 10% real data) and 89.7-99.1% across settings. No code or weights
  were released, so this is a RE-IMPLEMENTATION from the published description; choices the description leaves open are
  fixed here before any training:
    signals  vehicle_local_position vx, vy, vz; vehicle_angular_velocity xyz[0..2]; vehicle_acceleration xyz[0..2];
             roll, pitch, yaw from vehicle_attitude; linearly resampled to 10 Hz over the airborne armed period
             (take-off and armed period as rflymad_eval.score_one);
    window   32 samples (3.2 s), non-overlapping; per-channel standardisation fitted on the training fold only;
    network  1-D LeNet-5 over time with 12 input channels: Conv(12->6, k5)+BN+ReLU+MaxPool2, Conv(6->16, k5)+BN+ReLU
             +MaxPool2, FC 80->120->84->2; Adam (lr 1e-3), batch 64, 10 epochs, cross-entropy; torch seed = fold seed.
  Data: RflyMAD real flights as rflymad_eval (same exclusions): the 240 motor-fault flights and the 51 fault-free flights.
  A window is FAULT if it lies wholly between the injection and the end of the fault (rfly_ctrl_lxl), PRE if it lies
  wholly before the injection; fault-free flights give NORMAL windows, split into before and after the pseudo-onset of
  rflymad_eval (same rule).
  Conditions (metric: window-level accuracy at 0.5 and AUC; 5 seeds 0-4 unless stated):
    A1 as published: FAULT vs NORMAL windows, random 80/20 window split (windows of one flight can fall on both sides);
    A2 the same task, 5-fold cross-validation grouped by flight;
    A3 the same task, 5-fold grouped by flight day (from the log name);
    A4 known-cause control: PRE windows of fault flights (label 1) vs NORMAL windows before the pseudo-onset (label 0),
       grouped by flight: no fault exists in either class;
    A5 A4 grouped by flight day.
  For A2-A5: 100 label permutations at flight level (labels shuffled across flights, seed 2140) for p; flight-level
  bootstrap (2,000, seed 2141) for the A1 - A3 AUC difference.
  Wording rules (fixed now): the published accuracy is "reproduced on a random window split" if A1 accuracy >= 0.90;
  the split "inflates" the detector if A1 AUC - A3 AUC >= 0.05 with an interval excluding zero; the detector "separates
  fault flights with no fault present" if A4 AUC >= 0.70 with permutation p < 0.05.

PART B - Injected-fault control: two more reports (review problem 4)
  B1 With the day-grouped folds of r20_audit A (same model, seeds 42-46, seed-averaged out-of-fold scores), AUC within
     each of the four days that contain fault-free flights, for the pre, fault and whole windows, and their size-weighted
     mean.
  B2 Why the day-grouped whole-flight AUC (0.538) is lower than the pre-fault one: per class, the median window length
     (s) of the pre and whole windows, and the share of whole windows longer than 120 s. Descriptive.

PART C - Third rater by aircraft type (review problem 7): the third rater's "correct" counts by index aircraft type and
  crash status (as r19_audit A1 does for the first two reviewers).

PART D - The rule on decided multicopter crashes (review problem 8): balanced accuracy of the declared rule on multicopter
  crashes whose verdict is not "unknown", held-out and modelled sets, with bootstrap intervals (2,000, seed 2142), and the
  number undecided.

Outputs: research/results/px4_log_study/r21_audit.md and .json.

    PYTHONPATH=. ~/.venvs/torch/bin/python research/px4_log_study/r21_audit.py DATA_ROOT RFLYMAD_DIR
"""
import csv
import gzip
import json
import os
import re
import sys
from collections import Counter, defaultdict

import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)
import factorial_audit as fa

RESULTS_DIR = os.path.join(SCRIPT_DIR, "..", "results", "px4_log_study")
MULTI = ("Quadrotor", "Hexarotor", "Octorotor")
HZ, WIN = 10, 32


def jsonl(name):
    return [json.loads(l) for l in open(os.path.join(RESULTS_DIR, name))]


def boot_ci(vals):
    vals = [v for v in vals if v == v]
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


# ---------------------------------------------------------------- A: signals and windows

def signals(path):
    from pyulog import ULog
    want = ["vehicle_local_position", "vehicle_angular_velocity", "vehicle_acceleration", "vehicle_attitude"]
    u = ULog(path, message_name_filter_list=want)
    d = {x.name: x.data for x in u.data_list if x.multi_id == 0}
    if any(w not in d for w in want):
        return None
    lp, av, ac, at = (d[w] for w in want)
    q0, q1, q2, q3 = at["q[0]"], at["q[1]"], at["q[2]"], at["q[3]"]
    roll = np.arctan2(2 * (q0 * q1 + q2 * q3), 1 - 2 * (q1 ** 2 + q2 ** 2))
    pitch = np.arcsin(np.clip(2 * (q0 * q2 - q3 * q1), -1, 1))
    yaw = np.arctan2(2 * (q0 * q3 + q1 * q2), 1 - 2 * (q2 ** 2 + q3 ** 2))
    return [(lp["timestamp"], lp["vx"]), (lp["timestamp"], lp["vy"]), (lp["timestamp"], lp["vz"]),
            (av["timestamp"], av["xyz[0]"]), (av["timestamp"], av["xyz[1]"]), (av["timestamp"], av["xyz[2]"]),
            (ac["timestamp"], ac["xyz[0]"]), (ac["timestamp"], ac["xyz[1]"]), (ac["timestamp"], ac["xyz[2]"]),
            (at["timestamp"], roll), (at["timestamp"], pitch), (at["timestamp"], np.unwrap(yaw))]


def windows_for(row, root):
    """Returns list of (window array 32x12, kind) with kind in FAULT, PRE, NORMAL_PRE, NORMAL_POST."""
    path = os.path.join(root, row["path"])
    sig = signals(path)
    if sig is None:
        return []
    t0, t_end = row["t0"], row["t_end"]
    grid = np.arange(t0, t_end, 1e6 / HZ)
    X = np.stack([np.interp(grid, t, v) for t, v in sig], axis=1).astype(np.float32)
    out = []
    for k in range(len(grid) // WIN):
        a, b = grid[k * WIN], grid[(k + 1) * WIN - 1]
        w = X[k * WIN:(k + 1) * WIN]
        if row["cls"] == "motor":
            if a >= row["t_f"] and b <= row["t_f_end"]:
                out.append((w, "FAULT"))
            elif b < row["t_f"]:
                out.append((w, "PRE"))
        else:
            out.append((w, "NORMAL_PRE" if b < row["pseudo"] else "NORMAL_POST"))   # a window straddling the pseudo-onset counts as POST
    return out


def load_rflymad(rdir):
    R = [json.loads(l) for l in open(os.path.join(RESULTS_DIR, "rflymad_scores.jsonl"))]
    keep = [r for r in R if "error" not in r and not (r["cls"] != "no_fault" and r["t_f"] is None)
            and not (r["cls"] == "no_fault" and r["t_f"] is not None)]
    off = defaultdict(list)
    for r in keep:
        if r["t_f"] is not None:
            off[r["status"]].append((r["t_f"] - r["t0"]) / 1e6)
    allo = [x for v in off.values() for x in v]
    rows = []
    for r in keep:
        if r["cls"] not in ("motor", "no_fault"):
            continue
        if r["t_f"] is None:
            s = min(max(int(round(np.median(off.get(r["status"]) or allo))), 10), 120)
            r["pseudo"] = r["t0"] + s * 1_000_000
        r["date"] = re.search(r"log_\d+_(\d{4}-\d+-\d+)", r["path"]).group(1)
        rows.append(r)
    data = []
    for r in rows:
        try:
            for w, kind in windows_for(r, rdir):
                data.append((w, kind, r["case"] + "|" + r["path"], r["date"]))
        except Exception:
            pass
    return data


# ---------------------------------------------------------------- A: model

def make_net():
    import torch.nn as nn
    return nn.Sequential(
        nn.Conv1d(12, 6, 5), nn.BatchNorm1d(6), nn.ReLU(), nn.MaxPool1d(2),
        nn.Conv1d(6, 16, 5), nn.BatchNorm1d(16), nn.ReLU(), nn.MaxPool1d(2),
        nn.Flatten(), nn.Linear(80, 120), nn.ReLU(), nn.Linear(120, 84), nn.ReLU(), nn.Linear(84, 2))


def train_predict(Xtr, ytr, Xte, seed):
    import torch
    torch.manual_seed(seed)
    mu, sd = Xtr.mean(axis=(0, 1)), Xtr.std(axis=(0, 1)) + 1e-6
    f = lambda X: torch.tensor(((X - mu) / sd).transpose(0, 2, 1), dtype=torch.float32)
    xtr, yt, xte = f(Xtr), torch.tensor(ytr, dtype=torch.long), f(Xte)
    net = make_net()
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    loss = torch.nn.CrossEntropyLoss()
    g = torch.Generator().manual_seed(seed)
    for _ in range(10):
        net.train()
        for idx in torch.randperm(len(yt), generator=g).split(64):
            if len(idx) < 2:
                continue
            opt.zero_grad()
            loss(net(xtr[idx]), yt[idx]).backward()
            opt.step()
    net.eval()
    with torch.no_grad():
        return torch.softmax(net(xte), 1)[:, 1].numpy()


def grouped_cv(X, y, groups, seed, k=5):
    uniq = sorted(set(groups))
    rng = np.random.default_rng(seed)
    rng.shuffle(uniq)
    fold = {g: i % k for i, g in enumerate(uniq)}
    f = np.array([fold[g] for g in groups])
    s = np.zeros(len(y))
    for i in range(k):
        te, tr = f == i, f != i
        if len(set(y[tr])) < 2 or te.sum() == 0:
            s[te] = 0.5
            continue
        s[te] = train_predict(X[tr], y[tr], X[te], seed * 10 + i)
    return s


def part_a(rdir):
    data = load_rflymad(rdir)
    kinds = Counter(k for _, k, _, _ in data)
    out = {"windows": dict(kinds), "flights": len({f for _, _, f, _ in data})}

    def task(pos, neg):
        sel = [(w, 1 if k in pos else 0, fl, d) for w, k, fl, d in data if k in pos or k in neg]
        X = np.stack([s[0] for s in sel])
        y = np.array([s[1] for s in sel])
        fl = [s[2] for s in sel]
        dy = [s[3] for s in sel]
        return X, y, fl, dy

    # A1 random window split
    X, y, fl, dy = task({"FAULT"}, {"NORMAL_PRE", "NORMAL_POST"})
    accs, aucs, a1_scores = [], [], []
    for seed in range(5):
        rng = np.random.default_rng(seed)
        idx = rng.permutation(len(y))
        cut = int(0.8 * len(y))
        tr, te = idx[:cut], idx[cut:]
        p = train_predict(X[tr], y[tr], X[te], seed)
        accs.append(float(np.mean((p > 0.5) == y[te])))
        aucs.append(fa.auc(y[te], p))
    out["A1_random_window_split"] = {"n_windows": int(len(y)), "n_fault": int(y.sum()), "accuracy": float(np.mean(accs)),
                                     "auc": float(np.mean(aucs)), "accuracy_by_seed": accs}
    print("A1", out["A1_random_window_split"], flush=True)

    def run(name, X, y, groups, flights):
        S = [grouped_cv(X, y, groups, seed) for seed in range(5)]
        s = np.mean(S, axis=0)
        res = {"n_windows": int(len(y)), "n_pos": int(y.sum()), "accuracy": float(np.mean([np.mean((x > 0.5) == y) for x in S])),
               "auc": float(np.mean([fa.auc(y, x) for x in S]))}
        # flight-level permutation
        fl_lab = {}
        for f_, yy in zip(flights, y):
            fl_lab[f_] = yy
        fls = sorted(fl_lab)
        rng = np.random.default_rng(2140)
        null = []
        for _ in range(100):
            perm = dict(zip(fls, rng.permutation([fl_lab[f_] for f_ in fls])))
            yp = np.array([perm[f_] for f_ in flights])
            null.append(fa.auc(yp, grouped_cv(X, yp, groups, 0)))
        res["perm_p"] = float((np.sum(np.array(null) >= res["auc"]) + 1) / 101)
        res["null_mean"] = float(np.mean(null))
        out[name] = res
        print(name, res, flush=True)
        return s

    sA2 = run("A2_grouped_by_flight", X, y, fl, fl)
    sA3 = run("A3_grouped_by_day", X, y, dy, fl)
    # A1 - A3 difference: flight-level bootstrap on A3 scores vs a refit A1 over all windows
    a1_all = np.zeros(len(y))
    for seed in range(5):
        rng = np.random.default_rng(seed)
        f = rng.integers(0, 5, len(y))
        for i in range(5):
            a1_all[f == i] += train_predict(X[f != i], y[f != i], X[f == i], seed * 10 + i) / 5
    by_fl = defaultdict(list)
    for i, f_ in enumerate(fl):
        by_fl[f_].append(i)
    fls = np.array(sorted(by_fl))
    rng = np.random.default_rng(2141)
    diffs = []
    for _ in range(2000):
        pick = [i for f_ in rng.choice(fls, len(fls)) for i in by_fl[f_]]
        diffs.append(fa.auc(y[pick], a1_all[pick]) - fa.auc(y[pick], sA3[pick]))
    out["A1_minus_A3"] = {"a1_window_cv_auc": fa.auc(y, a1_all), "a3_auc": fa.auc(y, sA3),
                          "diff": fa.auc(y, a1_all) - fa.auc(y, sA3), "ci": boot_ci(diffs)}
    X4, y4, fl4, dy4 = task({"PRE"}, {"NORMAL_PRE"})
    run("A4_pre_onset_grouped_by_flight", X4, y4, fl4, fl4)
    run("A5_pre_onset_grouped_by_day", X4, y4, dy4, fl4)
    a1, d = out["A1_random_window_split"], out["A1_minus_A3"]
    out["wording"] = {
        "published_accuracy_reproduced_random_split": a1["accuracy"] >= 0.90,
        "split_inflates": d["diff"] >= 0.05 and d["ci"][0] > 0,
        "separates_without_fault": out["A4_pre_onset_grouped_by_flight"]["auc"] >= 0.70 and out["A4_pre_onset_grouped_by_flight"]["perm_p"] < 0.05}
    return out


# ---------------------------------------------------------------- B

def part_b():
    R = [json.loads(l) for l in open(os.path.join(RESULTS_DIR, "rflymad_scores.jsonl"))]
    keep = [r for r in R if "error" not in r and not (r["cls"] != "no_fault" and r["t_f"] is None)
            and not (r["cls"] == "no_fault" and r["t_f"] is not None)]
    off = defaultdict(list)
    for r in keep:
        if r["t_f"] is not None:
            off[r["status"]].append((r["t_f"] - r["t0"]) / 1e6)
    allo = [x for v in off.values() for x in v]
    for r in keep:
        if r["t_f"] is None:
            s = min(max(int(round(np.median(off.get(r["status"]) or allo))), 10), 120)
            r["pre_len"] = s
            for w, g in (("pre", s), ("fault", min(s + 10, 120))):
                if f"g{g}" in r["feat"]:
                    r["feat"][w] = r["feat"][f"g{g}"]
        else:
            r["pre_len"] = (r["t_f"] - r["t0"]) / 1e6
    rs = [r for r in keep if all(w in r["feat"] for w in ("pre", "fault", "whole"))]
    y = np.array([0 if r["cls"] == "no_fault" else 1 for r in rs])
    date = [re.search(r"log_\d+_(\d{4}-\d+-\d+)", r["path"]).group(1) for r in rs]
    mixed = sorted({d for d, t in zip(date, y) if t == 0})
    out = {"mixed_days": len(mixed)}
    for w in ("pre", "fault", "whole"):
        X = np.array([[np.nan if r["feat"][w][f] is None else r["feat"][w][f] for f in fa.FEATURES] for r in rs], float)
        _, _, s = fa.cv_scores(X, y, date, "group")
        per = []
        for d in mixed:
            idx = [i for i, dd in enumerate(date) if dd == d]
            per.append({"day": d, "n": len(idx), "n_nofault": int((y[idx] == 0).sum()), "auc": fa.auc(y[idx], s[idx])})
        out[w] = {"per_day": per, "weighted_mean": float(sum(p["n"] * p["auc"] for p in per) / sum(p["n"] for p in per))}
    whole_len = lambda r: (r["t_end"] - r["t0"]) / 1e6
    out["B2"] = {c: {"median_pre_s": float(np.median([r["pre_len"] for r in rs if (r["cls"] == "no_fault") == (c == "no_fault")])),
                     "median_whole_s": float(np.median([whole_len(r) for r in rs if (r["cls"] == "no_fault") == (c == "no_fault")])),
                     "share_whole_over_120s": float(np.mean([whole_len(r) > 120 for r in rs if (r["cls"] == "no_fault") == (c == "no_fault")]))}
                 for c in ("fault", "no_fault")}
    return out


# ---------------------------------------------------------------- C, D

def part_c(root, db):
    import postcrash_audit as pca
    from r16_audit import crash_status
    from r19_audit import ptype
    key = json.load(open(os.path.join(RESULTS_DIR, "crash_moment_blind_key.json")))["panel_to_log_id"]
    path = os.path.join(SCRIPT_DIR, "relabel_pack", "returned", "crash_moment_form.xlsx")
    from openpyxl import load_workbook
    C = {}
    for row in load_workbook(path, data_only=True)["Review"].iter_rows(min_row=2, values_only=True):
        if row[0] and row[1]:
            C[key[str(int(row[0]))]] = str(row[1]).strip().lower()
    status = crash_status(pca.ulg_paths(root), sorted(C))
    out = defaultdict(Counter)
    for l, lab in C.items():
        t = ptype(db.get(l, {}).get("mav_type"))
        out[t][status[l]] += 1
        out[t][f"{status[l]}|C_correct"] += lab == "correct"
    return {t: dict(c) for t, c in out.items()}


def part_d(db):
    mc = lambda lid: db.get(lid, {}).get("mav_type") in MULTI
    mod = {r["log"] for r in jsonl("leak_curve_features.jsonl") if r["group"] == "crash" and r["margin"] == 0}
    pv = {r["log_id"]: r for n in ("holdout.jsonl", "pilot_vs_drone.jsonl") for r in jsonl(n)}
    sets = {"holdout": [r for r in jsonl("holdout.jsonl") if r.get("label") in ("pilot", "drone") and mc(r["log_id"])],
            "modelled": [pv[l] for l in sorted(mod) if l in pv and mc(l) and pv[l].get("label") in ("pilot", "drone")]}
    out = {}
    for name, rows in sets.items():
        dec = [r for r in rows if r["verdict"] in ("pilot", "drone")]
        y = np.array([1 if r["label"] == "drone" else 0 for r in dec])
        v = np.array([1 if r["verdict"] == "drone" else 0 for r in dec])
        ba = lambda yy, vv: float((np.mean(vv[yy == 1] == 1) + np.mean(vv[yy == 0] == 0)) / 2) if (yy == 0).any() and (yy == 1).any() else np.nan
        rng = np.random.default_rng(2142)
        bs = [ba(y[b], v[b]) for b in (rng.integers(0, len(y), len(y)) for _ in range(2000))]
        out[name] = {"n": len(rows), "undecided": len(rows) - len(dec), "n_decided": len(dec), "ba_decided": ba(y, v),
                     "ci": boot_ci(bs), "recall_aircraft": float(np.mean(v[y == 1] == 1)), "recall_pilot": float(np.mean(v[y == 0] == 0))}
    return out


def main(root, rdir):
    raw = open(os.path.join(root, "dbinfo.json"), "rb").read()
    db = {x["log_id"]: x for x in json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)}
    rep = {"declared_in": "research/px4_log_study/r21_audit.py docstring"}
    for name, fn in (("B", part_b), ("C", lambda: part_c(root, db)), ("D", lambda: part_d(db)), ("A", lambda: part_a(rdir))):
        try:
            rep[name] = fn()
        except Exception as e:
            rep[name] = f"not run: {type(e).__name__}: {e}"
        print("done", name, flush=True)
        json.dump(rep, open(os.path.join(RESULTS_DIR, "r21_audit.json"), "w"), indent=1, default=float)
    open(os.path.join(RESULTS_DIR, "r21_audit.md"), "w").write(
        "# Round 21 audit\n\nDeclared in `research/px4_log_study/r21_audit.py`. Exploratory (dagger).\n\n```\n"
        + json.dumps(rep, indent=1, default=float) + "\n```\n")
    print(json.dumps(rep, indent=1, default=float))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/Volumes/One Touch/AeroFleet_px4_data",
         sys.argv[2] if len(sys.argv) > 2 else "/Volumes/One Touch/AeroFleet_px4_data/external/rflymad")
