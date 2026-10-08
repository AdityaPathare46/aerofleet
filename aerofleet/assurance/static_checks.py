"""Run the flight-controller compliance rules on an uploaded parameter file — no drone connected.

The 59 rules in aerofleet/hardware/compliance_rules.py were written for a live MAVLink inspection.
A parameter file answers only some of them, so this report says, per rule, which kind it is:

  evaluated      decided from the file (PASS / WARN / FAIL)
  needs_live     needs sensor or telemetry data, or a parameter that is not in the file (UNKNOWN)
  manual         a physical check a person does (MANUAL)

The file verdict is about the evaluated rules only: FAIL, WARN or PASS — and it always states how
many rules it could not answer, so a pass here is never mistaken for a full inspection.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from aerofleet.hardware.compliance_rules import InspectionContext, build_report
from aerofleet.hardware.fc_inspector import FCSnapshot

SOURCE_PARAM_FILE = "param_file"


def checks_from_params(params: Mapping[str, float], context: Optional[InspectionContext] = None) -> Dict[str, Any]:
    snapshot = FCSnapshot.from_dict({"params": dict(params), "source": SOURCE_PARAM_FILE, "connection": "file"})
    # bench_mode: no GPS fix or live link is expected from a file
    full = build_report(snapshot, context or InspectionContext(bench_mode=True))
    groups: Dict[str, list] = {"evaluated": [], "needs_live": [], "manual": []}
    for c in full["checks"]:
        key = "manual" if c["status"] == "MANUAL" else "needs_live" if c["status"] == "UNKNOWN" else "evaluated"
        groups[key].append({k: c[k] for k in ("id", "category", "title", "status", "detail", "fix", "required", "evidence")})
    statuses = [c["status"] for c in groups["evaluated"]]
    verdict = "FAIL" if "FAIL" in statuses else "WARN" if "WARN" in statuses else "PASS" if statuses else "NOTHING_EVALUATED"
    return {
        "source": SOURCE_PARAM_FILE,
        "verdict": verdict,
        "counts": {"total": len(full["checks"]), "evaluated": len(statuses), "needs_live": len(groups["needs_live"]),
                   "manual": len(groups["manual"]), "PASS": statuses.count("PASS"), "WARN": statuses.count("WARN"),
                   "FAIL": statuses.count("FAIL")},
        "note": "Decided from the parameter file alone. Rules under needs_live and manual are not covered by this verdict.",
        "rules_version": full.get("rules_version"),
        **groups,
    }
