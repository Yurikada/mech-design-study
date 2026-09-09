"""Compare plane-stress elements against the lecture 4 pure-bending solution."""

import argparse
import json
import sys
from pathlib import Path

from mech_design.plane_study import load_study, replay_study, run_study


def render(report: dict) -> str:
    lines = [
        f"Plane benchmark: {report['status']}",
        report["scope"],
        "ID | family | elements | nodes | free DOFs | tip error % | energy error % | status",
    ]
    for row in report["rows"]:
        if row["status"] == "error":
            lines.append(f"{row['id']} | ERROR: {row['error']} | results=N/A")
        else:
            lines.append(
                f"{row['id']} | {row['settings']['family']} | {row['elements']} | "
                f"{row['nodes']} | {row['free_dofs']} | {100 * row['errors']['tip']:.6g} | "
                f"{100 * row['errors']['energy']:.6g} | {row['status']}"
            )
            failed = [key for key, passed in row["checks"].items() if not passed]
            if failed:
                lines.append("  Outside tolerance: " + ", ".join(failed))
    lines.append("Qualified in this benchmark: " + ", ".join(report["qualified_ids"]))
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
        print(f"Plane benchmark error: {exc}", file=sys.stderr)
        return 1
    print(serialized if args.json else render(report))
    return {"ok": 0, "error": 1, "fail": 2}[report["status"]]
