"""Unit tests for aerofleet/city/restricted_sites.py and the real,
site-based airspace built from it (aerofleet/city/airspace.py's
build_airspace_from_sites()) — the actual DGCA-relevant Red/Yellow zones
and altitude ceilings for Pune and Mumbai, not the old single generic
airport circle.
"""
import pytest

from aerofleet.city.airspace import ZoneColor, build_airspace_from_sites
from aerofleet.city.restricted_sites import (
    MUMBAI_RESTRICTED_SITES,
    MUMBAI_SAFE_ZONES,
    PUNE_RESTRICTED_SITES,
    PUNE_SAFE_ZONES,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def pune_airspace():
    return build_airspace_from_sites(PUNE_RESTRICTED_SITES, PUNE_SAFE_ZONES)


@pytest.fixture
def mumbai_airspace():
    return build_airspace_from_sites(MUMBAI_RESTRICTED_SITES, MUMBAI_SAFE_ZONES)


class TestPuneZones:
    def test_pune_airport_is_red(self, pune_airspace):
        assert pune_airspace.zone_at(18.5822, 73.9197) == ZoneColor.RED

    def test_8km_from_pune_airport_is_yellow(self, pune_airspace):
        # Due north of the airport, far from the cantonment, to isolate
        # which site is actually driving the classification.
        assert pune_airspace.zone_at(18.6542, 73.9197) == ZoneColor.YELLOW

    def test_far_from_any_site_is_green(self, pune_airspace):
        assert pune_airspace.zone_at(18.40, 73.75) == ZoneColor.GREEN

    def test_pune_cantonment_is_red(self, pune_airspace):
        assert pune_airspace.zone_at(18.5089, 73.8830) == ZoneColor.RED

    def test_pune_has_named_safe_zones(self, pune_airspace):
        names = [s.name for s in pune_airspace.safe_zones]
        assert "Saras Baug (open garden)" in names


class TestMumbaiZones:
    def test_csmia_is_red(self, mumbai_airspace):
        assert mumbai_airspace.zone_at(19.0896, 72.8656) == ZoneColor.RED

    def test_juhu_aerodrome_is_red(self, mumbai_airspace):
        assert mumbai_airspace.zone_at(19.0968, 72.8347) == ZoneColor.RED

    def test_naval_dockyard_is_red(self, mumbai_airspace):
        assert mumbai_airspace.zone_at(18.9220, 72.8347) == ZoneColor.RED

    def test_ins_hamla_is_red(self, mumbai_airspace):
        assert mumbai_airspace.zone_at(19.1875, 72.8400) == ZoneColor.RED

    def test_barc_trombay_is_red(self, mumbai_airspace):
        assert mumbai_airspace.zone_at(19.0176, 72.9280) == ZoneColor.RED

    def test_naval_dockyard_has_no_yellow_ring(self, mumbai_airspace):
        # MILITARY/STRATEGIC sites are Red-disc-only per DGCA's rule text —
        # unlike an AIRPORT site, there's no ATC-permission lateral band.
        # A point just outside the 3 km Navy radius should already be GREEN.
        just_outside_navy_radius = (18.9220 + 0.035, 72.8347)  # ~3.9 km north
        assert mumbai_airspace.zone_at(*just_outside_navy_radius) == ZoneColor.GREEN


class TestAltitudeCeiling:
    def test_ceiling_is_operational_default_far_from_any_site(self, pune_airspace):
        assert pune_airspace.altitude_ceiling_m_at(18.40, 73.75) == 100.0

    def test_ceiling_drops_to_60m_in_yellow_band(self, pune_airspace):
        assert pune_airspace.altitude_ceiling_m_at(18.6542, 73.9197) == 60.0

    def test_medical_priority_demoted_to_fit_reduced_ceiling(self, pune_airspace):
        band = pune_airspace.assign_altitude_band("MEDICAL", 18.6542, 73.9197)
        assert band.ceiling_m <= 60.0

    def test_medical_priority_gets_high_band_away_from_any_site(self, pune_airspace):
        band = pune_airspace.assign_altitude_band("MEDICAL", 18.40, 73.75)
        assert band.name == "HIGH"

    def test_no_coordinates_preserves_legacy_behavior(self, pune_airspace):
        band = pune_airspace.assign_altitude_band("MEDICAL")
        assert band.name == "HIGH"
