"""Pre-flight route check (aerofleet/assurance/airspace_check.py), with a made-up zone map."""
from aerofleet.assurance.airspace_check import CLEAR, NEEDS_PERMISSION, NOT_PERMITTED, UNCHECKED, check_route, explain


def zones(lat, lon):
    """A red disc around (18.50, 73.88) of about 1 km and a yellow band north of 18.53."""
    if (lat - 18.50) ** 2 + (lon - 73.88) ** 2 < 0.009 ** 2:
        return {"id": "R1", "color": "RED", "name": "Test cantonment"}
    if lat > 18.53:
        return {"id": "Y1", "color": "YELLOW", "name": "Test airport"}
    return None


def test_green_and_low_is_clear():
    r = check_route("OK", [(18.45, 73.80, 0), (18.45, 73.81, 60), (18.45, 73.80, 0)], zones)
    assert r["verdict"] == CLEAR and r["findings"] == [] and explain(r) == "Stays in green airspace and under 120 m."
    assert 2000 < r["length_m"] < 2200 and r["max_height_m"] == 60


def test_a_route_into_a_red_zone_is_not_permitted_and_says_where():
    r = check_route("RED", [(18.50, 73.86, 0), (18.50, 73.90, 60)], zones)
    f = r["findings"][0]
    assert r["verdict"] == NOT_PERMITTED and f["color"] == "RED" and f["zone"] == "Test cantonment"
    assert 1000 < f["at_m"] < 1300 and f["until_m"] > f["at_m"]                 # enters about 1.2 km in, and leaves again
    assert "red zone" in explain(r) and "1.2 km into the route" in explain(r)


def test_yellow_needs_permission_and_red_wins_over_yellow():
    assert check_route("Y", [(18.52, 73.80, 0), (18.54, 73.80, 50)], zones)["verdict"] == NEEDS_PERMISSION
    both = check_route("YR", [(18.54, 73.80, 0), (18.50, 73.88, 50)], zones)
    assert both["verdict"] == NOT_PERMITTED and {f["color"] for f in both["findings"]} == {"RED", "YELLOW"}


def test_above_120_m_is_not_permitted_even_in_green():
    r = check_route("HIGH", [(18.45, 73.80, 0), (18.45, 73.81, 150)], zones)
    assert r["verdict"] == NOT_PERMITTED and r["findings"][0]["kind"] == "ceiling" and r["findings"][0]["max_m"] == 150
    assert "above the 120 m limit" in explain(r)


def test_without_zone_data_a_route_is_unchecked_never_clear():
    r = check_route("FAR", [(28.6, 77.2, 0), (28.61, 77.2, 60)], None)
    assert r["verdict"] == UNCHECKED and "not checked" in explain(r) and "Digital Sky" in explain(r)
    assert check_route("FARHIGH", [(28.6, 77.2, 0), (28.61, 77.2, 200)], None)["verdict"] == NOT_PERMITTED   # height is known anywhere


def test_india_wide_airport_lookup_catches_red_yellow_and_never_claims_clear_outside_mapped_cities():
    from aerofleet.assurance.airspace_check import INDIA_AIRPORTS, india_airport_zone_at

    assert len(INDIA_AIRPORTS) >= 37
    # Inside Nagpur Airport 0-5 km RED zone
    nag_red = check_route("NAG-RED", [(21.092, 79.055, 10), (21.100, 79.060, 10)], india_airport_zone_at, airports_only=True)
    assert nag_red["verdict"] == NOT_PERMITTED and nag_red["findings"][0]["color"] == "RED" and "Nagpur" in nag_red["findings"][0]["zone"]
    # Inside Nashik Airport 5-8 km inner YELLOW band (~8.2 km from center -> ~6.7 km from perimeter): yellow at any height (4 m)
    isk_yel = check_route("ISK-YEL", [(20.045, 73.914, 4), (20.044, 73.914, 4)], india_airport_zone_at, airports_only=True)
    assert isk_yel["verdict"] == NEEDS_PERMISSION and isk_yel["findings"][0]["color"] == "YELLOW" and "Nashik" in isk_yel["findings"][0]["zone"]
    # H5: Inside Nashik Airport 8-12 km outer YELLOW band (~11.5 km from center -> ~10.0 km from perimeter):
    # 4 m agricultural spraying is GREEN (<= 60 m floor) -> UNCHECKED (not over-restricted); 80 m mapping -> NEEDS_PERMISSION!
    isk_outer_low = check_route("ISK-4M", [(20.016, 73.914, 4), (20.015, 73.914, 4)], india_airport_zone_at, airports_only=True)
    isk_outer_high = check_route("ISK-80M", [(20.016, 73.914, 80), (20.015, 73.914, 80)], india_airport_zone_at, airports_only=True)
    assert isk_outer_low["verdict"] == UNCHECKED
    assert isk_outer_high["verdict"] == NEEDS_PERMISSION and ">60 m" in isk_outer_high["findings"][0]["zone"]
    # Baramati farming-district aerodrome is covered
    bar_red = check_route("BAR-RED", [(18.218, 74.580, 10), (18.220, 74.582, 10)], india_airport_zone_at, airports_only=True)
    assert bar_red["verdict"] == NOT_PERMITTED and "Baramati" in bar_red["findings"][0]["zone"]
    # Rural Maharashtra far from any airport -> UNCHECKED (never CLEAR because military zones aren't mapped outside Pune/Mumbai)
    rural = check_route("RURAL", [(17.10, 74.90, 5), (17.105, 74.90, 5)], india_airport_zone_at, airports_only=True)
    assert rural["verdict"] == UNCHECKED and "Indian airport zones" in explain(rural) and "Digital Sky" in explain(rural)
