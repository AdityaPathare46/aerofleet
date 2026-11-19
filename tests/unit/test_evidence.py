"""The in-app recomputation of the paper's results (aerofleet/evidence.py) gives the paper's numbers, from the same
arithmetic as the study's scripts, and each test was declared before its result was committed."""
import shutil
import sys
from pathlib import Path

import pytest

from aerofleet.evidence import CLAIMS, between_drones, claims, within_drone

ROOT = Path(__file__).resolve().parents[2]
PAPER = " ".join((ROOT / "docs/paper/latex/main.tex").read_text().split())


def test_every_claim_recomputes_to_the_number_the_paper_states():
    out = {c["id"]: c for c in claims()}
    assert all(c["matches_paper"] for c in out.values()), {k: c["recomputed"] for k, c in out.items()}
    assert out["attribution"]["recomputed"] == 0.47 and out["attribution"]["n"] == 112
    assert out["within"]["recomputed"] == 0.48 and out["within"]["ci"] == [0.38, 0.58] and out["within"]["n"] == 61
    assert round(out["within"]["p"], 2) == 0.67
    assert out["between"]["recomputed"] == 0.67 and out["between"]["n"] == 60 and round(out["between"]["p"], 4) == 0.0023
    assert out["screening"]["recomputed"] == 1.77 and out["screening"]["stored"] is True


def test_the_paper_states_each_number_we_compare_with():
    for c in CLAIMS:
        assert " ".join(c["paper_text"].split()) in PAPER, c["id"]


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git history")
def test_each_test_was_declared_before_its_result():
    for c in claims():
        if c["declared"].get("date") is None:
            pytest.skip("commit history not available (e.g. a shallow clone)")
        assert c["declared_before_result"], c["id"]


def test_same_ranks_as_the_studys_figure_script():
    pytest.importorskip("matplotlib")
    sys.path.insert(0, str(ROOT / "research" / "px4_log_study"))
    import paper_figures as pf

    assert len(pf._within_ranks("vib_p95")) == within_drone()["n"]
    assert pf._within_ranks("vib_p95").mean() == pytest.approx(within_drone()["value"])
    assert pf._between_ranks("vib_p95").mean() == pytest.approx(between_drones()["value"])
