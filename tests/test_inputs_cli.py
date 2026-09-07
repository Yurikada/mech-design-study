import json
import subprocess
import sys
from dataclasses import replace

import pytest

from mech_design.case import load_case


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), True, "0.003"])
def test_invalid_dimensions_rejected(case, value):
    with pytest.raises(ValueError, match="finite positive"):
        replace(case.beam, thickness_m=value)


def test_short_beam_outside_model_scope(case):
    with pytest.raises(ValueError, match="length/thickness"):
        replace(case.beam, thickness_m=0.02)


@pytest.mark.parametrize(
    "before,after",
    [
        ("schema_version = 1", "schema_version = 2"),
        ("schema_version = 1", "schema_version = true"),
        ("length_m = 0.10", "length_mm = 100"),
        ("heat_w = 1.0", "heat_w = nan"),
    ],
)
def test_malformed_schema_and_units_rejected(case_path, tmp_path, before, after):
    bad = tmp_path / "bad.toml"
    bad.write_text(case_path.read_text(encoding="utf-8").replace(before, after), encoding="utf-8")
    with pytest.raises(ValueError):
        load_case(bad)


def invoke(case_path, tmp_path, *args):
    return subprocess.run(
        [sys.executable, "-m", "mech_design", str(case_path), *args],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )


def test_installed_cli_runs_outside_repository(case_path, tmp_path):
    result = invoke(case_path, tmp_path, "--json")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["overall_status"] == "incomplete"
    assert report["input"]["beam"]["length_m"] == 0.1


def test_strict_completeness_exit_code(case_path, tmp_path):
    assert invoke(case_path, tmp_path, "--require-complete").returncode == 3


def test_failed_constraint_exit_code(case_path, tmp_path):
    thin = tmp_path / "thin.toml"
    thin.write_text(
        case_path.read_text(encoding="utf-8").replace("thickness_m = 0.003", "thickness_m = 0.002"),
        encoding="utf-8",
    )
    result = invoke(thin, tmp_path, "--json")
    assert result.returncode == 2
    assert json.loads(result.stdout)["overall_status"] == "fail"


def test_missing_input_is_actionable_error(tmp_path):
    result = invoke(tmp_path / "missing.toml", tmp_path)
    assert result.returncode == 1
    assert "Case evaluation error" in result.stderr
    assert "Traceback" not in result.stderr
