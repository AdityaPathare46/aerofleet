"""
Scenario dataclasses and YAML schema definitions.

A Scenario is the complete specification of a mission test case:
  - Input parameters (what the user/pipeline feeds in)
  - Expected outputs (ground truth from real missions or physics derivation)
  - Tolerance thresholds (per-metric, configurable toward 100% strictness)
  - Metadata (source, tags, difficulty)

YAML Schema Example:
--------------------
id: "SYN-001"
name: "Standard delivery, clear weather"
type: "synthetic"
source: "AeroFleet synthetic scenario generator"
description: "Baseline single-order dispatch, no anomalies."
parameters:
  priority: "STANDARD"
  distance_km: 4.2
  payload_kg: 1.5
  wind_speed_mps: 3.0
  zone_colour: "GREEN"
expected_outputs:
  eta_minutes: 6.3
  eta_tolerance_pct: 5.0
  battery_margin_wh: 320
  battery_margin_tolerance_wh: 15.0
  cost_usd: 0.55
  cost_tolerance_pct: 10.0
  comm_link_margin_db: 8.0
  comm_tolerance_db: 1.0
  cbf_all_pass: true
  dgca_compliant: true
  safety_flags: ["nominal"]
tags: ["standard", "baseline"]
difficulty: "baseline"
max_retries: 20
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum


class ScenarioType(str, Enum):
    HISTORICAL = "historical"
    SYNTHETIC = "synthetic"
    EDGE_CASE = "edge_case"


class ScenarioDifficulty(str, Enum):
    BASELINE = "baseline"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXTREME = "extreme"


@dataclass
class ExpectedOutputs:
    """
    Ground truth expected outputs for a drone-dispatch scenario.

    Each metric has a value and a tolerance. The evaluator checks that
    the agent/council's output falls within the tolerance band.
    Tolerances start permissive and are tightened toward zero over time.
    """
    # Timing
    eta_minutes: Optional[float] = None
    eta_tolerance_pct: float = 5.0

    # Energy
    battery_margin_wh: Optional[float] = None
    battery_margin_tolerance_wh: float = 10.0

    # Cost
    cost_usd: Optional[float] = None
    cost_tolerance_pct: float = 10.0

    # Noise
    peak_noise_db: Optional[float] = None
    noise_tolerance_db: float = 5.0

    # Communications
    comm_link_margin_db: Optional[float] = None
    comm_tolerance_db: float = 1.0

    # Safety & Compliance (binary)
    cbf_all_pass: bool = True
    dgca_compliant: bool = True
    safety_flags: List[str] = field(default_factory=lambda: ["nominal"])


@dataclass
class Scenario:
    """
    Complete specification of a mission training scenario.
    """
    id: str                         # Unique identifier e.g. "HIST-001"
    name: str                       # Human-readable name
    scenario_type: ScenarioType     # historical | synthetic | edge_case
    source: str                     # Data source (NASA NSSDCA, ESA, synthetic, etc.)
    description: str
    parameters: Dict[str, Any]      # Mission input parameters
    expected: ExpectedOutputs       # Ground truth expected outputs
    tags: List[str] = field(default_factory=list)
    difficulty: ScenarioDifficulty = ScenarioDifficulty.BASELINE
    max_retries: int = 20           # Max retry attempts before giving up
    enabled: bool = True


def scenario_from_dict(data: Dict[str, Any]) -> Scenario:
    """
    Parse a YAML-loaded dict into a Scenario dataclass.

    Args:
        data: Raw dict loaded from YAML file

    Returns:
        Scenario dataclass instance
    """
    raw_expected = data.get("expected_outputs", {})
    expected = ExpectedOutputs(
        eta_minutes=raw_expected.get("eta_minutes"),
        eta_tolerance_pct=raw_expected.get("eta_tolerance_pct", 5.0),
        battery_margin_wh=raw_expected.get("battery_margin_wh"),
        battery_margin_tolerance_wh=raw_expected.get("battery_margin_tolerance_wh", 10.0),
        cost_usd=raw_expected.get("cost_usd"),
        cost_tolerance_pct=raw_expected.get("cost_tolerance_pct", 10.0),
        peak_noise_db=raw_expected.get("peak_noise_db"),
        noise_tolerance_db=raw_expected.get("noise_tolerance_db", 5.0),
        comm_link_margin_db=raw_expected.get("comm_link_margin_db"),
        comm_tolerance_db=raw_expected.get("comm_tolerance_db", 1.0),
        cbf_all_pass=raw_expected.get("cbf_all_pass", True),
        dgca_compliant=raw_expected.get("dgca_compliant", True),
        safety_flags=raw_expected.get("safety_flags", ["nominal"]),
    )

    return Scenario(
        id=data["id"],
        name=data["name"],
        scenario_type=ScenarioType(data.get("type", "synthetic")),
        source=data.get("source", "unknown"),
        description=data.get("description", ""),
        parameters=data.get("parameters", {}),
        expected=expected,
        tags=data.get("tags", []),
        difficulty=ScenarioDifficulty(data.get("difficulty", "baseline")),
        max_retries=data.get("max_retries", 20),
        enabled=data.get("enabled", True),
    )
