"""Compare mesh refinements against the lecture 5 body-force manufactured solution."""

import argparse
import json
import sys
from pathlib import Path

from mech_design.mms_study import load_study, replay_study, run_study


def render(report: dict) -> str:
    lines = [
        f"MMS benchmark: {report['status']}",
        report["scope"],
        "ID | family | free DOFs | L2 error % | energy norm error % | tip error % | status",
    ]
    for row in report["rows"]:
        if row["status"] == "error":
            lines.append(f"{row['id']} | ERROR: {row['error']} | results=N/A")
        else:
            e = row["errors"]
            lines.append(
                f"{row['id']} | {row['settings']['family']} | {row['free_dofs']} | "
                f"{100 * e['displacement_l2']:.6g} | {100 * e['strain_energy_norm']:.6g} | "
                f"{100 * e['tip']:.6g} | {row['status']}"
            )
            failed = [k for k, passed in row["checks"].items() if not passed]
            if failed:
                lines.append("  Failed balance checks: " + ", ".join(failed))
    for pair in report["refinement_pairs"]:
        values = [
            f"{m}: {r['value']:.4f}" if r["value"] is not None else f"{m}: N/A ({r['reason']})"
            for m, r in pair["observed_orders"].items()
        ]
        lines.append(f"{pair['coarse_id']} -> {pair['fine_id']}: " + "; ".join(values))
    lines.append("Accuracy/asymptotic convergence: not_evaluated (no acceptance thresholds set)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study", nargs="?", type=Path)
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if (args.study is None) == (args.replay is None):
        parser.error("Provide study TOML or --replay JSON exclusively")
    try:
        report = replay_study(args.replay) if args.replay else run_study(load_study(args.study))
        serialized = json.dumps(report, ensure_ascii=True, indent=2, allow_nan=False)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(serialized + "\n")
    except (OSError, ValueError, ArithmeticError) as exc:
        print(f"MMS benchmark error: {exc}", file=sys.stderr)
        return 1
    print(serialized if args.json else render(report))
    return {"ok": 0, "error": 1, "fail": 2}[report["status"]]
