"""Validated MMS input, provenance, refinement pairs and replay.

The legacy plane implementation is deliberately unchanged so its published
code digest and load interpretation remain reproducible.
"""

import hashlib
import json
import math
import platform
import statistics
import tomllib
from pathlib import Path

import numpy as np
import scipy

from mech_design.comparison_input import exact_keys
from mech_design.mms_solver import solve_mms
from mech_design.plane_study import parse_study as parse_plane

RATE_FLOOR = 1e-10  # conservative reporting floor, not a measured roundoff bound
METRICS = ("displacement_l2", "strain_energy_norm")


def parse_study(raw: dict) -> dict:
    exact_keys(raw, {"schema_version", "model", "designs"}, {"repetitions"}, "MMS study")
    model = raw["model"]
    exact_keys(
        model,
        {
            "length_m",
            "depth_m",
            "thickness_m",
            "young_modulus_pa",
            "poisson_ratio",
            "root_moment_scale_nm",
        },
        set(),
        "MMS model",
    )
    legacy_model = dict(model)
    legacy_model["moment_nm"] = legacy_model.pop("root_moment_scale_nm")
    # Reuse bounded nu=0 geometry/design validation, including its conservative
    # pure-bending displacement bound (1.5 times the MMS reference tip value).
    validated = parse_plane({**raw, "model": legacy_model})
    return {**validated, "model": dict(model)}


def provenance() -> dict:
    names = [
        "mms_model.py",
        "mms_solver.py",
        "mms_study.py",
        "plane_elements.py",
        "plane_mesh.py",
        "plane_study.py",
        "comparison_input.py",
    ]
    digest = hashlib.sha256()
    for name in names:
        digest.update(name.encode())
        digest.update(Path(__file__).with_name(name).read_text(encoding="utf-8").encode())
    return {
        "model_version": "plane-variable-curvature-mms-v1",
        "code_sha256": digest.hexdigest(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
    }


def observed_rate(coarse: float, fine: float) -> dict:
    if not all(math.isfinite(e) and e > RATE_FLOOR for e in (coarse, fine)):
        return {
            "status": "not_evaluated",
            "value": None,
            "reason": "error_at_or_below_reporting_floor",
        }
    return {"status": "computed", "value": math.log2(coarse / fine)}


def refinement_pairs(rows: list) -> list:
    pairs = []
    for fine in rows:
        v = fine["settings"]
        if v["distortion"] != 0 or "fault" in v:
            continue
        candidates = [
            c
            for c in rows
            if c["settings"]["family"] == v["family"]
            and c["settings"]["integration"] == v["integration"]
            and c["settings"]["distortion"] == 0
            and "fault" not in c["settings"]
            and c["settings"]["nx"] * 2 == v["nx"]
            and c["settings"]["ny"] * 2 == v["ny"]
        ]
        for coarse in candidates:
            if coarse["status"] != "computed" or fine["status"] != "computed":
                rates = {
                    m: {
                        "status": "not_evaluated",
                        "value": None,
                        "reason": "pair_has_failed_or_error_row",
                    }
                    for m in METRICS
                }
            else:
                rates = {m: observed_rate(coarse["errors"][m], fine["errors"][m]) for m in METRICS}
            pairs.append(
                {
                    "coarse_id": coarse["id"],
                    "fine_id": fine["id"],
                    "h_ratio": 2,
                    "observed_orders": rates,
                }
            )
    return pairs


def run_study(raw: dict) -> dict:
    study = parse_study(raw)
    rows = []
    for design in study["designs"]:
        try:
            solve_mms(study["model"], design)
            samples = [solve_mms(study["model"], design) for _ in range(study["repetitions"])]
            row = samples[-1]
            row["timing_samples_s"] = [s["timing_s"] for s in samples]
            row["timing_s"] = {
                k: statistics.median(s["timing_s"][k] for s in samples) for k in row["timing_s"]
            }
        except (ValueError, ArithmeticError, np.linalg.LinAlgError) as exc:
            row = {
                "status": "error",
                "error": str(exc),
                "results": None,
                "accuracy_status": "not_evaluated",
            }
        rows.append({"id": design["id"], "settings": design, **row})
    status = (
        "error"
        if any(r["status"] == "error" for r in rows)
        else "fail"
        if any(r["status"] == "fail" for r in rows)
        else "ok"
    )
    return {
        "schema_version": 1,
        "status": status,
        "scope": (
            "nu=0 body-force MMS code verification; computed is not accuracy or product approval"
        ),
        "input": study,
        "provenance": provenance(),
        "model_settings": {
            "boundary": "left u=v=0; right/top/bottom traction-free",
            "body_force": "bx=-M0*y/(I*L) [N/m^3]; by=0; I=s*H^3/12",
            "body_load_quadrature": "5x5 Gauss; triangle Duffy transform",
            "error_quadrature": "5x5 Gauss; triangle Duffy transform",
            "reference_norms": "analytical rectangle integrals",
            "rate_reporting_floor": RATE_FLOOR,
            "rate_scope": "regular meshes, same family and stiffness rule, nx and ny both doubled",
        },
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "timing_method": "one warmup; median repetitions; dense solver including rank check",
        },
        "rows": rows,
        "refinement_pairs": refinement_pairs(rows),
        "convergence_status": "not_evaluated",
        "convergence_note": (
            "Observed orders are evidence, not an automatic asymptotic convergence gate"
        ),
    }


def load_study(path: Path) -> dict:
    with path.open("rb") as stream:
        return parse_study(tomllib.load(stream))


def replay_study(path: Path) -> dict:
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(snapshot, dict)
        or type(snapshot.get("schema_version")) is not int
        or snapshot.get("schema_version") != 1
        or snapshot.get("provenance") != provenance()
    ):
        raise ValueError(
            "Replay requires matching MMS schema, solver code and numpy/scipy versions"
        )
    if "input" not in snapshot:
        raise ValueError("Replay input missing")
    return run_study(snapshot["input"])
