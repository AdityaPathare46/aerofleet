"""Score the forum expert-diagnosis recording: do the two recorders agree, and do experts agree with uploaders?

    python research/px4_log_study/score_forum.py REVIEWER_A.xlsx REVIEWER_B.xlsx FORUM_KEY_CSV [OUT_MD]

REVIEWER_A may also be the first recording as a CSV (results/px4_log_study/forum_expert_labels.csv), which is
how the 161 threads were first recorded; it is matched to the sheet rows through the key's topic_id. Agreement
with an independent second recorder (sheet B, filled blind) is the reliability check of the expert labels.
"""
import csv
import sys
from collections import Counter

from openpyxl import load_workbook

from score_review import kappa


def read(path, key=None):
    if path.endswith(".csv"):
        by_topic = {r["topic_id"]: r for r in csv.DictReader(open(path))}
        return {i: {"crash": t["is_crash"], "verdict": t["expert_conclusion"], "cause": t["cause"], "who": t["who"],
                    "confirmed": t["poster_confirmed"]}
                for i, k in key.items() for t in [by_topic.get(k["topic_id"])] if t}
    ws = load_workbook(path, data_only=True)["Threads"]
    return {r[0]: {"crash": r[6], "verdict": r[7], "cause": r[8], "who": r[9], "confirmed": r[10]}
            for r in ws.iter_rows(min_row=2, values_only=True) if r[0]}


def main(a_path, b_path, key_path, out=None):
    key = {int(r["#"]): r for r in csv.DictReader(open(key_path))}
    A, B = read(a_path, key), read(b_path)
    both = [i for i in key if A.get(i, {}).get("verdict") and B.get(i, {}).get("verdict")]
    L = ["# Forum expert diagnoses: recording agreement", "", f"Threads recorded by both: {len(both)}", ""]
    for field in ("crash", "verdict", "cause", "confirmed"):
        k, n = kappa([(A[i][field], B[i][field]) for i in both])
        L.append(f"- {field}: A and B agree on {sum(A[i][field] == B[i][field] for i in both)} of {n}; kappa {k:.2f}")
    agreed = [i for i in both if A[i]["verdict"] == B[i]["verdict"] and A[i]["crash"] == "yes"]
    L += ["", "Expert conclusion where both recorders agree (crash threads):", ""]
    for v, n in Counter(A[i]["verdict"] for i in agreed).most_common():
        L.append(f"- {v}: {n}")
    rated = [i for i in agreed if "crash_" in key[i]["flight_review_ratings"] and A[i]["verdict"] in ("drone", "pilot")]
    match = sum(("crash_sw_hw" in key[i]["flight_review_ratings"]) == (A[i]["verdict"] == "drone") for i in rated)
    L += ["", f"Uploader crash rating vs expert conclusion (both decided): agree on {match} of {len(rated)}"]
    text = "\n".join(L) + "\n"
    if out:
        open(out, "w").write(text)
    print(text)


if __name__ == "__main__":
    main(*sys.argv[1:5])
