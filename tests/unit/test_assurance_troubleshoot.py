"""Troubleshooting search over expert-diagnosed PX4 crashes (aerofleet/assurance/troubleshoot.py)."""
from aerofleet.assurance.troubleshoot import PLAYBOOK, search, tokens


def test_symptoms_point_to_the_cause_experts_usually_found():
    assert search("drone circles in position mode like a toilet bowl, then flies away")["likely_causes"][0]["cause"] == "GPS / compass / estimator"
    assert search("strong vibration, accelerometer clipping and altitude jumps")["likely_causes"][0]["cause"] == "vibration / mounting"
    assert search("battery voltage sag then the flight controller rebooted")["likely_causes"][0]["cause"] == "battery / power"


def test_answers_carry_checks_precedents_and_the_caveat():
    r = search("quad oscillates and wobbles in hover", limit=3)
    top = r["likely_causes"][0]
    assert top["checks"] and top["fixes"] and " of " in top["share_of_expert_diagnosed_crashes"]
    assert 0 < len(r["similar_cases"]) <= 3 and all(c["url"].startswith("https://discuss.px4.io/t/") for c in r["similar_cases"])
    assert "does not diagnose" in r["note"] and r["cases_searched"] == 161


def test_same_words_same_answer_and_no_match_says_so():
    q = "motor stopped and the drone flipped"
    assert search(q) == search(q)
    empty = search("hello there")
    assert empty["likely_causes"] == [] and empty["similar_cases"] == [] and "Describe what the drone did" in empty["message"]


def test_every_playbook_entry_is_complete_and_tokens_ignore_filler():
    assert all(p["symptoms"] and p["checks"] and p["fixes"] for p in PLAYBOOK.values())
    assert tokens("Hi, my drone is oscillating!") == ["oscillat"]
