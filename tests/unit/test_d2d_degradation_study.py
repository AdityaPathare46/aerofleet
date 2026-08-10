"""Smoke test for scenario_engine/d2d_degradation_study.py — confirms the
study runs end to end and produces a well-formed, internally-consistent
report. Doesn't assert specific statistical values (that's what running the
study for real and reading scenario_reports/ is for) — only that the
plumbing (simulation, both CBF evaluations, aggregation) doesn't break.
"""
import pytest

from scenario_engine.d2d_degradation_study import run_study

pytestmark = pytest.mark.unit


class TestRunStudy:
    def test_produces_well_formed_report(self):
        report = run_study(trials=20, seed=1)
        assert report["metric_1_verdict_equivalence"]["n_trials"] == 20
        assert 0.0 <= report["metric_1_verdict_equivalence"]["agreement_rate"] <= 1.0

    def test_is_deterministic_given_a_seed(self):
        report_a = run_study(trials=50, seed=7)
        report_b = run_study(trials=50, seed=7)
        assert report_a["metric_1_verdict_equivalence"] == report_b["metric_1_verdict_equivalence"]
        assert report_a["metric_3_undetected_conflict_rate"] == report_b["metric_3_undetected_conflict_rate"]

    def test_different_seeds_can_differ(self):
        report_a = run_study(trials=50, seed=1)
        report_b = run_study(trials=50, seed=2)
        # Not a hard guarantee for every possible pair of seeds, but true
        # for these two — catches an accidentally-unseeded RNG regression.
        assert report_a != report_b

    def test_no_d2d_baseline_always_catches_zero_conflicts(self):
        # This is true by construction (see module docstring) — asserted
        # explicitly so a future refactor can't silently change it.
        report = run_study(trials=200, seed=3)
        assert report["metric_3_undetected_conflict_rate"]["conflicts_caught_by_no_d2d_baseline"] == 0

    def test_degradation_response_latency_is_closed_form(self):
        report = run_study(trials=5, seed=1, heartbeat_interval_s=2.0)
        m2 = report["metric_2_degradation_response_latency"]
        assert m2["time_to_degraded_s"] == m2["degraded_at_missed_heartbeats"] * 2.0
        assert m2["time_to_store_forward_s"] == m2["store_forward_at_missed_heartbeats"] * 2.0

    def test_zero_packet_loss_and_zero_broadcast_interval_gives_perfect_agreement(self):
        # With no loss and a broadcast every simulated tick, D2D data is
        # never stale, so it should always agree with the centralized verdict.
        report = run_study(trials=100, seed=1, packet_loss_rate=0.0, broadcast_interval_s=1.0, dt_s=1.0)
        assert report["metric_1_verdict_equivalence"]["agreement_rate"] == 1.0


class TestStressSampling:
    """Phase AL — importance-sampled adversarial trials for a defensible
    d2d_catch_rate confidence interval, on top of Phase AD's original
    natural-rate-only study."""

    def test_default_stress_fraction_reproduces_original_numbers_bit_for_bit(self):
        """The single most important regression test in this file: adding
        stress_fraction must not silently change Phase AD's already-published
        natural-rate numbers for existing callers that don't pass it."""
        report = run_study(trials=300, seed=11)
        assert report["parameters"]["stress_fraction"] == 0.0
        assert report["parameters"]["n_stress_trials"] == 0
        assert report["parameters"]["n_natural_trials"] == 300
        assert report["metric_3b_stress_undetected_conflict_rate"]["true_conflicts_during_outage"] == 0

    def test_stress_fraction_produces_far_more_true_conflicts_than_natural_rate(self):
        """The actual fix: importance sampling must produce a usably large
        sample of true conflicts, not the ~8-out-of-5000 Phase AD's natural
        rate produced."""
        report = run_study(trials=2000, seed=5, stress_fraction=0.6)
        natural_conflicts = report["metric_3_undetected_conflict_rate"]["true_conflicts_during_outage"]
        stress_conflicts = report["metric_3b_stress_undetected_conflict_rate"]["true_conflicts_during_outage"]
        assert stress_conflicts > natural_conflicts
        assert stress_conflicts >= 50  # comfortably enough for a tight Wilson CI

    def test_stress_catch_rate_ci_is_present_and_tight_with_enough_trials(self):
        report = run_study(trials=2000, seed=5, stress_fraction=0.6)
        m3b = report["metric_3b_stress_undetected_conflict_rate"]
        ci = m3b["d2d_catch_rate_95pct_wilson_ci"]
        assert ci is not None
        lower, upper = ci
        assert 0.0 <= lower <= m3b["d2d_catch_rate"] <= upper <= 1.0
        assert (upper - lower) < 0.25  # "defensible" — not the wide interval an n=8 sample would give

    def test_wilson_ci_is_none_with_zero_conflicts(self):
        report = run_study(trials=10, seed=1, stress_fraction=0.0)
        assert report["metric_3b_stress_undetected_conflict_rate"]["d2d_catch_rate_95pct_wilson_ci"] is None

    def test_stress_sampling_is_deterministic_given_a_seed(self):
        report_a = run_study(trials=500, seed=9, stress_fraction=0.5)
        report_b = run_study(trials=500, seed=9, stress_fraction=0.5)
        assert report_a["metric_3b_stress_undetected_conflict_rate"] == report_b["metric_3b_stress_undetected_conflict_rate"]

    def test_natural_and_stress_trial_counts_sum_to_total(self):
        report = run_study(trials=777, seed=3, stress_fraction=0.3)
        assert report["parameters"]["n_natural_trials"] + report["parameters"]["n_stress_trials"] == 777
