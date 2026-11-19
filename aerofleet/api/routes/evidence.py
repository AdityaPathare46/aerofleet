"""GET /api/v1/evidence/claims: the paper's headline results recomputed now from the committed data, with the commits
that declared each test and added its result (aerofleet/evidence.py). Read-only and public: it uses no user data."""
from typing import Any, Dict, List

from fastapi import APIRouter

router = APIRouter()


@router.get("/claims")
async def evidence_claims() -> List[Dict[str, Any]]:
    from aerofleet.evidence import claims

    return claims()
