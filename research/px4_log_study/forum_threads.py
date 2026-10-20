"""Collect PX4 forum crash threads that link a Flight Review log, for expert-diagnosis labels.

Searches discuss.px4.io (public Discourse API), fetches each thread, pulls out Flight Review log IDs, and records
every reply with the replier's forum role. Matches the log IDs against the Flight Review index so we know which
also carry an uploader crash rating. Forum text is cached locally and is not committed (it is the forum's content).

    python research/px4_log_study/forum_threads.py DBINFO_JSON CACHE_DIR OUT_JSONL
"""
import gzip
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

BASE = "https://discuss.px4.io"
QUERIES = ["review.px4.io crash", "logs.px4.io crash", "plot_app crash", "review.px4.io crashed", "logs.px4.io crashed",
           "review.px4.io flyaway", "review.px4.io fell", "logs.px4.io flipped", "review.px4.io flipped",
           "plot_app crashed", "review.px4.io lost control", "logs.px4.io lost control"]
LOG_RE = re.compile(r"(?:review|logs)\.px4\.io/plot_app\?log=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})")
TAG_RE = re.compile(r"<[^>]+>")


def get(url, cache_dir, name):
    path = os.path.join(cache_dir, name)
    if os.path.exists(path):
        return json.load(open(path))
    for wait in (2, 10, 30, 60):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AeroFleet-research (student project)"})
            data = json.load(urllib.request.urlopen(req, timeout=60))
            json.dump(data, open(path, "w"))
            time.sleep(1.5)
            return data
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(wait)
    return None


def text(html_):
    import html
    return " ".join(html.unescape(TAG_RE.sub(" ", html_ or "")).split())


def main(dbinfo, cache_dir, out):
    os.makedirs(cache_dir, exist_ok=True)
    raw = open(dbinfo, "rb").read()
    index = {x["log_id"]: x for x in json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)}
    topics = {}
    for q in QUERIES:
        for page in range(1, 6):
            d = get(f"{BASE}/search.json?q={urllib.parse.quote(q)}&page={page}", cache_dir,
                    f"search_{re.sub('[^a-z0-9]', '_', q)}_{page}.json")
            if not d or not d.get("topics"):
                break
            for t in d["topics"]:
                topics[t["id"]] = t["title"]
            if not d.get("grouped_search_result", {}).get("more_full_page_results"):
                break
    print(f"{len(topics)} candidate threads")
    n_logs = n_rated = 0
    with open(out, "w") as f:
        for tid, title in sorted(topics.items()):
            t = get(f"{BASE}/t/{tid}.json", cache_dir, f"t_{tid}.json")
            if not t:
                continue
            posts = t.get("post_stream", {}).get("posts", [])
            if not posts:
                continue
            op = posts[0]["username"]
            logs = []
            for p in posts:
                for lid in LOG_RE.findall(p.get("cooked", "")):
                    if lid not in logs:
                        logs.append(lid)
            if not logs:
                continue
            replies = [{"post": p["post_number"], "user": p["username"], "is_op": p["username"] == op,
                        "role": ("staff" if p.get("staff") or p.get("moderator") or p.get("admin") else
                                 (p.get("primary_group_name") or f"trust{p.get('trust_level', '?')}")),
                        "text": text(p.get("cooked"))[:1500]} for p in posts[1:]]
            rated = [{"log_id": lid, "rating": index[lid]["rating"]} for lid in logs if lid in index]
            n_logs += 1
            n_rated += any(r["rating"] in ("crash_sw_hw", "crash_pilot") for r in rated)
            f.write(json.dumps({"topic_id": tid, "title": title, "url": f"{BASE}/t/{tid}", "created": t.get("created_at"),
                                "log_ids": logs, "in_index": rated, "op_text": text(posts[0].get("cooked"))[:2000],
                                "n_replies": len(replies), "n_non_op_replies": sum(not r["is_op"] for r in replies),
                                "replies": replies}) + "\n")
    print(f"threads with a log link: {n_logs}; of those, with a log rated as a crash on Flight Review: {n_rated}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
