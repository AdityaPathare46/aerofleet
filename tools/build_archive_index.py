#!/usr/bin/env python3
"""Build the index behind "Search the public log archive" (aerofleet/assurance/archive_search.py).

Two parts, both from the public PX4 Flight Review archive:
  1. Text: what uploaders wrote about their own flights (description and feedback in dbinfo.json), with the
     uploader's rating, vehicle type, airframe and log id. Boilerplate ("None Given", "QGroundControl Session"),
     file names and text with fewer than three real words are left out; identical texts (test benches upload the
     same note hundreds of times) are kept at most three times, with the count.
  2. Logs: every .ulg on this computer's data drive is read with AeroFleet's own reader, and the signs its log shows
     (aerofleet/assurance/log_signs.py) are stored with its id. Results are cached in a .jsonl next to the index, so
     a second run only reads new logs.

The index holds other people's text, so it is written to this install's data folder, not to the repository:
    python tools/build_archive_index.py [--data "/Volumes/One Touch/AeroFleet_px4_data"] [--out PATH] [--workers 6]
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

BOILER = {"none given", "qgroundcontrol session", "none", "n/a", "na", "-", "test", "flight", "log"}
FOLDERS = ["screen_ref", "within", "rough", "control", "newer", "h", "crash", "archive_crash"]
MAX_TEXT = 600


def clean(entry):
    parts = []
    for k in ("description", "feedback"):
        v = re.sub(r"\s+", " ", (entry.get(k) or "")).strip()
        if v and v.lower() not in BOILER and not re.fullmatch(r"[\w\-. ()]+\.(ulg|bin|log|tlog)", v, re.I):
            parts.append(v)
    text = " · ".join(dict.fromkeys(parts))
    words = [w for w in re.findall(r"[A-Za-z]{3,}", text) if not re.search(r"\d", w)]
    from aerofleet.assurance.troubleshoot import tokens

    return text[:MAX_TEXT] if len(set(tokens(" ".join(words)))) >= 3 else None


def one_log(path):
    from aerofleet.assurance.flightlog import FlightLogError, read_flight_log
    from aerofleet.assurance.log_signs import signs_from_flight

    lid = os.path.basename(path)[:-4]
    try:
        f = read_flight_log(path)
        return {"id": lid, "signs": sorted(signs_from_flight(f)), "vehicle": f.vehicle,
                "min": round((f.track[-1][0] - f.track[0][0]) / 60, 1) if f.track else 0}
    except (FlightLogError, Exception) as e:          # a public log the reader cannot use is skipped, with the reason
        return {"id": lid, "error": str(e)[:200]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/Volumes/One Touch/AeroFleet_px4_data")
    ap.add_argument("--out", default=None)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--no-logs", action="store_true", help="text part only")
    a = ap.parse_args()
    from aerofleet.assurance.archive_search import index_path

    out_path = a.out or str(index_path())
    raw = open(os.path.join(a.data, "dbinfo.json"), "rb").read()
    try:
        raw = gzip.decompress(raw)
    except OSError:
        pass
    dbinfo = json.loads(raw)
    meta = {e["log_id"]: e for e in dbinfo}

    # text part, with how often each text occurred
    counts = {}
    reports = []
    for e in dbinfo:
        text = clean(e)
        if not text:
            continue
        key = re.sub(r"\d+", "#", text.lower())
        counts[key] = counts.get(key, 0) + 1
        if counts[key] > 3:
            continue
        reports.append({"id": e["log_id"], "date": e.get("log_date"), "text": text, "rating": e.get("rating") or "",
                        "type": e.get("mav_type") or "", "airframe": e.get("airframe_name") or "",
                        "hw": e.get("sys_hw") or "", "fw": (e.get("ver_sw_release") or "").split(" ")[0],
                        "min": round((e.get("duration_s") or 0) / 60, 1), "_key": key})
    for r in reports:
        r["same_text"] = counts[r.pop("_key")]
    print(f"text: {len(reports)} reports kept from {len(dbinfo)} archive entries")

    # log part
    logs = []
    if not a.no_logs:
        cache_path = out_path.replace(".json.gz", "") + "_signs.jsonl"
        cache = {}
        if os.path.exists(cache_path):
            for line in open(cache_path, encoding="utf-8"):
                r = json.loads(line)
                cache[r["id"]] = r
        paths = {}
        for folder in FOLDERS:
            for dirpath, _, files in os.walk(os.path.join(a.data, folder)):
                for name in files:
                    if name.endswith(".ulg") and not name.startswith("._"):
                        paths.setdefault(name[:-4], os.path.join(dirpath, name))
        todo = [p for lid, p in paths.items() if lid not in cache]
        print(f"logs: {len(paths)} on this drive, {len(todo)} to read")
        with open(cache_path, "a", encoding="utf-8") as fc, ProcessPoolExecutor(a.workers) as ex:
            futs = [ex.submit(one_log, p) for p in todo]
            for i, fut in enumerate(as_completed(futs), 1):
                r = fut.result()
                cache[r["id"]] = r
                fc.write(json.dumps(r) + "\n")
                if i % 200 == 0:
                    print(f"  {i}/{len(todo)}", flush=True)
        for lid in paths:
            r = cache.get(lid)
            if r and "signs" in r:
                m = meta.get(lid, {})
                logs.append({"id": lid, "signs": r["signs"], "vehicle": r.get("vehicle") or m.get("mav_type") or "",
                             "min": r.get("min"), "rating": m.get("rating") or "", "date": m.get("log_date"),
                             "airframe": m.get("airframe_name") or "", "text": clean(m) if m else None})
        print(f"logs: {len(logs)} readable, {sum(1 for r in cache.values() if 'error' in r)} skipped")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with gzip.open(out_path, "wt", encoding="utf-8") as f:
        json.dump({"built_from": "PX4 Flight Review public archive (dbinfo.json) and the logs on this computer",
                   "archive_entries": len(dbinfo), "reports": reports, "logs": logs}, f)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
