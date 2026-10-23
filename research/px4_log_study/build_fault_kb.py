"""Build the troubleshooting knowledge base from the PX4 forum crash threads labelled for the log study.

    python research/px4_log_study/build_fault_kb.py FORUM_CACHE_DIR

Input: research/results/px4_log_study/forum_expert_labels.csv (161 threads, expert conclusion and cause recorded
by hand) and the cached thread JSON (not committed). Output: aerofleet/assurance/data/fault_cases.json.

Forum text is not copied. Each case keeps the thread title, link, the labels, and up to 30 descriptive terms taken
from the opening post (the words that carry the symptom: "toilet bowl", "baro", "flip", ...), which is enough to
match a new description against it and sends the reader to the thread for the details.
"""
import csv
import html
import json
import math
import os
import re
import sys
from collections import Counter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, ROOT)

from aerofleet.assurance.troubleshoot import tokens  # noqa: E402

LABELS = os.path.join(ROOT, "research", "results", "px4_log_study", "forum_expert_labels.csv")
OUT = os.path.join(ROOT, "aerofleet", "assurance", "data", "fault_cases.json")
TERMS = 30


def opening_post(thread):
    posts = thread.get("post_stream", {}).get("posts", [])
    raw = posts[0].get("cooked", "") if posts else ""
    raw = re.sub(r"<(pre|code|a)[^>]*>.*?</\1>", " ", raw, flags=re.S)     # links and pasted logs carry no symptom
    return html.unescape(re.sub(r"<[^>]+>", " ", raw))


def main(cache):
    rows = list(csv.DictReader(open(LABELS)))
    docs = {}
    for r in rows:
        path = os.path.join(cache, f"t_{r['topic_id']}.json")
        thread = json.load(open(path)) if os.path.exists(path) else {}
        docs[r["topic_id"]] = (thread.get("title", ""), tokens(opening_post(thread)))
    df = Counter(t for _, toks in docs.values() for t in set(toks))
    n = len(docs)
    cases = []
    for r in rows:
        title, toks = docs[r["topic_id"]]
        tf = Counter(toks)
        # terms that are frequent in this post and rare across posts; terms in a single post are mostly names
        score = {t: c * math.log(n / df[t]) for t, c in tf.items() if df[t] >= 2 and df[t] < n / 3}
        terms = sorted(score, key=lambda t: (-score[t], t))[:TERMS]
        cases.append({
            "topic_id": int(r["topic_id"]), "url": r["url"], "title": title,
            "terms": sorted(terms), "is_crash": r["is_crash"] == "yes",
            "expert_conclusion": r["expert_conclusion"] or "not recorded", "cause": r["cause"] or "not stated",
            "who": r["who"], "poster_confirmed": r["poster_confirmed"] or "not stated",
            "log_ids": r["log_ids"].split(),
        })
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"source": "PX4 discussion forum threads that link a Flight Review log and describe a crash; "
                         "expert conclusion and cause recorded by the authors (research/px4_log_study)",
               "cases": cases}, open(OUT, "w"), indent=1)
    print(f"{len(cases)} cases -> {OUT}")


if __name__ == "__main__":
    main(sys.argv[1])
