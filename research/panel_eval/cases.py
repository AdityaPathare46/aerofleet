"""Synthetic flight-review episodes with a known cause, for evaluating the review panel.

Each case is built from a scenario, not from the comparator's thresholds: the injected cause has a
continuous strength, and half the cases are SUBTLE (a real change that stays inside the plain rule's
thresholds, e.g. satellites falling from 14 to 7 where the rule fires below 6). One case in three also
carries a harmless distractor in another slice. UNKNOWN cases have nothing notable anywhere; the right
answer for them is to defer to a person.

These are generated facts, not real incidents: the evaluation measures reading-the-evidence skill on a
controlled task. It does not show how often each cause occurs in the field.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List

from aerofleet.assurance.review_panel import episode_facts

TRUTHS = ("PILOT_MANUAL_CONTROL", "GPS_DEGRADED", "WIND_OR_ENVIRONMENT", "LOW_BATTERY_RESPONSE", "CONFIGURATION", "UNKNOWN")
SEED = 20261012


def make_case(index: int, seed: int = SEED) -> Dict[str, Any]:
    rng = random.Random(seed * 100003 + index)
    truth = TRUTHS[index % len(TRUTHS)]
    subtle = (index // len(TRUTHS)) % 2 == 1 and truth not in ("CONFIGURATION", "UNKNOWN")
    start, dur = rng.uniform(40, 70), rng.uniform(6, 35)
    t0 = 1000.0
    cruise = rng.uniform(9, 13)
    slow = 1.0
    if truth == "WIND_OR_ENVIRONMENT":
        slow = rng.uniform(0.72, 0.85) if subtle else rng.uniform(0.4, 0.6)
    track, lat = [], 18.52
    for i in range(140):
        v = cruise * (slow if start - 2 <= i <= start + dur + 2 else 1.0)
        lat += v / 111_320.0
        track.append((t0 + i, lat, 73.85, 60.0))

    modes = [(t0, "GUIDED"), (t0 + 8, "AUTO")]
    if truth == "PILOT_MANUAL_CONTROL":
        took = start + (dur - rng.uniform(2, 4) if subtle else rng.uniform(0, 3))
        modes += [(t0 + took, rng.choice(["LOITER", "ALT_HOLD", "POSHOLD", "STABILIZE"])), (t0 + took + (rng.uniform(2, 4) if subtle else rng.uniform(10, 18)), "AUTO")]

    base_sats, base_hdop = rng.randint(12, 16), rng.uniform(0.7, 1.1)
    bad_gps = None
    if truth == "GPS_DEGRADED":
        bad_gps = (rng.randint(7, 8), rng.uniform(1.8, 2.4), 3) if subtle else (rng.randint(3, 5), rng.uniform(3.0, 5.0), rng.choice([2, 3]))
    base_v, base_pct = rng.uniform(15.2, 16.4), rng.uniform(45, 85)
    bad_batt = None
    if truth == "LOW_BATTERY_RESPONSE":
        bad_batt = (base_v - rng.uniform(1.0, 1.5), rng.uniform(22, 28)) if subtle else (base_v - rng.uniform(1.6, 2.4), rng.uniform(8, 18))
        base_pct = bad_batt[1] + rng.uniform(4, 8)
    drift: List[Dict[str, Any]] = []
    if truth == "CONFIGURATION":
        drift = [{"severity": rng.choice(["CRITICAL", "HIGH"]), "approved": False} for _ in range(rng.randint(1, 2))]

    distractor = None
    if rng.random() < 0.33:
        options = [o for o in ("gps", "battery", "settings") if {"gps": "GPS_DEGRADED", "battery": "LOW_BATTERY_RESPONSE", "settings": "CONFIGURATION"}[o] != truth]
        distractor = rng.choice(options)
    if distractor == "settings":
        drift = drift + [{"severity": "HIGH", "approved": True}]          # an approved change is not a cause

    def in_ep(t):
        return start <= t <= start + dur

    gps = [(t0 + i, *(bad_gps if bad_gps and in_ep(i) else ((base_sats - 2, base_hdop + 0.2, 3) if distractor == "gps" and in_ep(i) else (base_sats, base_hdop, 3))))
           for i in range(140)]
    battery = [(t0 + i, *(bad_batt if bad_batt and i >= start - 1 else ((base_v - 0.2, 35.0) if distractor == "battery" and base_pct > 40 and in_ep(i) else (base_v, base_pct))))
               for i in range(140)]
    episode = {"kind": "off_route", "start_s": round(start, 1), "duration_s": round(dur, 1), "max_m": round(rng.uniform(35, 150), 1)}
    facts = episode_facts(episode, track, modes, battery=battery, gps=gps, drift_changes=drift)
    return {"id": f"PE-{index:04d}", "truth": truth, "subtle": subtle, "distractor": distractor, "facts": facts}


def make_cases(n: int, seed: int = SEED) -> List[Dict[str, Any]]:
    return [make_case(i, seed) for i in range(n)]
