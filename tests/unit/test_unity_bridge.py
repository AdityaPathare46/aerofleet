"""Unit tests for aerofleet/validation/unity_bridge.py — the subprocess/
JSON wrapper logic, tested via a tiny stub script standing in for the real
`unity` CLI binary. Never needs an actual Unity Editor installed; that's
the whole point of testing the wrapper separately from RouteValidator.cs
(see unity/AeroFleetValidation/README.md for that side's own honest
not-yet-run status).
"""
import json
import os
import stat
import sys
from pathlib import Path

import pytest

from aerofleet.validation.unity_bridge import (
    DEFAULT_PROJECT_PATH,
    build_route_json,
    find_unity_cli,
    run_unity_validation,
)

pytestmark = pytest.mark.unit

_SAMPLE_RESULT = {
    "success": True,
    "waypoints": [
        {"index": 0, "reached": True, "deviation_m": 0.0},
        {"index": 1, "reached": True, "deviation_m": 1.2},
    ],
    "events": [],
    "error": None,
}


def _write_stub_unity_cli(path: Path, result_payload: dict, exit_code: int = 0, write_result: bool = True):
    """A stub standing in for `unity run <project> --timeout N -- -batchmode
    ... -output <path> ...` — parses just enough of the real argument shape
    (confirmed via `unity run --help`) to find `-output` and write a canned
    result there, so run_unity_validation()'s own logic is what's under
    test, not a real Unity install."""
    script = f"""#!/usr/bin/env python3
import sys, json
args = sys.argv[1:]
output_path = args[args.index("-output") + 1] if "-output" in args else None
if output_path and {write_result}:
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({result_payload!r}, f)
sys.exit({exit_code})
"""
    path.write_text(script, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


class TestBuildRouteJson:
    def test_builds_the_real_contract_shape(self):
        route = build_route_json(
            lat_lons=[(18.55, 73.90), (18.56, 73.91)],
            altitudes_m=[30.0, 30.0],
            wind_speeds_mps=[3.0, 3.0],
            drone_mass_kg=12.5,
        )
        assert route["drone_mass_kg"] == 12.5
        assert len(route["waypoints"]) == 2
        assert route["waypoints"][0] == {"lat": 18.55, "lon": 73.90, "altitude_m": 30.0, "wind_speed_mps": 3.0}

    def test_mismatched_list_lengths_raise(self):
        with pytest.raises(ValueError):
            build_route_json(
                lat_lons=[(18.55, 73.90)], altitudes_m=[30.0, 31.0], wind_speeds_mps=[3.0], drone_mass_kg=12.5,
            )

    def test_defaults_are_present(self):
        route = build_route_json(
            lat_lons=[(18.55, 73.90), (18.56, 73.91)], altitudes_m=[30.0, 30.0],
            wind_speeds_mps=[3.0, 3.0], drone_mass_kg=12.5,
        )
        assert route["max_thrust_n"] > 0
        assert route["drag_coefficient"] > 0


class TestFindUnityCli:
    def test_finds_binary_on_path(self, tmp_path, monkeypatch):
        fake_unity = tmp_path / "unity"
        fake_unity.write_text("#!/bin/sh\nexit 0\n")
        fake_unity.chmod(fake_unity.stat().st_mode | stat.S_IEXEC)
        monkeypatch.setenv("PATH", str(tmp_path))
        assert find_unity_cli() == str(fake_unity)

    def test_returns_none_when_not_found_anywhere(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PATH", str(tmp_path))  # empty dir, nothing on PATH
        monkeypatch.setattr(Path, "home", lambda: tmp_path)  # no ~/.unity/bin/unity either
        assert find_unity_cli() is None


class TestRunUnityValidation:
    def _route(self):
        return build_route_json(
            lat_lons=[(18.55, 73.90), (18.56, 73.91)], altitudes_m=[30.0, 30.0],
            wind_speeds_mps=[3.0, 3.0], drone_mass_kg=12.5,
        )

    def test_missing_cli_reports_invocation_error_not_a_crash(self, tmp_path, monkeypatch):
        monkeypatch.setattr("aerofleet.validation.unity_bridge.find_unity_cli", lambda: None)
        result = run_unity_validation(self._route(), work_dir=tmp_path / "work")
        assert result.success is False
        assert "not found" in result.invocation_error

    def test_missing_project_reports_invocation_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr("aerofleet.validation.unity_bridge.find_unity_cli", lambda: sys.executable)
        result = run_unity_validation(
            self._route(), work_dir=tmp_path / "work", project_path=tmp_path / "does_not_exist",
        )
        assert result.success is False
        assert "not found" in result.invocation_error

    def test_successful_run_parses_the_real_result_shape(self, tmp_path, monkeypatch):
        stub = tmp_path / "fake_unity.py"
        _write_stub_unity_cli(stub, _SAMPLE_RESULT)
        monkeypatch.setattr("aerofleet.validation.unity_bridge.find_unity_cli", lambda: sys.executable)
        # Swap the invocation to run our stub script instead of a real
        # "unity" binary — patch subprocess.run's first-arg construction
        # indirectly by pointing find_unity_cli at python and prefixing
        # the stub as the first real arg via project_path trick is messy;
        # instead monkeypatch subprocess.run directly to redirect argv[0].
        import subprocess as sp

        real_run = sp.run

        def fake_run(cmd, **kwargs):
            cmd = [sys.executable, str(stub)] + cmd[2:]  # drop "unity run", keep our own flags
            return real_run(cmd, **kwargs)

        monkeypatch.setattr("aerofleet.validation.unity_bridge.subprocess.run", fake_run)
        (tmp_path / "project").mkdir()
        result = run_unity_validation(
            self._route(), work_dir=tmp_path / "work", project_path=tmp_path / "project",
        )
        assert result.success is True
        assert len(result.waypoints) == 2
        assert result.waypoints[1].deviation_m == 1.2
        assert result.invocation_error is None

    def test_no_output_file_written_is_a_real_invocation_error(self, tmp_path, monkeypatch):
        stub = tmp_path / "fake_unity.py"
        _write_stub_unity_cli(stub, _SAMPLE_RESULT, write_result=False)
        monkeypatch.setattr("aerofleet.validation.unity_bridge.find_unity_cli", lambda: sys.executable)
        import subprocess as sp

        real_run = sp.run

        def fake_run(cmd, **kwargs):
            cmd = [sys.executable, str(stub)] + cmd[2:]
            return real_run(cmd, **kwargs)

        monkeypatch.setattr("aerofleet.validation.unity_bridge.subprocess.run", fake_run)
        (tmp_path / "project").mkdir()
        result = run_unity_validation(
            self._route(), work_dir=tmp_path / "work", project_path=tmp_path / "project",
        )
        assert result.success is False
        assert "without writing" in result.invocation_error
