"""Unit tests for aerofleet/agents/compliance_report.py — the deterministic,
synchronous, multi-domain compliance report. Not a gate: these tests only
check the report's own classification logic, using AgentTools.
dgca_compliance_check() (the real, reused function) directly for the
regulatory-mapping tests rather than re-deriving its issue strings by hand.
"""
import pytest

from aerofleet.agents.compliance_report import (
    DomainStatus,
    compute_compliance_report,
)
from aerofleet.agents.tools import AgentTools

pytestmark = pytest.mark.unit


def _plan(**overrides):
    base = {
        "payload_kg": 1.0,
        "battery_margin_wh": 100.0,
        "energy_wh_required": 20.0,
        "altitude_m": 60.0,
        "in_red_zone": False,
        "in_yellow_zone": False,
    }
    base.update(overrides)
    return base


class TestRegulatoryDomain:
    """The exact mapping rule resolved from AgentTools.dgca_compliance_check()'s
    real 4 issue strings — hard rule violations dominate soft/administrative
    ones."""

    def test_clean_plan_is_compliant(self):
        report = compute_compliance_report(_plan(), safety_margin_summary={})
        assert report["domains"]["regulatory"]["status"] == DomainStatus.COMPLIANT.value

    def test_red_zone_is_non_compliant(self):
        report = compute_compliance_report(_plan(in_red_zone=True), safety_margin_summary={})
        assert report["domains"]["regulatory"]["status"] == DomainStatus.NON_COMPLIANT.value

    def test_missing_uin_only_is_at_risk_not_non_compliant(self):
        report = compute_compliance_report(_plan(uin_registered=False), safety_margin_summary={})
        assert report["domains"]["regulatory"]["status"] == DomainStatus.AT_RISK.value

    def test_missing_atc_permission_in_yellow_zone_is_at_risk(self):
        report = compute_compliance_report(
            _plan(in_yellow_zone=True, atc_permission=False), safety_margin_summary={},
        )
        assert report["domains"]["regulatory"]["status"] == DomainStatus.AT_RISK.value

    def test_red_zone_plus_missing_uin_is_non_compliant_not_at_risk(self):
        # A hard violation must dominate even when a soft issue is also present.
        report = compute_compliance_report(
            _plan(in_red_zone=True, uin_registered=False), safety_margin_summary={},
        )
        assert report["domains"]["regulatory"]["status"] == DomainStatus.NON_COMPLIANT.value

    def test_altitude_over_ceiling_is_non_compliant(self):
        report = compute_compliance_report(_plan(altitude_m=150.0), safety_margin_summary={})
        assert report["domains"]["regulatory"]["status"] == DomainStatus.NON_COMPLIANT.value

    def test_reuses_the_real_agent_tools_function_not_a_reimplementation(self):
        # Sanity check that our mapping is actually driven by real output,
        # not a parallel hand-rolled copy of the same logic.
        direct = AgentTools.dgca_compliance_check(
            zone_color="RED", uin_registered=True, atc_permission=False, altitude_m=60.0,
        )
        report = compute_compliance_report(_plan(in_red_zone=True), safety_margin_summary={})
        assert report["domains"]["regulatory"]["issues"] == direct["issues"]


class TestAirworthinessDomain:
    def test_small_category_classified_correctly(self):
        report = compute_compliance_report(
            _plan(payload_kg=3.0), safety_margin_summary={}, drone_weight_kg=10.0,
        )
        assert report["domains"]["airworthiness"]["category"] == "Small"
        assert report["domains"]["airworthiness"]["status"] == DomainStatus.COMPLIANT.value

    def test_unknown_weight_is_at_risk(self):
        report = compute_compliance_report(_plan(), safety_margin_summary={}, drone_weight_kg=None)
        assert report["domains"]["airworthiness"]["status"] == DomainStatus.AT_RISK.value

    def test_near_a_category_boundary_is_at_risk(self):
        # 24.5kg total is within 10% of the 25kg Small/Medium boundary.
        report = compute_compliance_report(
            _plan(payload_kg=0.0), safety_margin_summary={}, drone_weight_kg=24.5,
        )
        assert report["domains"]["airworthiness"]["status"] == DomainStatus.AT_RISK.value

    def test_comfortably_within_a_band_is_compliant(self):
        report = compute_compliance_report(
            _plan(payload_kg=0.0), safety_margin_summary={}, drone_weight_kg=10.0,
        )
        assert report["domains"]["airworthiness"]["status"] == DomainStatus.COMPLIANT.value


class TestEnergyDomain:
    def test_negative_margin_is_non_compliant(self):
        report = compute_compliance_report(
            _plan(battery_margin_wh=-5.0), safety_margin_summary={}, battery_reserve_wh=50.0,
        )
        assert report["domains"]["energy"]["status"] == DomainStatus.NON_COMPLIANT.value

    def test_margin_below_reserve_is_at_risk(self):
        report = compute_compliance_report(
            _plan(battery_margin_wh=20.0), safety_margin_summary={}, battery_reserve_wh=50.0,
        )
        assert report["domains"]["energy"]["status"] == DomainStatus.AT_RISK.value

    def test_margin_above_reserve_is_compliant(self):
        report = compute_compliance_report(
            _plan(battery_margin_wh=200.0), safety_margin_summary={}, battery_reserve_wh=50.0,
        )
        assert report["domains"]["energy"]["status"] == DomainStatus.COMPLIANT.value


class TestAirspaceSafetyDomain:
    def test_any_negative_margin_is_non_compliant(self):
        report = compute_compliance_report(
            _plan(), safety_margin_summary={"min_separation": -1.0, "wind_limit": 5.0},
        )
        assert report["domains"]["airspace_safety"]["status"] == DomainStatus.NON_COMPLIANT.value
        assert "min_separation" in report["domains"]["airspace_safety"]["violated_constraints"]

    def test_all_healthy_margins_are_compliant(self):
        report = compute_compliance_report(
            _plan(), safety_margin_summary={"min_separation": 10.0, "wind_limit": 5.0},
        )
        assert report["domains"]["airspace_safety"]["status"] == DomainStatus.COMPLIANT.value

    def test_thin_but_positive_margin_is_still_compliant(self):
        # Deliberately no invented "near zero" threshold — see the
        # function's own docstring for why a flat cutoff across
        # differently-scaled constraints (metres vs Wh vs a 1e-4-capped
        # probability) would be actively misleading, not conservative.
        report = compute_compliance_report(
            _plan(), safety_margin_summary={"min_separation": 0.2, "collision_probability": 0.0001},
        )
        assert report["domains"]["airspace_safety"]["status"] == DomainStatus.COMPLIANT.value


class TestFinancialDomain:
    def test_under_budget_is_compliant(self):
        report = compute_compliance_report(
            _plan(energy_wh_required=10.0), safety_margin_summary={}, budget_ceiling=1000.0,
        )
        assert report["domains"]["financial"]["status"] == DomainStatus.COMPLIANT.value

    def test_over_budget_is_non_compliant(self):
        report = compute_compliance_report(
            _plan(energy_wh_required=10.0), safety_margin_summary={}, budget_ceiling=1.0,
        )
        assert report["domains"]["financial"]["status"] == DomainStatus.NON_COMPLIANT.value


class TestOverallStatus:
    def test_overall_status_is_the_worst_of_all_domains(self):
        # Force airspace_safety to NON_COMPLIANT while everything else is clean.
        report = compute_compliance_report(
            _plan(), safety_margin_summary={"min_separation": -1.0}, drone_weight_kg=10.0, battery_reserve_wh=10.0,
        )
        assert report["domains"]["energy"]["status"] == DomainStatus.COMPLIANT.value
        assert report["overall_status"] == DomainStatus.NON_COMPLIANT.value

    def test_all_compliant_domains_give_compliant_overall(self):
        report = compute_compliance_report(
            _plan(), safety_margin_summary={"min_separation": 10.0}, drone_weight_kg=10.0, battery_reserve_wh=10.0,
        )
        assert all(d["status"] == DomainStatus.COMPLIANT.value for d in report["domains"].values())
        assert report["overall_status"] == DomainStatus.COMPLIANT.value
