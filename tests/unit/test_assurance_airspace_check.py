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
