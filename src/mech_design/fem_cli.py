"""Run and save a reproducible beam-FEM verification study."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from mech_design.fem_study import load_fem, replay_fem, run_fem


def render(report: dict) -> str:
    lines = [
        f"FEM verification: {report['verification_status']}",
        report["scope"],
        "elements | deflection_mm | root_force_N | root_moment_Nm | f1_Hz | f1_error_percent",
    ]
    for row in report["meshes"]:
        if row["status"] == "error":
            lines.append(f"{row['elements']} | ERROR: {row['error']}")
            continue
        mode = row["modes"][0]
        lines.append(
            f"{row['elements']} | {row['tip_deflection_m'] * 1000:.8f} | "
            f"{row['root_force_n']:.8g} | {row['root_moment_nm']:.8g} | "
            f"{mode['frequency_hz']:.8f} | {100 * mode['relative_error']:.8g}"
        )
        for m in row["modes"][1:]:
            detail = (
                f"{m['frequency_hz']:.6f} Hz, error={100 * m['relative_error']:.6g}%"
                if m["status"] == "computed"
                else m["reason"]
            )
            lines.append(f"  mode {m['mode']}: {m['status']} {detail}")
    for c in report["verification_checks"]:
        lines.append(f"[{c['status']}] {c['metric']}: {c['value']}")
    design = report["design_evaluation"]
    if design:
        lines.append(f"Design overall: {design['overall_status']} (FEM beam + analytical thermal)")
        lines.append(
            "Not evaluated: "
            + ", ".join(
                r["discipline"] for r in design["evaluations"] if r["status"] == "not_evaluated"
            )
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study", nargs="?", type=Path)
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path, help="Save full JSON to a new file")
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args(argv)
    if (args.study is None) == (args.replay is None):
        parser.error("Provide study TOML or --replay JSON exclusively")
    try:
        report = (
            replay_fem(json.loads(args.replay.read_text(encoding="utf-8")))
            if args.replay
            else run_fem(load_fem(args.study))
        )
        serialized = json.dumps(report, ensure_ascii=True, indent=2, allow_nan=False)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(serialized + "\n")
    except (OSError, ValueError, ArithmeticError, np.linalg.LinAlgError) as exc:
        print(f"FEM error: {exc}", file=sys.stderr)
        return 1
    print(serialized if args.json else render(report))
    if report["verification_status"] == "error":
        return 1
    design = report["design_evaluation"]
    if report["verification_status"] == "fail" or (design and design["overall_status"] == "fail"):
        return 2
    if report["verification_status"] == "incomplete" or (
        args.require_complete and design and design["overall_status"] == "incomplete"
    ):
        return 3
    return 0
