"""Moved to aerofleet/compliance/flight_checks.py: these are deterministic calculators (route, battery, geofence,
weather, cost, DGCA, link budget) that the earlier prototype's AI agents called as tools. Kept so legacy imports work."""
from aerofleet.compliance.flight_checks import *  # noqa: F401,F403
from aerofleet.compliance.flight_checks import AgentTools  # noqa: F401
