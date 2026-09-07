from dataclasses import replace

import pytest

from mech_design.evaluation import DISCIPLINES, Status, check, evaluate, overall_status


def test_unevaluated_disciplines_prevent_overall_pass(case):
    report = evaluate(case)
    assert report["overall_status"] == "incomplete"
    assert {item["discipline"] for item in report["evaluations"]} == set(DISCIPLINES)
    assert sum(item["status"] == "not_evaluated" for item in report["evaluations"]) == 9
    assert sum(item["status"] == "pass" for item in report["evaluations"]) == 4


def test_thinning_exposes_displacement_and_frequency_violations(case):
    report = evaluate(replace(case, beam=replace(case.beam, thickness_m=0.002)))
    failed = {item["metric"] for item in report["evaluations"] if item["status"] == "fail"}
    assert report["overall_status"] == "fail"
    assert failed == {"tip_deflection", "first_frequency"}


@pytest.mark.parametrize(
    "relation,value,status,margin",
    [
        ("<=", 10.0, Status.PASS, 0.0),
        ("<=", 11.0, Status.FAIL, -1.0),
        (">=", 9.0, Status.FAIL, -1.0),
        (">=", 11.0, Status.PASS, 1.0),
    ],
)
def test_constraint_direction_and_boundary(relation, value, status, margin):
    result = check("stress", "test", value, "Pa", 10, relation, "test", "test")
    assert result.status == status
    assert result.margin == margin


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_solver_output_is_error(value):
    result = check("stress", "test", value, "Pa", 10, "<=", "test", "test")
    assert result.status == Status.ERROR
    assert overall_status([result]) == "error"


def test_empty_report_cannot_pass():
    assert overall_status([]) == "incomplete"


def test_large_deflection_rejected(case):
    with pytest.raises(ValueError, match="small-deflection"):
        evaluate(replace(case, beam=replace(case.beam, tip_force_n=100)))
