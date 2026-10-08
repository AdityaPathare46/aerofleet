"""Parameter-file parsing (aerofleet/assurance/params.py)."""
import pytest

from aerofleet.assurance.params import ParamFileError, parse_param_bytes, parse_param_text

pytestmark = pytest.mark.unit


def test_mission_planner_format_with_comments_and_blank_lines():
    f = parse_param_text("#NOTE: saved from Mission Planner\n\nFS_THR_ENABLE,1\nRTL_ALT,1500\nANGLE_MAX,3000.5\n")
    assert f.format == "mission_planner"
    assert f.params == {"FS_THR_ENABLE": 1.0, "RTL_ALT": 1500.0, "ANGLE_MAX": 3000.5}
    assert f.rejected == [] and f.duplicates == []


def test_mavproxy_format():
    f = parse_param_text("FS_THR_ENABLE 1\nRTL_ALT      1500.000000\n")
    assert f.format == "mavproxy" and f.params["RTL_ALT"] == 1500.0


def test_qgroundcontrol_format():
    text = "# Onboard parameters for Vehicle 1\n# Vehicle-Id Component-Id Name Value Type\n1\t1\tCOM_LOW_BAT_ACT\t3\t6\n1\t1\tRTL_RETURN_ALT\t60.0\t9\n"
    f = parse_param_text(text)
    assert f.format == "qgc" and f.params == {"COM_LOW_BAT_ACT": 3.0, "RTL_RETURN_ALT": 60.0}


def test_bad_lines_are_reported_not_dropped_silently():
    f = parse_param_text("FS_THR_ENABLE,1\nthis is not a parameter line at all\nRTL_ALT,abc\nBATT_CAPACITY,5200\n")
    assert set(f.params) == {"FS_THR_ENABLE", "BATT_CAPACITY"}
    assert [n for n, _ in f.rejected] == [2, 3]
    assert "not a number" in f.rejected[1][1]


def test_duplicate_names_are_flagged_and_last_value_wins():
    f = parse_param_text("RTL_ALT,1500\nRTL_ALT,3000\n")
    assert f.params["RTL_ALT"] == 3000.0 and f.duplicates == ["RTL_ALT"]


def test_non_finite_values_are_rejected():
    f = parse_param_text("RTL_ALT,nan\nANGLE_MAX,inf\nFS_THR_ENABLE,1\n")
    assert set(f.params) == {"FS_THR_ENABLE"} and len(f.rejected) == 2


def test_empty_or_useless_file_is_an_error():
    with pytest.raises(ParamFileError, match="No parameters found"):
        parse_param_text("# only a comment\n\n")


def test_binary_and_oversized_uploads_are_refused():
    with pytest.raises(ParamFileError, match="binary"):
        parse_param_bytes(b"\xa3\x95\x80\x00\x00binarylog")
    with pytest.raises(ParamFileError, match="2 MB"):
        parse_param_bytes(b"A,1\n" * 600_000)
