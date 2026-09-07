"""Compare within explicit requirements while retaining full evaluation uncertainty."""

import hashlib
import json
import math
from dataclasses import asdict, replace
from pathlib import Path

from mech_design import __version__
from mech_design.comparison_input import Study, study_from_snapshot
from mech_design.evaluation import Status, check, evaluate

COMPARISON_VERSION = "case_comparison_v1"
PHYSICAL_METRICS = {"root_stress", "tip_deflection", "first_frequency", "tip_temperature"}
BOUNDARIES = {
    "structural": "Uniform small-deflection Euler-Bernoulli beam; perfectly fixed root",
    "static_load": "Transverse force at the free end; no self-weight or thermal stress",
    "vibration": "Unloaded uniform beam; no attached mass, damping or forced response",
    "thermal": "Steady 1D conduction; fixed root temperature; tip heat; insulated sides",
}


def input_digest(snapshot: dict) -> str:
    data = json.dumps(snapshot, sort_keys=True, ensure_ascii=True, allow_nan=False).encode()
    return hashlib.sha256(data).hexdigest()


def code_digest() -> str:
    root = Path(__file__).parent
    names = ("case.py", "models.py", "evaluation.py", "comparison_input.py", "comparison.py")
    # Normalize line endings for replay between Windows and Linux checkouts.
    source = "\n".join(name + "\n" + (root / name).read_text(encoding="utf-8") for name in names)
    return hashlib.sha256(source.encode()).hexdigest()


def compare(study: Study) -> dict:
    # Validate public API inputs as strictly as TOML and replay inputs.
    study = study_from_snapshot(study.snapshot())
    rows = []
    for design in study.designs:
        geometry = asdict(design)
        geometry.pop("id")
        snapshot = asdict(study.common_case)
        snapshot["name"] = design.id
        snapshot["beam"].update(geometry)
        row = {"id": design.id, "input": snapshot, "evaluation": None, "requirements": []}
        try:
            case = replace(
                study.common_case,
                name=design.id,
                beam=replace(study.common_case.beam, **geometry),
            )
            report = evaluate(case)
            mass = report["mass_kg"]
            if not math.isfinite(mass) or mass <= 0:
                raise ValueError("Model returned invalid mass")
            physical = [r for r in report["evaluations"] if r["metric"] in PHYSICAL_METRICS]
            if {r["metric"] for r in physical} != PHYSICAL_METRICS or len(physical) != 4:
                raise ValueError("Required physical evaluations are missing or duplicated")
            if any(r["status"] not in (Status.PASS, Status.FAIL) for r in physical):
                raise ValueError("Required physical evaluations are unavailable")
            if report["overall_status"] == "error":
                raise ValueError("Physical evaluation failed")
            row["evaluation"] = report
            req = study.requirements
            specs = [
                ("length_min", design.length_m, req.required_length_m, ">=", "m"),
                ("length_max", design.length_m, req.required_length_m, "<=", "m"),
                ("width", design.width_m, req.max_width_m, "<=", "m"),
                ("thickness", design.thickness_m, req.max_thickness_m, "<=", "m"),
            ]
            if req.max_mass_kg is not None:
                specs.append(("mass", mass, req.max_mass_kg, "<=", "kg"))
            checks = [
                asdict(
                    check(
                        "study_requirements",
                        metric,
                        value,
                        unit,
                        limit,
                        relation,
                        COMPARISON_VERSION,
                        f"Teaching requirement {study.requirements_version}; "
                        "no tolerance allowance",
                    )
                )
                for metric, value, limit, relation, unit in specs
            ]
            row["requirements"] = checks
            violations = [
                r["metric"] for r in [*report["evaluations"], *checks] if r["status"] == Status.FAIL
            ]
            row.update(
                candidate_status="excluded" if violations else "eligible",
                exclusion_reasons=violations,
                error=None,
            )
        except (ValueError, ArithmeticError) as exc:
            row.update(candidate_status="error", exclusion_reasons=[], error=str(exc))
        rows.append(row)

    candidates = [row for row in rows if row["candidate_status"] == "eligible"]
    candidates.sort(key=lambda row: (row["evaluation"]["mass_kg"], row["id"]))
    has_error = any(row["candidate_status"] == "error" for row in rows)
    lightest = []
    if candidates and not has_error:
        minimum = candidates[0]["evaluation"]["mass_kg"]
        lightest = [row["id"] for row in candidates if row["evaluation"]["mass_kg"] == minimum]
    snapshot = study.snapshot()
    return {
        "schema_version": 1,
        "comparison_version": COMPARISON_VERSION,
        "name": study.name,
        "status": "error" if has_error else "ok" if candidates else "no_candidate",
        "scope": "Eligible means current study constraints only; not full product approval",
        "input": snapshot,
        "provenance": {
            "package_version": __version__,
            "code_sha256": code_digest(),
            "input_sha256": input_digest(snapshot),
            "boundary_conditions": BOUNDARIES.copy(),
        },
        "results": rows,
        "eligible_mass_order": [row["id"] for row in candidates],
        "lightest_candidate_ids": lightest,
    }


def replay(saved: dict) -> dict:
    """Recompute from saved inputs, never trusting cached values as new solver output."""
    if not isinstance(saved, dict) or type(saved.get("schema_version")) is not int:
        raise ValueError("Invalid saved comparison report")
    if saved["schema_version"] != 1 or saved.get("comparison_version") != COMPARISON_VERSION:
        raise ValueError("Unsupported saved comparison version")
    provenance = saved.get("provenance")
    if not isinstance(provenance, dict) or provenance.get("code_sha256") != code_digest():
        raise ValueError(
            "Model/comparison code differs from saved report; use the original revision"
        )
    snapshot = saved.get("input")
    study = study_from_snapshot(snapshot)
    if input_digest(snapshot) != provenance.get("input_sha256"):
        raise ValueError("Saved input digest mismatch")
    return compare(study)
