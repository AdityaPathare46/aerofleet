"""Approved-policy overlay for the CBF gate — per-city threshold overrides
that a human operator has explicitly approved (aerofleet/api/routes/policy.py),
never anything a council proposal writes directly.

build_cbf_gate() (aerofleet/safety/cbf_gate.py) consults get_active_policy(city)
as a fallback layer BELOW an explicit dispatch_plan value and ABOVE the
gate's own hardcoded defaults:

    dispatch_plan value  >  approved policy overlay  >  hardcoded default

This is additive: with no approved proposal for a city, get_active_policy()
returns {} and the gate behaves exactly as it did before this module existed.
"""
from __future__ import annotations

from typing import Dict, Optional

from aerofleet.data.database import get_db_session
from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)

# Process-wide cache: querying the DB on every dispatch would reintroduce
# exactly the kind of per-request latency Phase AB spent its whole effort
# removing. A proposal is approved/rejected rarely (human-gated, not
# per-order), so the cache only needs invalidating on those two actions —
# see invalidate_policy_cache(), called from aerofleet/api/routes/policy.py.
_cache: Dict[str, Dict[str, float]] = {}


def get_active_policy(city: str) -> Dict[str, float]:
    """Latest APPROVED PolicyProposal's proposed_changes for a city, or {}
    if none exists. Never raises — a lookup failure should never be able to
    block dispatch, which is the whole reason this stays out of the
    request-handling path except as a plain in-memory dict read after the
    first (cached) lookup."""
    city = (city or "").lower()
    if not city:
        return {}
    if city in _cache:
        return _cache[city]

    overlay: Dict[str, float] = {}
    try:
        from aerofleet.data.models.models import PolicyProposal

        with get_db_session() as db:
            proposal = (
                db.query(PolicyProposal)
                .filter(PolicyProposal.city == city, PolicyProposal.status == "APPROVED")
                .order_by(PolicyProposal.reviewed_at.desc())
                .first()
            )
            if proposal is not None:
                overlay = dict(proposal.proposed_changes or {})
    except Exception as exc:
        logger.warning(f"get_active_policy({city}) lookup failed, using no overlay: {exc}")
        overlay = {}

    _cache[city] = overlay
    return overlay


def invalidate_policy_cache(city: Optional[str] = None) -> None:
    """Call after approving or rejecting a proposal so the next dispatch in
    that city picks up the change immediately instead of waiting on process
    restart."""
    if city is None:
        _cache.clear()
    else:
        _cache.pop((city or "").lower(), None)
