"""Search the public PX4 log archive for flights like the user's problem.

Two kinds of match, both shown as things to read, never as an answer:
  * What people wrote: BM25 word matching of the user's description against what uploaders wrote about their own
    flights in the public archive (description and feedback), with each flight's rating as the uploader gave it.
  * What logs showed: the public logs on this computer whose logs show the same signs (aerofleet/assurance/log_signs.py)
    as the user's flight, or as the signs the description's words point to.

The index is built by tools/build_archive_index.py into this install's data folder (it holds other people's text, so
it is not in the repository). Without it the search says so and returns nothing. No model is called.
"""
from __future__ import annotations

import gzip
import json
import math
import os
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from aerofleet.assurance.log_signs import SIGNS, similarity
from aerofleet.assurance.troubleshoot import K1, B, tokens

REVIEW_URL = "https://review.px4.io/plot_app?log={id}"
CRASH = {"crash_sw_hw", "crash_pilot"}
RATING = {"good": "good", "great": "great", "BRAVO!": "great", "unsatisfactory": "unsatisfactory",
          "crash_sw_hw": "crash (hardware/software)", "crash_pilot": "crash (pilot)", "": "not rated", "none": "not rated"}
LOGS_NOTE = ("The public logs on this computer were downloaded for the crash study, so crashed flights are far more "
             "common among them than among flights in general: the crash count beside them is not a risk.")
NOTE = ("These are other people's flights. Ratings and descriptions are the uploaders' own, not findings, and flights "
        "that look alike, in words or in their logs, can have different causes. Read them as places to look.")


def index_path() -> Path:
    override = os.environ.get("AEROFLEET_ARCHIVE_INDEX")
    if override:
        return Path(override)
    from aerofleet.assurance.ledger import key_file

    return key_file().with_name("archive_index.json.gz")


class _Index:
    def __init__(self, data: Dict[str, Any]):
        self.reports: List[Dict[str, Any]] = data.get("reports") or []
        self.logs: List[Dict[str, Any]] = data.get("logs") or []
        self.archive_entries = data.get("archive_entries")
        self.post: Dict[str, List[tuple]] = defaultdict(list)
        self.len: List[int] = []
        for i, r in enumerate(self.reports):
            toks = tokens(r["text"])
            self.len.append(len(toks))
            for t, f in Counter(toks).items():
                self.post[t].append((i, f))
        n = max(1, len(self.reports))
        self.avg = (sum(self.len) / n) if self.len else 1.0
        self.idf = {t: math.log(1 + (n - len(p) + 0.5) / (len(p) + 0.5)) for t, p in self.post.items()}
        rated = [r["rating"] for r in self.reports if r["rating"]]
        self.base_crash = (sum(r in CRASH for r in rated) / len(rated)) if rated else None

    def text_scores(self, query: List[str]) -> Dict[int, float]:
        out: Dict[int, float] = defaultdict(float)
        for t in set(query):
            for i, f in self.post.get(t, ()):
                out[i] += self.idf[t] * f * (K1 + 1) / (f + K1 * (1 - B + B * self.len[i] / self.avg))
        return out


@lru_cache(maxsize=1)
def _load(path: str, mtime: float) -> Optional[_Index]:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return _Index(json.load(f))
    except (OSError, ValueError):
        return None


def index() -> Optional[_Index]:
    p = index_path()
    return _load(str(p), p.stat().st_mtime) if p.exists() else None


def status() -> Dict[str, Any]:
    ix = index()
    if ix is None:
        return {"ready": False, "message": "The archive index is not built on this computer. Run "
                                           "`python tools/build_archive_index.py` once (it reads the public archive's "
                                           "dbinfo.json and the logs on the data drive)."}
    return {"ready": True, "reports": len(ix.reports), "logs": len(ix.logs), "archive_entries": ix.archive_entries}


def _rating(r: str) -> str:
    return RATING.get(r, r or "not rated")


def _same_kind(vehicle_filter: Optional[str], vehicle: str) -> bool:
    if not vehicle_filter:
        return True
    multi = ("rotor", "copter", "quad", "hexa", "octo", "coax")
    a, b = vehicle_filter.lower(), (vehicle or "").lower()
    return any(k in a for k in multi) == any(k in b for k in multi) and (("wing" in a) == ("wing" in b))


def search(description: str, signs: Optional[Set[str]] = None, vehicle: Optional[str] = None, limit: int = 10,
           exclude: Optional[Set[str]] = None) -> Dict[str, Any]:
    """`signs`: from the user's own reviewed flight, if one was chosen; otherwise the words' signs are used.
    `exclude`: archive log ids never to return (the user's own log, when it came from the public archive)."""
    from aerofleet.assurance.log_signs import signs_from_words

    ix = index()
    if ix is None:
        return {**status(), "text_matches": [], "log_matches": [], "note": NOTE}
    word_signs = signs_from_words(description)
    want = set(signs or ()) or word_signs
    exclude = exclude or set()
    q = tokens(description)

    scored = sorted(((s, i) for i, s in ix.text_scores(q).items() if s > 0 and _same_kind(vehicle, ix.reports[i]["type"]) and ix.reports[i]["id"] not in exclude),
                    reverse=True)
    text = []
    for s, i in scored[:limit]:
        r = ix.reports[i]
        text.append({"id": r["id"], "date": r["date"], "text": r["text"], "rating": _rating(r["rating"]),
                     "vehicle": r["type"], "airframe": r["airframe"], "minutes": r["min"], "same_text": r.get("same_text", 1),
                     "score": round(s, 2), "url": REVIEW_URL.format(id=r["id"])})
    top = [ix.reports[i]["rating"] for _, i in scored[:50] if ix.reports[i]["rating"]]
    words_summary = None
    if top:
        words_summary = {"rated": len(top), "crash": sum(r in CRASH for r in top),
                         "base_crash_share": round(ix.base_crash, 3) if ix.base_crash is not None else None}

    logs = []
    if want:
        ranked = []
        for r in ix.logs:
            if r["id"] in exclude:
                continue
            sim = similarity(want, set(r["signs"]))
            if sim > 0 and _same_kind(vehicle, r["vehicle"]):
                bonus = sum(ix.idf.get(t, 0) for t in set(q) & set(tokens(r.get("text") or ""))) if r.get("text") else 0.0
                ranked.append((sim, bonus, r))
        ranked.sort(key=lambda x: (x[0], x[1]), reverse=True)
        for sim, _, r in ranked[:limit]:
            logs.append({"id": r["id"], "date": r["date"], "signs": [SIGNS[s] for s in r["signs"] if s in SIGNS],
                         "shared": [SIGNS[s] for s in sorted(want & set(r["signs"]))], "similarity": round(sim, 2),
                         "rating": _rating(r["rating"]), "vehicle": r["vehicle"], "airframe": r["airframe"],
                         "minutes": r["min"], "text": r.get("text"), "url": REVIEW_URL.format(id=r["id"])})
        same = [r for s, _, r in ranked if s > 0]
        logs_summary = {"with_shared_sign": len(same), "of": len(ix.logs),
                        "crash": sum(r["rating"] in CRASH for r in same), "rated": sum(1 for r in same if r["rating"]),
                        "note": LOGS_NOTE}
    else:
        logs_summary = None
    return {"ready": True, "query_signs": [SIGNS[s] for s in sorted(want)], "signs_from": "your flight" if signs else "your words",
            "text_matches": text, "words_summary": words_summary, "log_matches": logs, "logs_summary": logs_summary,
            "reports": len(ix.reports), "logs": len(ix.logs), "note": NOTE}
