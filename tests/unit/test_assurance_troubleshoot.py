"""Troubleshooting search over expert-diagnosed PX4 crashes (aerofleet/assurance/troubleshoot.py)."""
from aerofleet.assurance.troubleshoot import PLAYBOOK, search, tokens


def _mentioned(description):
    return {c["cause"] for c in search(description)["checklist"] if c["mentioned"]}


def test_the_causes_a_description_mentions_are_marked():
    assert "GPS / compass / estimator" in _mentioned("drone circles in position mode like a toilet bowl, then flies away")
    assert "vibration / mounting" in _mentioned("strong vibration, accelerometer clipping and altitude jumps")
    assert "battery / power" in _mentioned("battery voltage sag then the flight controller rebooted")


def test_the_checklist_follows_how_often_experts_found_each_cause_not_the_words():
    r = search("compass heading wrong, drone circles in loiter")
    found = [int(c["experts_found"].split(" of ")[0]) for c in r["checklist"][:5]]
    assert r["checklist"][0]["cause"] == "tuning / configuration" and found == sorted(found, reverse=True)
    gps = next(c for c in r["checklist"] if c["cause"] == "GPS / compass / estimator")
    assert gps["mentioned"] and "compass" in gps["matched_words"] and gps["checks"] and gps["fixes"]
    rare = search("radio link lost, receiver failsafe")["checklist"]
    assert any(c["cause"] == "radio or data link" and c["mentioned"] for c in rare)      # a rare cause still appears when named


def test_answers_carry_precedents_the_caveat_and_the_measured_accuracy():
    r = search("quad oscillates and wobbles in hover", limit=3)
    assert 0 < len(r["similar_cases"]) <= 3 and all(c["url"].startswith("https://discuss.px4.io/t/") for c in r["similar_cases"])
    assert "not a diagnosis" in r["note"] and "20%" in r["how_well_it_works"] and r["cases_searched"] == 161


def test_same_words_same_answer_and_no_match_says_so():
    q = "motor stopped and the drone flipped"
    assert search(q) == search(q)
    empty = search("hello there")
    assert not any(c["mentioned"] for c in empty["checklist"]) and empty["similar_cases"] == []
    assert "Describe what the drone did" in empty["message"]


def test_every_playbook_entry_is_complete_and_tokens_ignore_filler():
    assert all(p["symptoms"] and p["checks"] and p["fixes"] for p in PLAYBOOK.values())
    assert tokens("Hi, my drone is oscillating!") == ["oscillat"]
