"""Common constraint records: unevaluated disciplines never become a product pass."""

import math
from dataclasses import asdict, dataclass
from enum import StrEnum

from mech_design.case import Case
from mech_design.models import cantilever, tip_temperature


class Status(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NOT_EVALUATED = "not_evaluated"
    NOT_APPLICABLE = "not_applicable"
    ERROR = "error"


DISCIPLINES = (
    "topology_optimization",
    "stress",
    "fatigue",
    "environmental_degradation",
    "creep_relaxation",
    "emc",
    "manufacturability",
    "assembly",
    "maintenance",
    "circuit",
    "thermal",
    "vibration",
)


@dataclass(frozen=True)
class Evaluation:
    discipline: str
    metric: str
    status: Status
    value: float | None
    unit: str
    limit: float | None
    relation: str
    margin: float | None
    method: str
    note: str


def check(
    discipline: str,
    metric: str,
    value: float,
    unit: str,
    limit: float,
    relation: str,
    method: str,
    note: str,
) -> Evaluation:
    if relation not in ("<=", ">="):
        raise ValueError("Unsupported constraint relation")
    if not math.isfinite(value) or not math.isfinite(limit):
        return Evaluation(
            discipline,
            metric,
            Status.ERROR,
            None,
            unit,
            None,
            relation,
            None,
            method,
            "Nonfinite model output or limit",
        )
    margin = limit - value if relation == "<=" else value - limit
    return Evaluation(
        discipline,
        metric,
        Status.PASS if margin >= 0 else Status.FAIL,
        value,
        unit,
        limit,
        relation,
        margin,
        method,
        note,
    )


def overall_status(evaluations: list[Evaluation]) -> str:
    if any(item.status == Status.ERROR for item in evaluations):
        return "error"
    if any(item.status == Status.FAIL for item in evaluations):
        return "fail"
    covered = {item.discipline for item in evaluations}
    if covered != set(DISCIPLINES) or any(
        item.status == Status.NOT_EVALUATED for item in evaluations
    ):
        return "incomplete"
    return "pass"


def evaluate(case: Case) -> dict:
    values = cantilever(case.beam)
    if values["tip_deflection_m"] / case.beam.length_m > 0.05:
        raise ValueError("Deflection/length exceeds educational small-deflection limit 0.05")
    checks = [
        check(
            "stress",
            "root_stress",
            values["root_stress_pa"],
            "Pa",
            case.limits.max_stress_pa,
            "<=",
            "euler_bernoulli_v1",
            "Nominal elastic bending stress; no fillet/contact stress concentration",
        ),
        check(
            "stress",
            "tip_deflection",
            values["tip_deflection_m"],
            "m",
            case.limits.max_tip_deflection_m,
            "<=",
            "euler_bernoulli_v1",
            "Small deflection, fixed root, transverse end force",
        ),
        check(
            "vibration",
            "first_frequency",
            values["first_frequency_hz"],
            "Hz",
            case.limits.min_first_frequency_hz,
            ">=",
            "uniform_cantilever_v1",
            "Unloaded uniform beam; no attached mass, damping, or forced response",
        ),
        check(
            "thermal",
            "tip_temperature",
            tip_temperature(case.beam, case.thermal),
            "K",
            case.limits.max_tip_temperature_k,
            "<=",
            "steady_conduction_1d_v1",
            "Fixed root temperature; insulated sides; constant conductivity; no convection",
        ),
    ]
    for discipline in DISCIPLINES:
        if discipline not in {item.discipline for item in checks}:
            checks.append(
                Evaluation(
                    discipline,
                    "not_implemented",
                    Status.NOT_EVALUATED,
                    None,
                    "",
                    None,
                    "",
                    None,
                    "none",
                    "Model, inputs and validation are not implemented",
                )
            )
    return {
        "schema_version": 1,
        "case": case.name,
        "overall_status": overall_status(checks),
        "scope": "Educational analytical models; not a validated product design",
        "input": asdict(case),
        "model_version": "analytical_baseline_v1",
        "mass_kg": values["mass_kg"],
        "evaluations": [asdict(item) for item in checks],
    }
