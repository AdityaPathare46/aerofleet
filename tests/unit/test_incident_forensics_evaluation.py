"""Smoke test for scenario_engine/incident_forensics_evaluation.py —
confirms the labeled-evaluation harness runs end to end and produces a
well-formed report. Doesn't assert a specific F1 (mock mode trivially
scores 1.0 on the 5 regex-mappable factors by construction — see the
module docstring); only that the plumbing (labeled dataset -> worker ->
per-factor scoring) doesn't break.
"""
import pytest

from scenario_engine.incident_forensics_evaluation import LABELED_DATASET, run_evaluation

pytestmark = pytest.mark.unit


class TestRunEvaluation:
    def test_produces_a_well_formed_report(self):
        report = run_evaluation()
        assert report["n_labeled_incidents"] == len(LABELED_DATASET)
        assert 0.0 <= report["macro_f1"] <= 1.0

    def test_mock_mode_scores_perfectly_on_regex_mappable_factors(self):
        # This is a pipeline correctness check, not a capability claim —
        # the mock backend's domain assessment IS the regex ground-truth
        # check, so a mismatch here would mean the harness itself is
        # broken, not that the "model" reasoned badly.
        report = run_evaluation()
        for factor in ("battery_energy", "airspace_conflict", "weather_environmental",
                       "communications_link", "ops_scheduling_capacity"):
            assert report["per_factor_scores"][factor]["f1"] == 1.0

    def test_narrative_only_factors_are_excluded_not_faked(self):
        report = run_evaluation()
        for factor in ("routing_navigation", "cross_check_anomaly"):
            assert "note" in report["per_factor_scores"][factor]
            assert "f1" not in report["per_factor_scores"][factor]

    def test_no_violation_control_case_predicts_nothing_contributed(self):
        report = run_evaluation()
        control = next(r for r in report["per_incident_results"] if r["label"] == "no_real_violation_control")
        assert all(v != "CONTRIBUTED" for v in control["predictions"].values())
