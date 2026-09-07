import copy
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from mech_design.comparison import compare, replay
from mech_design.comparison_input import load_study, study_from_snapshot

ROOT = Path(__file__).resolve().parents[1]
STUDY_PATH = ROOT / "cases/heated_cantilever_comparison.toml"


@pytest.fixture
def study():
    return load_study(STUDY_PATH)


def invoke(tmp_path, *args):
    return subprocess.run(
        [sys.executable, "-m", "mech_design", "compare", *map(str, args)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )


def test_four_designs_match_lesson_and_preserve_unknowns(study):
    report = compare(study)
    assert report["status"] == "ok"
    assert report["eligible_mass_order"] == ["A", "C"]
    assert report["lightest_candidate_ids"] == ["A"]
    rows = {row["id"]: row for row in report["results"]}
    assert rows["B"]["exclusion_reasons"] == ["tip_deflection", "first_frequency"]
    assert rows["D"]["exclusion_reasons"] == ["length_min"]
    expected = {
        "A": (0.02430, 0.000070546737, 246.7565296),
        "B": (0.01620, 0.000238095238, 164.5043530),
        "C": (0.03645, 0.000047031158, 246.7565296),
        "D": (0.01134, 0.000081666667, 335.7231695),
    }
    for name, (mass, deflection, frequency) in expected.items():
        result = rows[name]["evaluation"]
        metrics = {item["metric"]: item for item in result["evaluations"]}
        assert result["mass_kg"] == pytest.approx(mass)
        assert metrics["tip_deflection"]["value"] == pytest.approx(deflection)
        assert metrics["first_frequency"]["value"] == pytest.approx(frequency)
        assert sum(r["status"] == "not_evaluated" for r in result["evaluations"]) == 9
        assert result["overall_status"] == ("fail" if name == "B" else "incomplete")
        assert result["input"] == rows[name]["input"]
    width = next(r for r in rows["C"]["requirements"] if r["metric"] == "width")
    assert width["status"] == "pass" and width["margin"] == 0


@pytest.mark.parametrize("field", ["tip_force_n", "young_modulus_pa", "heat_w", "limits"])
def test_per_design_common_condition_overrides_are_rejected(study, field):
    snapshot = study.snapshot()
    snapshot["designs"][1][field] = 0.5
    with pytest.raises(ValueError, match="only geometry may vary"):
        study_from_snapshot(snapshot)


@pytest.mark.parametrize("value", [True, 0, -1, float("nan"), float("inf"), "0.03"])
def test_bad_geometry_is_input_error(study, value):
    snapshot = study.snapshot()
    snapshot["designs"][0]["width_m"] = value
    with pytest.raises(ValueError, match="finite positive"):
        study_from_snapshot(snapshot)


@pytest.mark.parametrize("mutation", ["empty", "duplicate", "wrong_units", "wrong_version"])
def test_ambiguous_studies_are_rejected(study, mutation):
    snapshot = study.snapshot()
    if mutation == "empty":
        snapshot["designs"] = []
    elif mutation == "duplicate":
        snapshot["designs"][1]["id"] = "A"
    elif mutation == "wrong_units":
        snapshot["requirements"]["required_length_mm"] = snapshot["requirements"].pop(
            "required_length_m"
        )
    else:
        snapshot["schema_version"] = True
    with pytest.raises(ValueError):
        study_from_snapshot(snapshot)


def test_optional_mass_limit_and_no_candidate(study):
    capped = replace(study, requirements=replace(study.requirements, max_mass_kg=0.025))
    report = compare(capped)
    assert report["eligible_mass_order"] == ["A"]
    assert report["results"][2]["exclusion_reasons"] == ["mass"]
    capped = replace(study, requirements=replace(study.requirements, max_mass_kg=0.001))
    report = compare(capped)
    assert report["status"] == "no_candidate"
    assert report["eligible_mass_order"] == report["lightest_candidate_ids"] == []


def test_mass_ties_are_retained_without_selecting_one(study):
    duplicate_geometry = replace(study.designs[0], id="E")
    report = compare(replace(study, designs=(*study.designs, duplicate_geometry)))
    assert report["lightest_candidate_ids"] == ["A", "E"]


@pytest.mark.parametrize("thickness", [0.03, 0.0001])
def test_out_of_model_design_keeps_other_rows_but_prevents_best_claim(study, thickness):
    bad = replace(study.designs[1], thickness_m=thickness)
    report = compare(replace(study, designs=(study.designs[0], bad)))
    assert report["status"] == "error"
    assert report["results"][0]["candidate_status"] == "eligible"
    assert report["results"][1]["candidate_status"] == "error"
    assert report["results"][1]["evaluation"] is None
    assert report["results"][1]["error"]
    assert report["lightest_candidate_ids"] == []
    json.dumps(report, allow_nan=False)


def test_missing_physical_evaluation_never_becomes_candidate(study, monkeypatch):
    import mech_design.comparison as module

    real = module.evaluate

    def missing(case):
        report = real(case)
        report["evaluations"] = [
            item for item in report["evaluations"] if item["metric"] != "first_frequency"
        ]
        return report

    monkeypatch.setattr(module, "evaluate", missing)
    report = compare(study)
    assert report["status"] == "error"
    assert report["eligible_mass_order"] == []


def test_replay_recomputes_from_snapshot_after_original_files_removed(tmp_path):
    base_path = tmp_path / "heated_cantilever.toml"
    study_path = tmp_path / "study.toml"
    base_path.write_bytes((ROOT / "cases/heated_cantilever.toml").read_bytes())
    study_path.write_bytes(STUDY_PATH.read_bytes())
    original = compare(load_study(study_path))
    base_path.unlink()
    study_path.unlink()
    cached = copy.deepcopy(original)
    cached["results"][0]["evaluation"]["mass_kg"] = 999
    assert replay(json.loads(json.dumps(cached))) == original


def test_replay_rejects_changed_input_and_engine(study):
    report = compare(study)
    modified = copy.deepcopy(report)
    modified["input"]["common_case"]["beam"]["tip_force_n"] = 0.5
    with pytest.raises(ValueError, match="input digest"):
        replay(modified)
    report["provenance"]["code_sha256"] = "another-version"
    with pytest.raises(ValueError, match="code differs"):
        replay(report)


def test_cli_save_replay_and_strict_status_outside_repo(tmp_path):
    output = tmp_path / "outputs" / "comparison.json"
    result = invoke(tmp_path, STUDY_PATH, "--output", output, "--json")
    assert result.returncode == 0, result.stderr
    original = json.loads(result.stdout)
    assert json.loads(output.read_text(encoding="utf-8")) == original
    replayed = invoke(tmp_path, "--replay", output, "--json", "--require-complete")
    assert replayed.returncode == 3, replayed.stderr
    assert json.loads(replayed.stdout) == original
    text = invoke(tmp_path, STUDY_PATH)
    assert "D | excluded" in text.stdout
    assert "FAIL length_min" in text.stdout
    assert "Not evaluated: " in text.stdout
    assert "Lightest within study: A" in text.stdout


def test_cli_does_not_overwrite_output(tmp_path):
    output = tmp_path / "report.json"
    output.write_text("keep", encoding="utf-8")
    result = invoke(tmp_path, STUDY_PATH, "--output", output)
    assert result.returncode == 1
    assert output.read_text(encoding="utf-8") == "keep"
    assert "Traceback" not in result.stderr


def test_cli_invalid_condition_shows_actionable_difference(tmp_path):
    source = (
        STUDY_PATH.read_text(encoding="utf-8")
        .replace(
            'base_case = "heated_cantilever.toml"',
            'base_case = "' + (ROOT / "cases/heated_cantilever.toml").as_posix() + '"',
        )
        .replace('id = "B"', 'id = "B"\ntip_force_n = 0.5')
    )
    bad = tmp_path / "mixed.toml"
    bad.write_text(source, encoding="utf-8")
    result = invoke(tmp_path, bad, "--json")
    assert result.returncode == 1
    assert "tip_force_n" in result.stderr and "only geometry" in result.stderr
    assert "Traceback" not in result.stderr
    assert not result.stdout


def test_cli_no_candidate_and_error_exit_codes(tmp_path, study):
    # Save valid replay envelopes so both exit paths exercise the actual CLI.
    for expected, altered in [
        (2, replace(study, requirements=replace(study.requirements, max_mass_kg=0.001))),
        (1, replace(study, designs=(replace(study.designs[0], thickness_m=0.03),))),
    ]:
        saved = tmp_path / f"report-{expected}.json"
        saved.write_text(json.dumps(compare(altered)), encoding="utf-8")
        result = invoke(tmp_path, "--replay", saved, "--json", "--require-complete")
        assert result.returncode == expected, result.stderr
        assert json.loads(result.stdout)["lightest_candidate_ids"] == []
