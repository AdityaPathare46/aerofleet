"""Moved to aerofleet/compliance/report.py (deterministic compliance report). Kept so legacy imports work."""
from aerofleet.compliance.report import *  # noqa: F401,F403
from aerofleet.compliance.report import (  # noqa: F401
    DomainStatus, _airworthiness_domain, _classify_dgca_issues, _energy_domain, _financial_domain, _regulatory_domain,
    _airspace_safety_domain, compute_compliance_report)
