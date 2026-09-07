"""Text and JSON presentation for the constrained comparison learning case."""

import argparse
import json
import sys
from pathlib import Path

from mech_design.comparison import compare, replay
from mech_design.comparison_input import load_study


def render(report: dict) -> str:
    lines = [
        f"Comparison: {report['name']}",
        f"Status: {report['status']}",
        report["scope"],
        f"Requirements: {report['input']['requirements_version']}",
        "ID | candidate | mass_g | stress_MPa | deflection_mm | frequency_Hz | temperature_K"
        " | physical_overall | unevaluated",
    ]
    for row in report["results"]:
        result = row["evaluation"]
        if row["candidate_status"] == "error":
            lines.append(f"{row['id']} | error | {row['error']}")
            continue
        metrics = {r["metric"]: r["value"] for r in result["evaluations"]}
        count = sum(r["status"] == "not_evaluated" for r in result["evaluations"])
        lines.append(
            f"{row['id']} | {row['candidate_status']} | {result['mass_kg'] * 1000:.2f} | "
            f"{metrics['root_stress'] / 1e6:.3f} | {metrics['tip_deflection'] * 1000:.5f} | "
            f"{metrics['first_frequency']:.3f} | {metrics['tip_temperature']:.3f} | "
            f"{result['overall_status']} | {count}"
        )
        for item in [*result["evaluations"], *row["requirements"]]:
            if item["status"] == "fail":
                lines.append(
                    f"  FAIL {item['metric']}: {item['value']:.6g} {item['unit']} "
                    f"{item['relation']} {item['limit']:.6g}; "
                    f"margin={item['margin']:.6g} {item['unit']}"
                )
        pending = [r["discipline"] for r in result["evaluations"] if r["status"] == "not_evaluated"]
        lines.append(f"  Not evaluated: {', '.join(pending) or 'none'}")
    lines.append("Eligible mass order: " + (", ".join(report["eligible_mass_order"]) or "none"))
    lines.append(
        "Lightest within study: " + (", ".join(report["lightest_candidate_ids"]) or "none")
    )
    if report["status"] == "error":
        lines.append("Errors remain: no lightest-candidate conclusion is issued.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare geometry variants under shared conditions"
    )
    parser.add_argument("study", nargs="?", type=Path)
    parser.add_argument("--replay", type=Path, help="Recompute from a saved JSON input snapshot")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path, help="Save full JSON to a NEW file")
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args(argv)
    if (args.study is None) == (args.replay is None):
        parser.error("Provide a study TOML or --replay JSON, exclusively")
    try:
        if args.replay:
            report = replay(json.loads(args.replay.read_text(encoding="utf-8")))
        else:
            report = compare(load_study(args.study))
        serialized = json.dumps(report, ensure_ascii=True, indent=2, allow_nan=False)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(serialized + "\n")
    except (OSError, ValueError, ArithmeticError) as exc:
        print(f"Comparison error: {exc}", file=sys.stderr)
        return 1
    print(serialized if args.json else render(report))
    if report["status"] == "error":
        return 1
    if report["status"] == "no_candidate":
        return 2
    if args.require_complete and any(
        r["status"] == "not_evaluated"
        for row in report["results"]
        for r in row["evaluation"]["evaluations"]
    ):
        return 3
    return 0
