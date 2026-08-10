"""Real, publicly-known DGCA-relevant restricted sites for AeroFleet's
supported cities — Pune and Mumbai.

Radii follow DGCA Drone Rules 2021's stated distances where the rule gives
an explicit figure: 5 km Red Zone / 8-12 km Yellow Zone lateral band from
an active airport perimeter (the 2021 amendment cited as reducing the
yellow band from 45 km to 12 km), and the Indian Navy's own published 3 km
no-fly perimeter around its Mumbai installations (explicitly including
Naval Dockyard and INS Hamla by name in Navy public notices). Where DGCA
hasn't published an exact figure for a site category — military
cantonments, DRDO/strategic facilities — a conservative, clearly-labeled
estimate is used instead.

Honesty note: this is NOT a scrape of DGCA's live Digital Sky platform,
which isn't publicly queryable by automated means, and these radii are
rule-grounded rather than shapefile-precise. Before any real flight, an
operator must still verify against the actual Digital Sky NPNT platform
per DGCA Rule 19 — this module exists to give AeroFleet's simulation and
CBF gate a realistic, non-fabricated baseline, not to replace that legal
check.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class SiteCategory(Enum):
    AIRPORT = "AIRPORT"      # civil/international/domestic — Red disc + Yellow lateral ring
    MILITARY = "MILITARY"    # cantonment / defense installation — Red disc only
    STRATEGIC = "STRATEGIC"  # nuclear / other strategic site — Red disc only


@dataclass(frozen=True)
class RestrictedSite:
    name: str
    category: SiteCategory
    lat: float
    lon: float
    red_radius_m: float
    yellow_radius_m: Optional[float] = None  # only meaningful for AIRPORT
    source_note: str = ""


@dataclass(frozen=True)
class NamedSafeZone:
    """A real, well-known public open ground — a plausible emergency-
    landing candidate, not a DGCA/local-authority-approved landing site
    list. A real deployment needs airport/local-authority sign-off before
    any of these are used operationally."""
    name: str
    lat: float
    lon: float


# DGCA Drone Rules 2021: Red zone = 5 km from an active airport perimeter;
# Yellow zone = 8-12 km lateral band (modeled here as a 12 km outer ring —
# consistent with the widely-cited 2021 amendment reducing it from 45 km).
AIRPORT_RED_RADIUS_M = 5000.0
AIRPORT_YELLOW_RADIUS_M = 12000.0

# A smaller domestic/civil aerodrome (not an international hub) — DGCA's
# rule text also cites a "3-5 km of active airport boundaries" range for
# the Red Zone generally; the lower end fits a smaller aerodrome better
# than the 5 km figure reserved for major airports above.
AERODROME_RED_RADIUS_M = 3000.0
AERODROME_YELLOW_RADIUS_M = 8000.0

# Indian Navy's own published no-fly perimeter for its installations.
NAVY_RED_RADIUS_M = 3000.0

# Conservative, documented-as-approximate radius for non-aviation strategic
# / military sites where DGCA hasn't published an explicit figure.
STRATEGIC_RED_RADIUS_M = 3000.0
CANTONMENT_RED_RADIUS_M = 2000.0


PUNE_RESTRICTED_SITES: List[RestrictedSite] = [
    RestrictedSite(
        name="Pune Airport (Lohegaon) / Air Force Station Pune",
        category=SiteCategory.AIRPORT,
        lat=18.5822, lon=73.9197,
        red_radius_m=AIRPORT_RED_RADIUS_M,
        yellow_radius_m=AIRPORT_YELLOW_RADIUS_M,
        source_note="Joint civil airport and Indian Air Force Station — DGCA airport-proximity rule.",
    ),
    RestrictedSite(
        name="Pune Cantonment (Southern Command HQ)",
        category=SiteCategory.MILITARY,
        lat=18.5089, lon=73.8830,
        red_radius_m=CANTONMENT_RED_RADIUS_M,
        source_note="Military cantonment, houses Indian Army Southern Command HQ — DGCA Red Zone "
                     "by rule; radius is a conservative estimate of the cantonment's built extent, "
                     "not a DGCA-surveyed boundary.",
    ),
]

MUMBAI_RESTRICTED_SITES: List[RestrictedSite] = [
    RestrictedSite(
        name="Chhatrapati Shivaji Maharaj International Airport",
        category=SiteCategory.AIRPORT,
        lat=19.0896, lon=72.8656,
        red_radius_m=AIRPORT_RED_RADIUS_M,
        yellow_radius_m=AIRPORT_YELLOW_RADIUS_M,
        source_note="International airport — DGCA airport-proximity rule.",
    ),
    RestrictedSite(
        name="Juhu Aerodrome",
        category=SiteCategory.AIRPORT,
        lat=19.0968, lon=72.8347,
        red_radius_m=AERODROME_RED_RADIUS_M,
        yellow_radius_m=AERODROME_YELLOW_RADIUS_M,
        source_note="Domestic civil aerodrome, also used by the Coast Guard — smaller lateral "
                     "bands than an international airport's 5 km/12 km figures.",
    ),
    RestrictedSite(
        name="Naval Dockyard Mumbai (Western Naval Command HQ)",
        category=SiteCategory.MILITARY,
        lat=18.9220, lon=72.8347,
        red_radius_m=NAVY_RED_RADIUS_M,
        source_note="Indian Navy's published 3 km no-fly perimeter around its Mumbai installations.",
    ),
    RestrictedSite(
        name="INS Hamla (Malad)",
        category=SiteCategory.MILITARY,
        lat=19.1875, lon=72.8400,
        red_radius_m=NAVY_RED_RADIUS_M,
        source_note="Explicitly named in the Indian Navy's 3 km Mumbai no-fly-zone public notice.",
    ),
    RestrictedSite(
        name="Bhabha Atomic Research Centre (BARC), Trombay",
        category=SiteCategory.STRATEGIC,
        lat=19.0176, lon=72.9280,
        red_radius_m=STRATEGIC_RED_RADIUS_M,
        source_note="Nuclear/strategic installation — DGCA Red Zone by rule; radius is a "
                     "conservative estimate, not a DGCA-surveyed boundary.",
    ),
]


PUNE_SAFE_ZONES: List[NamedSafeZone] = [
    NamedSafeZone("Saras Baug (open garden)", 18.5018, 73.8508),
    NamedSafeZone("Sambhaji Park (Deccan Gymkhana)", 18.5162, 73.8407),
    NamedSafeZone("Pune Race Course open ground", 18.5535, 73.8895),
]

MUMBAI_SAFE_ZONES: List[NamedSafeZone] = [
    NamedSafeZone("Shivaji Park, Dadar", 19.0283, 72.8400),
    NamedSafeZone("Azad Maidan, Fort", 18.9430, 72.8320),
    NamedSafeZone("Cross Maidan, Churchgate", 18.9350, 72.8280),
]
