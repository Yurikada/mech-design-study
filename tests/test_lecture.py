"""Published teaching data must stay tied to the executable model and case definitions."""

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict
from pathlib import Path

import pytest

from mech_design.case import load_case
from mech_design.evaluation import evaluate

ROOT = Path(__file__).resolve().parents[1]


def load_data():
    text = (ROOT / "docs/learning/assets/lecture-data.js").read_text(encoding="utf-8")
    return json.loads(text.split("window.MECH_LECTURE_DATA = ", 1)[1].removesuffix(";\n"))


def test_lecture_comparison_only_changes_thickness(case):
    thin = load_case(ROOT / "cases/heated_cantilever_2mm.toml")
    original = asdict(case.beam)
    original["thickness_m"] = 0.002
    assert asdict(thin.beam) == original
    assert thin.thermal == case.thermal
    assert thin.limits == case.limits
    data = load_data()["scenarios"]["30:2"]
    report = evaluate(thin)
    for item in report["evaluations"]:
        if item["value"] is not None:
            assert data["metrics"][item["metric"]]["value"] == item["value"]
            assert data["metrics"][item["metric"]]["status"] == item["status"]


def test_lecture_data_reproducible_from_sources():
    result = subprocess.run(
        [sys.executable, "scripts/build_lecture_data.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_all_visual_ratios_fit_fixed_zero_to_eight_scale():
    data = load_data()
    assert len(data["scenarios"]) == 36
    base = data["scenarios"]["30:3"]
    root_temperature = data["baseline_input"]["thermal"]["base_temperature_k"]
    for scenario in data["scenarios"].values():
        assert scenario["unevaluated_count"] == 9
        assert scenario["overall_status"] in ("incomplete", "fail")
        assert 0 < scenario["mass_kg"] / base["mass_kg"] <= 8
        for key, metric in scenario["metrics"].items():
            offset = root_temperature if key == "tip_temperature" else 0
            assert 0 < ((metric["value"] - offset) / (base["metrics"][key]["value"] - offset)) <= 8


@pytest.mark.parametrize(
    "name", ["cantilever", "heat-path", "evaluation-flow", "verification-validation"]
)
def test_authored_diagrams_have_accessible_labels(name):
    root = ET.parse(ROOT / f"docs/learning/assets/{name}.svg").getroot()
    ns = {"svg": "http://www.w3.org/2000/svg"}
    assert root.find("svg:title", ns).text
    assert root.find("svg:desc", ns).text
    assert root.attrib["viewBox"].startswith("0 0 ")
