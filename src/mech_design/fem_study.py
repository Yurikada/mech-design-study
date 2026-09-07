"""Verification study and adapter: convergence is distinct from design acceptance."""

import hashlib
import json
import math
import tomllib
from dataclasses import asdict
from pathlib import Path

import numpy as np
import scipy
from scipy.linalg import LinAlgWarning
from scipy.optimize import brentq

from mech_design.case import load_case, parse_case
from mech_design.comparison_input import exact_keys
from mech_design.evaluation import Evaluation, check, evaluate, overall_status
from mech_design.fem_beam import solve_beam

VERSION = "hermite_beam_study_v1"
SETTINGS = {"elements", "mode_count", "element_type", "mass_matrix", "boundary"}


def digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def code_digest() -> str:
    root = Path(__file__).parent
    files = [
        "fem_beam.py",
        "fem_study.py",
        "case.py",
        "models.py",
        "evaluation.py",
        "comparison_input.py",
    ]
    return hashlib.sha256(
        "\n".join(f + "\n" + (root / f).read_text(encoding="utf-8") for f in files).encode()
    ).hexdigest()


def validate(snapshot: dict) -> None:
    exact_keys(snapshot, {"schema_version", "case", "settings"}, set(), "FEM snapshot")
    if type(snapshot["schema_version"]) is not int or snapshot["schema_version"] != 1:
        raise ValueError("Only FEM schema_version = 1 is supported")
    parse_case(snapshot["case"])
    settings = snapshot["settings"]
    exact_keys(settings, SETTINGS, set(), "FEM settings")
    for field, expected in [
        ("element_type", "hermite_cubic"),
        ("mass_matrix", "consistent"),
        ("boundary", "clamped_free"),
    ]:
        if settings[field] != expected:
            raise ValueError(f"Only {field} = {expected!r} is supported")
    counts = settings["elements"]
    if (
        not isinstance(counts, list)
        or not counts
        or any(type(n) is not int or not 1 <= n <= 64 for n in counts)
        or any(b != 2 * a for a, b in zip(counts, counts[1:], strict=False))
    ):
        raise ValueError("elements must be a nonempty doubling sequence of integers in [1,64]")
    if type(settings["mode_count"]) is not int or not 1 <= settings["mode_count"] <= 3:
        raise ValueError("mode_count must be in [1,3]")


def load_fem(path: Path) -> dict:
    with path.open("rb") as stream:
        raw = tomllib.load(stream)
    exact_keys(raw, {"schema_version", "base_case", "settings"}, set(), "FEM study")
    if not isinstance(raw["base_case"], str) or not raw["base_case"].strip():
        raise ValueError("base_case must be a nonempty path")
    case = load_case(path.parent / raw["base_case"])
    snapshot = {
        "schema_version": raw["schema_version"],
        "case": {"schema_version": 1, **asdict(case)},
        "settings": raw["settings"],
    }
    validate(snapshot)
    return snapshot


def run_fem(snapshot: dict) -> dict:
    validate(snapshot)
    case = parse_case(snapshot["case"])
    b = case.beam
    settings = snapshot["settings"]
    rigidity = b.young_modulus_pa * b.width_m * b.thickness_m**3 / 12
    betas = [
        brentq(lambda x: math.cosh(x) * math.cos(x) + 1, a, z, xtol=1e-14)
        for a, z in [(1, 2), (4, 5), (7, 8)]
    ]
    frequencies = [
        beta**2
        / (2 * math.pi)
        * math.sqrt(rigidity / (b.density_kg_m3 * b.width_m * b.thickness_m * b.length_m**4))
        for beta in betas[: settings["mode_count"]]
    ]
    reference = {
        "tip_deflection_m": b.tip_force_n * b.length_m**3 / (3 * rigidity),
        "root_force_n": -b.tip_force_n,
        "root_moment_nm": -b.tip_force_n * b.length_m,
        "frequencies_hz": frequencies,
        "beta_roots": betas[: len(frequencies)],
    }
    rows = []
    for n in settings["elements"]:
        try:
            row = solve_beam(b, n, settings["mode_count"])
            # Verify serializability before admitting the row into the report.
            json.dumps(row, allow_nan=False)
            row["status"] = "computed"
            row["static_relative_errors"] = {
                key: abs((row[key] - reference[key]) / reference[key])
                for key in ("tip_deflection_m", "root_force_n", "root_moment_nm")
            }
            for mode in row["modes"]:
                if mode["status"] == "computed":
                    ref = frequencies[mode["mode"] - 1]
                    mode["relative_error"] = abs((mode["frequency_hz"] - ref) / ref)
            rows.append(row)
        except (ValueError, ArithmeticError, np.linalg.LinAlgError, LinAlgWarning) as exc:
            rows.append({"elements": n, "status": "error", "error": str(exc)})
    checks = []
    design = None
    status = "error"
    if all(row["status"] == "computed" for row in rows):
        fine = rows[-1]
        checks.append(
            {
                "metric": "static_relative_error",
                "limit": 1e-8,
                "value": max(max(r["static_relative_errors"].values()) for r in rows),
            }
        )
        checks.append(
            {
                "metric": "normalized_residual",
                "limit": 1e-10,
                "value": max(
                    max(
                        [r["static_residual"]]
                        + [m["residual"] for m in r["modes"] if m["status"] == "computed"]
                    )
                    for r in rows
                ),
            }
        )
        for mode in fine["modes"]:
            i = mode["mode"] - 1
            prior = rows[-2]["modes"][i] if len(rows) >= 2 else None
            error = mode.get("relative_error")
            change = None
            if prior and prior["status"] == mode["status"] == "computed":
                change = abs((mode["frequency_hz"] - prior["frequency_hz"]) / mode["frequency_hz"])
            checks.extend(
                [
                    {"metric": f"mode_{i + 1}_reference_error", "value": error, "limit": 0.001},
                    {"metric": f"mode_{i + 1}_refinement_change", "value": change, "limit": 0.001},
                ]
            )
        for item in checks:
            item["status"] = (
                "not_evaluated"
                if item["value"] is None
                else "pass"
                if item["value"] <= item["limit"]
                else "fail"
            )
        checks.append(
            {
                "metric": "finest_elements",
                "value": fine["elements"],
                "minimum": 16,
                "status": "pass" if fine["elements"] >= 16 else "not_evaluated",
            }
        )
        status = (
            "fail"
            if any(c["status"] == "fail" for c in checks)
            else "incomplete"
            if any(c["status"] == "not_evaluated" for c in checks)
            else "pass"
        )
        # Thermal remains analytical. Replace only the three beam indicators with FEM output.
        design = evaluate(case)
        for metric, value, method in [
            ("root_stress", fine["root_stress_pa"], "hermite_curvature_v1"),
            ("tip_deflection", fine["tip_deflection_m"], "hermite_static_v1"),
            ("first_frequency", fine["modes"][0]["frequency_hz"], "hermite_consistent_mass_v1"),
        ]:
            index = next(i for i, r in enumerate(design["evaluations"]) if r["metric"] == metric)
            old = design["evaluations"][index]
            design["evaluations"][index] = asdict(
                check(
                    old["discipline"],
                    metric,
                    value,
                    old["unit"],
                    old["limit"],
                    old["relation"],
                    method,
                    old["note"] + f"; FEM elements={fine['elements']}",
                )
            )
        design["model_version"] = "hermite_beam_plus_analytical_thermal_v1"
        design["overall_status"] = overall_status([Evaluation(**r) for r in design["evaluations"]])
    return {
        "schema_version": 1,
        "model_version": VERSION,
        "input": snapshot,
        "scope": "Educational beam verification; not M2b or real-product validation",
        "provenance": {
            "code_sha256": code_digest(),
            "input_sha256": digest(snapshot),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "integration": "exact closed-form element stiffness and consistent mass",
            "scaling": "x/L; qbar=[w/L,theta]; unit static tip force",
            "solver": "scipy.linalg.solve(pos), eigh(gvd); clamped DOFs 0,1",
            "residual": "norm(Ax-b)/(norm(A)*norm(x)+norm(b)) in scaled coordinates",
            "mode_normalization": "max sampled |w|=1; tip positive; rotations=Ltheta/max|w|",
        },
        "reference": reference,
        "meshes": rows,
        "verification_checks": checks,
        "verification_status": status,
        "design_evaluation": design,
    }


def replay_fem(saved: dict) -> dict:
    if (
        not isinstance(saved, dict)
        or saved.get("model_version") != VERSION
        or type(saved.get("schema_version")) is not int
        or saved["schema_version"] != 1
    ):
        raise ValueError("Unsupported FEM report")
    p = saved.get("provenance", {})
    if not isinstance(p, dict) or (p.get("code_sha256"), p.get("numpy"), p.get("scipy")) != (
        code_digest(),
        np.__version__,
        scipy.__version__,
    ):
        raise ValueError("FEM code/dependency versions differ from saved report")
    snapshot = saved.get("input")
    validate(snapshot)
    if digest(snapshot) != p.get("input_sha256"):
        raise ValueError("Saved FEM input digest mismatch")
    return run_fem(snapshot)
