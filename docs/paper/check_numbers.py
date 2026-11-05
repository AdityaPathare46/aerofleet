"""Check that key numbers agree between the results files, the main text, the supplement, the highlights and the cover
letter. Each check takes the value from a results JSON where one exists, then finds every occurrence of the quantity
in the documents (by a regex with one capture group) and flags any occurrence that differs from the expected
rounding. Run after any edit:

    python docs/paper/check_numbers.py            (exit code 1 if any check fails)
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "..", "research", "results", "px4_log_study")
DOCS = {k: os.path.join(HERE, "latex", f) for k, f in
        (("main", "main.tex"), ("supp", "supplement.tex"), ("highlights", "highlights.txt"), ("letter", "cover_letter.tex"))}


def j(name, *path):
    d = json.load(open(os.path.join(RES, name)))
    for p in path:
        d = d[p]
    return d


def r(x, n=2):
    return f"{x:.{n}f}"


r20, r21, r22 = (lambda *p: j("r20_audit.json", *p)), (lambda *p: j("r21_audit.json", *p)), (lambda *p: j("r22_audit.json", *p))
pct = lambda x: f"{round(100 * x):d}"

# (name, expected value as string, regex with one capture group for the number)
CHECKS = [
    ("site-weighted p", r(r20("C", "p"), 3), r"site-weighted[^.]{0,60}?\$p=(0\.\d+)\$"),
    ("site-weighted Holm", r(r20("C", "holm"), 2), r"(?:Holm 0\.45|Holm-adjusted over the seven tests )(0\.\d+)|Holm (0\.4\d)\)"),
    ("tests-table site Holm", r(r20("C", "holm"), 2), r"0\.016; \$\^\\dagger\$0\.08; (0\.\d+) &"),
    ("design-table site Holm", r(r20("C", "holm"), 2), r"0\.08 clustered by airframe, (0\.\d+) with operator"),
    ("site-weighted mean rank", r(r20("C", "site_weighted_mean_rank"), 2), r"site-weighted mean rank (0\.\d+)|mean rank (0\.6\d), \$p=0\.076"),
    ("screening lift", r(1.77, 2), r"lift (?:of )?\$(1\.\d+)\\times\$ \[1\.00"),
    ("leave-one-out lift", r(r20("D", "D3_leave_one_out_10", "lift"), 2), r"\$(1\.6\d)\\times\$ \[0\.94"),
    ("detector random AUC", r(r21("A", "A1_random_window_split", "auc"), 2), r"AUC (0\.9\d) (?:\(random|on random|with random)|fell from AUC (0\.9\d) to"),
    ("detector days AUC", r(r21("A", "A3_grouped_by_day", "auc"), 2), r"fell from AUC 0\.94 to (0\.\d+)|(0\.6\d) \(days held out\)"),
    ("detector pre-fault flights", r(r21("A", "A4_pre_onset_grouped_by_flight", "auc"), 2), r"pre-fault[^.]{0,40}?(0\.8\d) with flights|at (0\.8\d) with flights held out"),
    ("detector pre-fault days", r(r21("A", "A5_pre_onset_grouped_by_day", "auc"), 2), r"pre-fault[^.]{0,80}?(0\.5\d) with days held out|but (0\.5\d) with days held out|fell to (0\.5\d) with days held out"),
    ("detector random-vs-day drop", r(r21("A", "A1_minus_A3", "diff"), 2), r"drop is (0\.3\d) \[0\.28"),
    ("tilt missed, first reviewer", pct(r22("A", "A", "missed")), r"about (\d+)\\% \[0, 22\]"),
    ("tilt missed, blind reviewer", pct(r22("A", "B", "missed")), r"(\d+)\\% \[15, 46\]"),
    ("tilt missed, third rater", pct(r22("A", "C", "missed")), r"(\d+)\\% \[34, 65\]"),
    ("tilt missed, majority", pct(r22("A", "majority", "missed")), r"(\d+)\\% \[8, 46\]"),
    ("tilt missed range", "7", r"misses roughly (\d+)--50\\%"),
    ("third rater tilt correct", str(r21("C", "multicopter", "confirmed|C_correct") + r21("C", "multicopter", "tilt_unconfirmed|C_correct")),
     r"(\d+) of 15 for the third"),
    ("relabelling kappa", r(j("relabel_scores.json", "R1_R3_all", "kappa"), 2), r"(?:uploaders?|uploader)[^.]{0,80}?\\kappa=(-?0\.\d+)|\$\\kappa=(-0\.\d+)\$"),
    ("relabelling rule BA", r(j("relabel_scores.json", "R1_R3_all", "rule_ba_vs_expert"), 2), r"reviewer's labels[^.]{0,60}?(0\.\d+) \[0\.42"),
    ("injected features by day", r(r20("A", "date", "pre", "auc"), 2), r"(0\.7\d) with folds grouped by flight day|(0\.7\d) \(days held out\); same"),
    ("injected features by pattern", r(r20("A", "pattern", "pre", "auc"), 2), r"(0\.7\d) grouped by flight pattern"),
    ("length-matched features by day", r(r22("C", "C2_matched_features", "by_day", "auc"), 2), r"(0\.7\d) with days held out, \$p\\le"),
    ("window-length AUC", r(r22("C", "C1_auc_pre_length"), 2), r"window length alone gives AUC (0\.\d+)"),
    ("multicopter rule held out", r(r20("B", "B1_rule_holdout", "ba"), 2), r"(0\.4\d) \[0\.33, 0\.54\]"),
    ("multicopter decided held out", r(r21("D", "holdout", "ba_decided"), 2), r"(0\.4\d) \[0\.35, 0\.56\]"),
    ("crash-containing, third rater (multicopter)", "82", r"(\d+)\\% \[68--94\\%\]"),
    ("crash-containing, majority (multicopter)", "67", r"(\d+)\\% \[50--85\\%\]"),
]


def main():
    text = {k: open(p).read() for k, p in DOCS.items() if os.path.exists(p)}
    bad = 0
    for name, want, rx in CHECKS:
        found = []
        for doc, t in text.items():
            for m in re.finditer(rx, t):
                v = next(g for g in m.groups() if g is not None)
                line = t.count("\n", 0, m.start()) + 1
                found.append((doc, line, v))
        wrong = [f for f in found if f[2] != want]
        status = "OK " if found and not wrong else ("MISS" if not found else "FAIL")
        bad += status != "OK "
        print(f"{status}  {name}: expected {want}; " + ", ".join(f"{d}:{l}={v}" for d, l, v in found))
    print(f"\n{len(CHECKS) - bad} of {len(CHECKS)} checks agree")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
