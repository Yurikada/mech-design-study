"""Validated, replayable plane-stress educational benchmark."""

import hashlib
import json
import math
import platform
import re
import statistics
import tomllib
from pathlib import Path

import numpy as np
import scipy

from mech_design.comparison_input import exact_keys
from mech_design.plane_elements import FAMILIES
from mech_design.plane_solver import solve_plane


def parse_study(raw: dict) -> dict:
    exact_keys(raw, {"schema_version", "model", "designs"}, {"repetitions"}, "plane study")
    if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
        raise ValueError("Unsupported plane schema")
    m = raw["model"]
    bounds = {
        "length_m": (1e-4, 1.0),
        "depth_m": (1e-6, 1.0),
        "thickness_m": (1e-6, 1.0),
        "young_modulus_pa": (1e6, 1e12),
        "moment_nm": (1e-9, 1e3),
        "poisson_ratio": (0.0, 0.0),
    }
    exact_keys(m, set(bounds), set(), "model")
    for key, (low, high) in bounds.items():
        value = m[key]
        if type(value) not in (float, int) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"{key} must lie in [{low}, {high}]; this benchmark requires nu=0")
    if not 0.02 <= m["depth_m"] / m["length_m"] <= 0.5:
        raise ValueError("depth/length must lie in [0.02, 0.5]")
    if m["thickness_m"] > m["depth_m"] / 5:
        raise ValueError("Plane-stress benchmark requires thickness <= depth/5")
    if (
        6
        * m["moment_nm"]
        * m["length_m"]
        / (m["young_modulus_pa"] * m["thickness_m"] * m["depth_m"] ** 3)
        > 0.05
    ):
        raise ValueError("Reference tip displacement exceeds 5 percent of length")
    repetitions = raw.get("repetitions", 3)
    if type(repetitions) is not int or not 1 <= repetitions <= 5:
        raise ValueError("repetitions must be an integer from 1 to 5")
    designs = raw["designs"]
    if not isinstance(designs, list) or not 1 <= len(designs) <= 24:
        raise ValueError("Provide 1 to 24 designs")
    normalized, ids = [], set()
    for source in designs:
        exact_keys(
            source, {"id", "family", "nx", "ny"}, {"distortion", "integration", "fault"}, "design"
        )
        v = {"distortion": 0.0, "integration": "full", **source}
        if (
            not isinstance(v["id"], str)
            or not re.fullmatch(r"[A-Za-z0-9_-]+", v["id"])
            or v["id"] in ids
        ):
            raise ValueError("Design IDs must be unique ASCII identifiers")
        ids.add(v["id"])
        if not isinstance(v["family"], str) or v["family"] not in FAMILIES:
            raise ValueError("Unsupported element family")
        for key, maximum in [("nx", 32), ("ny", 8)]:
            if type(v[key]) is not int or not 1 <= v[key] <= maximum:
                raise ValueError(f"{key} out of range")
        factor = 2 if v["family"] in {"T6", "Q9"} else 1
        if (factor * v["nx"] + 1) * (factor * v["ny"] + 1) > 300:
            raise ValueError("Dense educational solver is limited to 300 nodes")
        if (
            type(v["distortion"]) not in (int, float)
            or not math.isfinite(v["distortion"])
            or not 0 <= v["distortion"] <= 0.35
        ):
            raise ValueError("distortion must lie in [0, 0.35]")
        if (
            not isinstance(v["integration"], str)
            or v["integration"] not in {"full", "high", "reduced"}
            or (v["integration"] == "reduced" and v["family"] != "Q4")
        ):
            raise ValueError("Unsupported integration rule")
        if "fault" in v and v["fault"] != "reverse_first_element":
            raise ValueError("Unsupported diagnostic fault")
        normalized.append(v)
    return {
        "schema_version": 1,
        "model": dict(m),
        "designs": normalized,
        "repetitions": repetitions,
    }


def provenance() -> dict:
    names = ["plane_elements.py", "plane_mesh.py", "plane_solver.py", "plane_study.py"]
    digest = hashlib.sha256()
    for name in names:
        digest.update(name.encode())
        digest.update(
            Path(__file__)
            .with_name(name)
            .read_text(encoding="utf-8")
            .replace("\r\n", "\n")
            .encode()
        )
    return {
        "model_version": "plane-pure-bending-v1",
        "code_sha256": digest.hexdigest(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
    }


def run_study(raw: dict) -> dict:
    study = parse_study(raw)
    rows = []
    for design in study["designs"]:
        try:
            solve_plane(study["model"], design)  # warmup, excluded from timings
            samples = [solve_plane(study["model"], design) for _ in range(study["repetitions"])]
            row = samples[-1]
            row["timing_samples_s"] = [s["timing_s"] for s in samples]
            row["timing_s"] = {
                key: statistics.median(s["timing_s"][key] for s in samples)
                for key in row["timing_s"]
            }
        except (ValueError, ArithmeticError, np.linalg.LinAlgError) as exc:
            row = {"status": "error", "error": str(exc), "results": None}
        rows.append({"id": design["id"], "settings": design, **row})
    valid = [row for row in rows if row["status"] != "error"]
    passing = [row["id"] for row in rows if row["status"] == "pass"]
    status = "error" if len(valid) != len(rows) else "ok" if passing else "fail"
    return {
        "schema_version": 1,
        "status": status,
        "scope": "nu=0 plane-stress pure bending benchmark only; not product approval",
        "input": study,
        "provenance": provenance(),
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "timing_method": (
                "one warmup; median of recorded repetitions; dense solver; rank check included"
            ),
        },
        "rows": rows,
        "qualified_ids": passing,
        "computed_tip_accuracy_order": [
            r["id"] for r in sorted(valid, key=lambda r: r["errors"]["tip"])
        ],
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
        raise ValueError("Replay requires matching schema, solver code and numpy/scipy versions")
    if "input" not in snapshot:
        raise ValueError("Replay input missing")
    return run_study(snapshot["input"])
