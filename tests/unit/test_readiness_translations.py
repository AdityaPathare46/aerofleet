"""Every reason the readiness rules can give has an English, Hindi and Marathi wording, and the three agree on keys."""
import os
import re

from aerofleet.assurance.readiness import assess

TS = os.path.join(os.path.dirname(__file__), "..", "..", "tauri-app", "src", "lib", "readinessText.ts")


def _keys():
    src = open(TS, encoding="utf-8").read()
    out = {}
    for lang in ("en", "hi", "mr"):
        block = src.split(f"const {lang}: Dict = {{", 1)[1].split("\n}\n", 1)[0]
        out[lang] = set(re.findall(r"(?:^|[{,\n]\s*)(\w+):\s*['\"]", block))
    return out


def _all_codes():
    codes = set()
    for reg in (None, {"uin": "U", "status": "RECORDED"}):
        for settings in (None, {"verdict": "BLOCK", "critical": ["A"], "limits": []}, {"verdict": "REVIEW", "critical": [], "limits": ["B"]}):
            last = {"warnings": ["w1", "w2", "w3", "w4"], "critical_in_flight": 1, "deviated": True}
            codes |= {r["code"] for r in assess("D", settings, reg, last)["reasons"]}
    return codes


def test_the_three_languages_have_the_same_keys():
    k = _keys()
    assert k["en"] and k["en"] == k["hi"] == k["mr"], (k["en"] ^ k["hi"], k["en"] ^ k["mr"])


def test_every_reason_code_and_place_is_translated():
    k = _keys()["en"]
    codes = _all_codes()
    assert codes == {"no_uin", "uin_unverified", "settings_never", "critical_changed", "limit_changed",
                     "critical_in_flight", "deviated", "warning", "more_warnings"}
    assert codes <= k and {"settings", "flight", "register", "READY", "CHECK_FIRST", "DO_NOT_FLY"} <= k
