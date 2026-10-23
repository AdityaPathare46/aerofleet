"""Troubleshooting search: match a description of a drone problem against past crashes diagnosed by PX4 experts.

The cases (aerofleet/assurance/data/fault_cases.json, built by research/px4_log_study/build_fault_kb.py) are 161
PX4 forum threads that link a Flight Review log, with the expert's conclusion and the cause recorded by hand for
the log study. A description is matched by words (BM25), both against the cases and against a short list of the
symptoms each cause usually shows; nothing is generated and no model is called, so the same words always give
the same answer.

What it is for: a checklist and past threads that look alike. What it is not: a diagnosis. In a leave-one-out test
on the 90 threads where the expert blamed the aircraft and named a cause (research/px4_log_study/eval_troubleshoot.py,
results/px4_log_study/troubleshoot_loo.md), the cause best matched by the words was the expert's cause in 20% of
cases, below the 32% of always answering the most frequent cause. A description does not reveal the cause any more
than the log does. So the checklist is ordered by how often experts found each cause, the causes the description
mentions are marked, and the similar threads are offered to read, not as an answer.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

DATA = Path(__file__).with_name("data") / "fault_cases.json"
K1, B = 1.2, 0.75
MAX_QUERY = 4000

_STOP = set("""a about above after again against all am an and any are as at be because been before being below between
both but by can could did do does doing down during each few for from further had has have having he her here hers
him his how i if in into is it its itself just me more most my myself no nor not now of off on once only or other our
ours out over own same she should so some such than that the their them then there these they this those through to
too under until up very was we were what when where which while who whom why will with would you your yours also
get got one two see seems seem like dont im ive thanks hi hello please help anyone know think way still even
use used using px4 drone log logs flight flights review attached thank question issue problem""".split())

# Cause names as recorded in forum_expert_labels.csv. Symptoms are the words people use; checks and fixes are the
# usual first steps from PX4's documentation, written for this tool.
PLAYBOOK: Dict[str, Dict[str, Any]] = {
    "tuning / configuration": {
        "symptoms": "oscillation oscillates oscillating wobble wobbles shaking jitter jerky overshoot bounce bouncing "
                    "unstable instability pid gain gains tune tuning autotune twitch hover drift airframe frame "
                    "parameter parameters config configuration setting settings mixer geometry",
        "checks": ["Compare the drone's parameters with the fleet's approved baseline (Parameter drift).",
                   "Confirm the airframe/geometry matches the real frame and motor positions.",
                   "Look at rate-controller tracking (setpoint versus actual roll/pitch rate) in the log."],
        "fixes": ["Restore any parameter that drifted from the approved baseline, or approve it with a reason.",
                  "Retune rate gains (MC_ROLLRATE_*, MC_PITCHRATE_*) or run autotune after a hardware change.",
                  "Reduce gains if the oscillation is fast and grows with throttle."],
        "aerofleet": "parameter drift",
    },
    "GPS / compass / estimator": {
        "symptoms": "gps compass mag magnetometer heading yaw toilet bowl circle circling spiral flyaway fly away "
                    "drift drifting position hold loiter ekf ekf2 estimator innovation baro barometer altitude "
                    "height climb sink jump glitch satellites hdop interference rtk",
        "checks": ["Check GPS quality before take-off: satellites and HDOP (shown under Quality of the evidence).",
                   "Check magnetometer interference: compass heading change with throttle, distance from power wires.",
                   "Look for estimator warnings and innovation-test failures in the evidence timeline."],
        "fixes": ["Recalibrate the compass outdoors, away from metal; move the GPS/compass mast away from ESC wiring.",
                  "Wait for a good fix before arming; cover the barometer with open-cell foam against prop wash.",
                  "If headings disagree between compasses, disable the internal one near the power module."],
        "aerofleet": "evidence quality and timeline",
    },
    "motor / ESC / propeller": {
        "symptoms": "motor motors esc escs prop props propeller propellers desync spin spinning stop stopped "
                    "saturation saturated thrust flip flipped flips takeoff yaw spin direction order burnt hot",
        "checks": ["Run the actuator test: motor order and spin direction match the airframe diagram.",
                   "Check propellers are on the right motors and the right way up.",
                   "Look for one motor output at its limit before the upset (thrust loss on that arm)."],
        "fixes": ["Correct motor order, direction or propeller placement before the next flight.",
                  "Recalibrate ESCs; replace an ESC or motor that runs hot or desynchronises.",
                  "If outputs saturate in normal flight, the aircraft is under-powered for its weight."],
        "aerofleet": "flight review timeline",
    },
    "vibration / mounting": {
        "symptoms": "vibration vibrations vibe vibes clipping accel accelerometer imu mount mounting dampener "
                    "damping foam balance unbalanced altitude jump z resonance noise noisy",
        "checks": ["Compare this drone's vibration with the rest of the fleet (Vibration ranking).",
                   "Check accelerometer clipping counts in the log.",
                   "Inspect the flight-controller mount, propeller balance and loose parts."],
        "fixes": ["Soft-mount the flight controller; balance or replace propellers; tighten arms and motor screws.",
                  "Fly a short hover test after the fix and compare the vibration value with before."],
        "aerofleet": "fleet vibration ranking",
    },
    "battery / power": {
        "symptoms": "battery batteries voltage sag low cell cells brownout power reboot rebooted current "
                    "power module bec supply died shut off shutdown",
        "checks": ["Check battery voltage under load and the lowest cell before the fall.",
                   "Check the flight controller did not reboot in the air (log ends or restarts mid-flight).",
                   "Check low-battery failsafe settings (BAT_* and COM_LOW_BAT_ACT)."],
        "fixes": ["Replace weak packs; set the battery failsafe to return or land with margin.",
                  "Power the flight controller from a separate, adequate BEC or power module."],
        "aerofleet": "static checks",
    },
    "software / firmware bug": {
        "symptoms": "firmware bug version release update upgrade beta master main regression crash software "
                    "stack driver uorb",
        "checks": ["Record the firmware version and whether the problem started after an update.",
                   "Search PX4 GitHub issues and release notes for the same version and symptom."],
        "fixes": ["Move to the latest stable release; report it on GitHub with the Flight Review link."],
        "aerofleet": "flight review",
    },
    "pilot input / handling": {
        "symptoms": "pilot stick sticks manual stabilized acro throttle input inputs operator landing landed "
                    "hard tree hit wall obstacle",
        "checks": ["Look at the stick inputs and flight mode at the moment of the upset.",
                   "Check the aircraft did what the sticks asked before concluding it misbehaved."],
        "fixes": ["Fly assisted modes (Position) while training; set geofence and return altitude for the site."],
        "aerofleet": "flight review timeline",
    },
    "airframe / mechanical": {
        "symptoms": "frame arm arms broke broken crack cracked mechanical screw screws loose fell apart structure "
                    "landing gear",
        "checks": ["Inspect arms, motor mounts and screws; check for a part that came loose in flight."],
        "fixes": ["Replace damaged parts; use thread-locker on motor screws; check before each flight."],
        "aerofleet": "pre-flight checklist",
    },
    "radio or data link": {
        "symptoms": "rc radio receiver transmitter link signal lost loss telemetry range failsafe datalink "
                    "connection disconnect",
        "checks": ["Check RC-loss and data-link-loss failsafe actions (NAV_RCL_ACT, NAV_DLL_ACT, COM_RC_LOSS_T)."],
        "fixes": ["Set the loss-of-link action to return or land; check antenna placement and range."],
        "aerofleet": "static checks",
    },
    "wrong mode or mode switch": {
        "symptoms": "mode modes switch switched switching position altitude offboard mission rtl return land "
                    "unexpected",
        "checks": ["Check the mode changes in the evidence timeline and the RC switch mapping."],
        "fixes": ["Fix the mode-switch mapping; rehearse switching modes at a safe height."],
        "aerofleet": "flight review timeline",
    },
}

CHECKLIST = 5
NOT_A_DIAGNOSIS = ("A checklist and past cases, not a diagnosis of this drone. The checks are in the order PX4 experts most "
                   "often found each cause; causes your description mentions are marked. Confirm on the aircraft.")
TESTED = ("Tested on 90 expert-diagnosed crashes, each held out in turn: the cause best matched by the words was the "
          "expert's cause in 20% of cases, against 32% for always answering the most frequent cause. Descriptions "
          "do not reveal the cause, which is why the checklist follows how often each cause was found.")


def _stem(w: str) -> str:
    for suf in ("ations", "ation", "ing", "ers", "er", "es", "ed", "s"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def tokens(text: str) -> List[str]:
    words = re.findall(r"[a-z][a-z0-9]+", (text or "").lower())
    return [_stem(w) for w in words if w not in _STOP and len(w) > 1]


class _BM25:
    def __init__(self, docs: List[List[str]]):
        self.docs = [Counter(d) for d in docs]
        self.len = [len(d) for d in docs]
        self.avg = (sum(self.len) / len(docs)) if docs else 1.0
        df = Counter(t for d in docs for t in set(d))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: List[str]) -> List[float]:
        q = set(query)
        out = []
        for d, ln in zip(self.docs, self.len):
            s = 0.0
            for t in q:
                f = d.get(t)
                if f:
                    s += self.idf[t] * f * (K1 + 1) / (f + K1 * (1 - B + B * ln / self.avg))
            out.append(s)
        return out


@lru_cache(maxsize=1)
def _index():
    cases = json.loads(DATA.read_text())["cases"]
    case_ix = _BM25([tokens(c["title"]) * 2 + c["terms"] for c in cases])
    causes = list(PLAYBOOK)
    cause_ix = _BM25([tokens(PLAYBOOK[c]["symptoms"]) for c in causes])
    crash = [c for c in cases if c["is_crash"] and c["expert_conclusion"] in ("drone", "both")]
    base = Counter(c["cause"] for c in crash)
    return cases, case_ix, causes, cause_ix, base, len(crash)


def search(description: str, limit: int = 5, vibration: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """A checklist ordered by how often experts found each cause, the causes the description mentions, and the
    most similar past threads."""
    cases, case_ix, causes, cause_ix, base, n_crash = _index()
    q = tokens((description or "")[:MAX_QUERY])
    known = set(cause_ix.idf) | set(case_ix.idf)
    used = sorted(set(t for t in q if t in known))
    case_s = case_ix.scores(q)
    order = sorted((i for i, s in enumerate(case_s) if s > 0), key=lambda i: (-case_s[i], cases[i]["topic_id"]))
    top = order[:limit]

    # A cause scores on its own symptom words plus the similar cases that experts put down to it.
    cause_s = dict(zip(causes, cause_ix.scores(q)))
    best = max(case_s) if case_s and max(case_s) > 0 else 1.0
    votes = defaultdict(float)
    for i in order[:15]:
        votes[cases[i]["cause"]] += case_s[i] / best
    ranked = sorted(causes, key=lambda c: -(cause_s[c] + votes.get(c, 0.0)))
    matches = []                                          # kept for the leave-one-out test; not used to order the checklist
    for c in ranked:
        score = cause_s[c] + votes.get(c, 0.0)
        if score <= 0 or len(matches) == 3:
            break
        matches.append({"cause": c, "score": round(score, 2)})
    said = {_stem(w): w for w in re.findall(r"[a-z][a-z0-9]+", (description or "")[:MAX_QUERY].lower())}
    words = {c: sorted(said.get(t, t) for t in set(q) & set(tokens(PLAYBOOK[c]["symptoms"]))) for c in causes}
    common = [c for c, k in base.most_common() if k >= 2 and c in PLAYBOOK][:CHECKLIST]
    common += [c for c in causes if words[c] and c not in common]
    checklist = [{"cause": c, "experts_found": f"{base.get(c, 0)} of {n_crash}", "mentioned": bool(words[c]),
                  "matched_words": words[c], "checks": PLAYBOOK[c]["checks"], "fixes": PLAYBOOK[c]["fixes"],
                  "aerofleet_check": PLAYBOOK[c]["aerofleet"]} for c in common]

    similar = [{"title": cases[i]["title"], "url": cases[i]["url"], "score": round(case_s[i], 2),
                "expert_conclusion": cases[i]["expert_conclusion"], "cause": cases[i]["cause"],
                "who_diagnosed": cases[i]["who"], "poster_confirmed_fix": cases[i]["poster_confirmed"],
                "flight_review_logs": [f"https://review.px4.io/plot_app?log={x}" for x in cases[i]["log_ids"][:3]]}
               for i in top]
    out = {"query_words_used": used, "checklist": checklist, "word_matches": matches, "similar_cases": similar,
           "cases_searched": len(cases), "note": NOT_A_DIAGNOSIS, "how_well_it_works": TESTED}
    if not used:
        out["message"] = "None of the words matched a known symptom. Describe what the drone did, e.g. 'wobbles in hover', 'flipped on take-off', 'circles in position mode'."
    if vibration:
        out["this_drone_vibration"] = vibration
    return out
