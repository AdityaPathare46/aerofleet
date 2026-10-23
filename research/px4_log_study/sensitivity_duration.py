"""S8 (post hoc): does flight duration explain the between-drone vibration difference?

Within each vibration source, log(vibration) is regressed on log(duration) over all exposure flights; the
between-drone rank test is then repeated on the residuals (vibration not explained by duration).

    python research/px4_log_study/sensitivity_duration.py DBINFO_JSON
"""
import gzip
import json
import os
import sys
from collections import defaultdict

import numpy as np

from sensitivity import load_between, null_p

RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "px4_log_study")


def main(dbinfo):
    raw = open(dbinfo, "rb").read()
    db = {x["log_id"]: x for x in json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)}
    sets, role = load_between()
    pts = defaultdict(list)
    for sid, vehicles in sets.items():
        for v, rs in vehicles.items():
            for r in rs:
                f = r["features"]
                if f and f.get("vib_p95") and r["log_id"] in db and (db[r["log_id"]].get("duration_s") or 0) > 0:
                    pts[f["src_vib"]].append((np.log(db[r["log_id"]]["duration_s"]), np.log(f["vib_p95"]), r["log_id"]))
    resid, lines = {}, []
    for src, p in pts.items():
        x, y = np.array([a for a, _, _ in p]), np.array([b for _, b, _ in p])
        slope, icpt = np.polyfit(x, y, 1)
        rho = np.corrcoef(np.argsort(np.argsort(x)), np.argsort(np.argsort(y)))[0, 1]
        lines.append(f"- {src}: {len(p)} flights, Spearman rho(duration, vibration) = {rho:.2f}, slope {slope:.2f}")
        for (a, b, lid) in p:
            resid[lid] = b - (slope * a + icpt)
    ranks, sizes = [], []
    for sid, vehicles in sets.items():
        case = [v for v in vehicles if role[(sid, v)] == "case"]
        if not case:
            continue
        def val(rs, src):
            vs = [resid[r["log_id"]] for r in rs if r["log_id"] in resid and r["features"] and r["features"].get("src_vib") == src]
            return float(np.median(vs)) if len(vs) >= 2 else None
        srcs = {r["features"]["src_vib"] for r in vehicles[case[0]] if r["features"] and r["features"].get("src_vib")}
        for src in srcs:
            cv = val(vehicles[case[0]], src)
            ctrl = [val(vehicles[v], src) for v in vehicles if role[(sid, v)] == "control"]
            ctrl = [c for c in ctrl if c is not None]
            if cv is not None and ctrl:
                ranks.append(sum(c < cv for c in ctrl) / len(ctrl))
                sizes.append(len(ctrl))
            break
    obs, p, n = null_p(ranks, sizes)
    text = ["", "## S8 Duration-adjusted between-drone vibration test", ""] + lines + [
        "", f"On vibration adjusted for flight duration: {n} matched sets, mean scaled rank {obs:.2f}, one-sided p = {p:.4f}."]
    open(os.path.join(RES, "sensitivity.md"), "a").write("\n".join(text) + "\n")
    print("\n".join(text))


if __name__ == "__main__":
    main(sys.argv[1])
