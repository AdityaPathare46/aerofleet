"""First pass of the PX4 crash study: do crashed drones fly with different safety settings?

For each log, reads the settings stored at the start of the file and PX4's own record of which settings differ
from the firmware default. Each setting is graded with AeroFleet's catalogue (aerofleet/assurance/drift.py).
For full logs (the crashes) it also lists safety settings changed during the flight.

    python research/px4_log_study/analyze.py SELECTION_CSV LOG_DIR OUT_DIR

No language model is involved; every number comes from the log files.
"""
import csv
import json
import math
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from pyulog import ULog  # noqa: E402

from aerofleet.assurance.drift import CRITICAL, HIGH, severity_of  # noqa: E402

# Settings whose non-default value switches a protection off (PX4 parameter reference).
SWITCHED_OFF = {
    "NAV_DLL_ACT": lambda v: v == 0,          # data-link loss: no action
    "NAV_RCL_ACT": lambda v: v == 0,          # RC loss: no action (older firmware)
    "COM_RCL_EXCEPT": lambda v: v > 0,        # RC-loss failsafe skipped in some modes
    "COM_DLL_EXCEPT": lambda v: v > 0,
    "COM_LOW_BAT_ACT": lambda v: v == 0,      # low battery: warning only
    "GF_ACTION": lambda v: v == 0,            # geofence breach: no action
    "COM_ARM_WO_GPS": lambda v: v == 1,       # arming without GPS allowed (older meaning)
    "CBRK_SUPPLY_CHK": lambda v: v == 894281,  # power-supply check disabled
    "CBRK_USB_CHK": lambda v: v == 197848,    # arming with USB connected allowed
    "CBRK_IO_SAFETY": lambda v: v == 22027,   # safety switch disabled
    "CBRK_AIRSPD_CHK": lambda v: v == 162128,  # airspeed sensor check disabled
    "CBRK_VTOLARMING": lambda v: v == 159753,
    "FD_FAIL_P": lambda v: v == 0, "FD_FAIL_R": lambda v: v == 0,
}


def read(path, header_only):
    u = ULog(path, parse_header_only=header_only)
    params = u.initial_parameters
    defaults = u.get_default_parameters(0) if u.has_default_parameters else None
    changed = []
    if not header_only and u.data_list is not None:
        t0 = u.start_timestamp
        for t, name, value in u.changed_parameters:
            if t > t0 and name in params and value != params.get(name):
                changed.append({"t_s": round((t - t0) / 1e6, 1), "name": name, "value": value, "severity": severity_of(name)})
    off_default = [n for n in defaults if n in params and params[n] != defaults[n]] if defaults is not None else None
    return {
        "has_defaults": defaults is not None,
        "n_params": len(params),
        "off_default_critical": sorted(n for n in (off_default or []) if severity_of(n) == CRITICAL),
        "off_default_high": sorted(n for n in (off_default or []) if severity_of(n) == HIGH),
        # Only where the value is not the firmware default: several of these "off" values are PX4's own defaults
        # on some versions (e.g. NAV_DLL_ACT=0), which a first version of this script wrongly counted.
        "switched_off": (sorted(n for n, f in SWITCHED_OFF.items()
                                if n in params and n in defaults and params[n] != defaults[n] and f(params[n]))
                         if defaults is not None else None),
        "changed_in_flight": changed,
    }


def fisher_p(a, b, c, d):
    """Two-sided Fisher exact test for [[a, b], [c, d]]."""
    n, r1, c1 = a + b + c + d, a + b, a + c
    pr = lambda x: math.comb(c1, x) * math.comb(n - c1, r1 - x) / math.comb(n, r1)  # noqa: E731
    p0 = pr(a)
    return min(1.0, sum(pr(x) for x in range(max(0, r1 + c1 - n), min(r1, c1) + 1) if pr(x) <= p0 * (1 + 1e-9)))


def main(sel_csv, log_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    rows, errors = [], Counter()
    for r in csv.DictReader(open(sel_csv)):
        path = os.path.join(log_dir, r["group"], r["log_id"] + ".ulg")
        if not os.path.exists(path) or os.path.getsize(path) < 1000:
            errors["missing"] += 1
            continue
        try:
            r.update(read(path, header_only=(r["group"] == "control")))
        except Exception as e:  # truncated or damaged file
            errors[type(e).__name__] += 1
            continue
        rows.append(r)
    with open(os.path.join(out_dir, "per_log.jsonl"), "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    groups = {"crash (all)": [r for r in rows if r["group"] == "crash"],
              "crash: drone (sw/hw)": [r for r in rows if r["rating"] == "crash_sw_hw"],
              "crash: pilot": [r for r in rows if r["rating"] == "crash_pilot"],
              "control (good/great)": [r for r in rows if r["group"] == "control"]}
    lines = ["# PX4 crash study, first pass", "",
             f"Logs read: {len(rows)}; not read: {dict(errors)}. Source: PX4 Flight Review public logs, selection by "
             "`select_logs.py` (seed 1).", "",
             "| Group | Logs | Has default record | ≥1 safety-critical setting off default | ≥1 flight-limit setting off default "
             "| ≥1 protection switched off (vs default) | Median settings off default (critical) |", "|---|---|---|---|---|---|---|"]
    for g, xs in groups.items():
        wd = [x for x in xs if x["has_defaults"]]
        crit = sum(1 for x in wd if x["off_default_critical"])
        high = sum(1 for x in wd if x["off_default_high"])
        off = sum(1 for x in wd if x["switched_off"])
        med = sorted(len(x["off_default_critical"]) for x in wd)
        lines.append(f"| {g} | {len(xs)} | {len(wd)} | {crit} ({100 * crit / max(1, len(wd)):.0f}%) | {high} "
                     f"({100 * high / max(1, len(wd)):.0f}%) | {off} ({100 * off / max(1, len(wd)):.0f}%) | "
                     f"{med[len(med) // 2] if med else '-'} |")
    c, k = ([x for x in groups[g] if x["has_defaults"]] for g in ("crash (all)", "control (good/great)"))
    a, b = sum(1 for x in c if x["switched_off"]), sum(1 for x in c if not x["switched_off"])
    cc, d = sum(1 for x in k if x["switched_off"]), sum(1 for x in k if not x["switched_off"])
    lines += ["", f"Protection switched off, crash vs control: Fisher exact p = {fisher_p(a, b, cc, d):.3f}", "",
              "## Which protections were switched off (logs with a default record only)", "", "| Setting | Crash | Control |", "|---|---|---|"]
    sc, sk = Counter(n for x in c for n in x["switched_off"]), Counter(n for x in k for n in x["switched_off"])
    for n in sorted(set(sc) | set(sk), key=lambda n: -(sc[n] + sk[n])):
        lines.append(f"| `{n}` | {sc[n]} of {len(c)} | {sk[n]} of {len(k)} |")
    lines += ["", "## Safety-critical settings most often off default", "", "| Setting | Crash | Control |", "|---|---|---|"]
    oc = Counter(n for x in c for n in x["off_default_critical"])
    ok = Counter(n for x in k for n in x["off_default_critical"])
    for n in sorted(set(oc) | set(ok), key=lambda n: -(oc[n] + ok[n]))[:25]:
        lines.append(f"| `{n}` | {oc[n]} | {ok[n]} |")
    c = groups["crash (all)"]
    inflight = [x for x in c if any(ch["severity"] in (CRITICAL, HIGH) for ch in x["changed_in_flight"])]
    lines += ["", "## Safety settings changed during the flight (crash logs only; control logs were read header-only)", "",
              f"{len(inflight)} of {len(c)} crash logs.", ""]
    for x in inflight[:20]:
        ch = [f"{h['name']} at {h['t_s']} s" for h in x["changed_in_flight"] if h["severity"] in (CRITICAL, HIGH)][:6]
        lines.append(f"- `{x['log_id']}` ({x['rating']}, {x['mav_type']}): " + ", ".join(ch))
    lines += ["", "## Limits", "",
              "- Ratings are the uploader's own; nobody checked them. 'Good' logs are a self-selected comparison group.",
              "- Default records exist only on newer firmware; logs without them are left out of the off-default columns.",
              "- Control logs were downloaded only up to 2 MB, so in-flight changes are counted for crashes only.",
              "- A protection being off is not shown to have caused any crash; this is association, on a small sample."]
    open(os.path.join(out_dir, "summary.md"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main(*sys.argv[1:4])
