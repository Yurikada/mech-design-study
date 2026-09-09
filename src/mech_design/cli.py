import argparse
import json
import sys
from pathlib import Path

from mech_design.case import load_case
from mech_design.evaluation import evaluate


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "mms":
        from mech_design.mms_cli import main as mms_main

        return mms_main(argv[1:])
    if argv and argv[0] == "plane":
        from mech_design.plane_cli import main as plane_main

        return plane_main(argv[1:])
    if argv and argv[0] == "fem":
        from mech_design.fem_cli import main as fem_main

        return fem_main(argv[1:])
    if argv and argv[0] == "compare":
        from mech_design.comparison_cli import main as compare_main

        return compare_main(argv[1:])
    parser = argparse.ArgumentParser(
        description="Evaluate a mechanical design learning case",
        epilog="For multi-case comparison: mech-study compare --help",
    )
    parser.add_argument("case", type=Path)
    parser.add_argument("--json", action="store_true", help="Emit SI-valued structured results")
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Return exit 3 if any discipline remains unevaluated",
    )
    args = parser.parse_args(argv)
    try:
        report = evaluate(load_case(args.case))
        serialized = json.dumps(report, ensure_ascii=True, indent=2, allow_nan=False)
    except (OSError, ValueError, ArithmeticError) as exc:
        print(f"Case evaluation error: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(serialized)
    else:
        print(f"Case: {report['case']}")
        print(f"Overall: {report['overall_status'].upper()}")
        print(report["scope"])
        print(f"Mass: {report['mass_kg']:.6g} kg")
        for item in report["evaluations"]:
            if item["value"] is None:
                detail = item["note"]
            else:
                detail = (
                    f"{item['value']:.6g} {item['unit']} {item['relation']} "
                    f"{item['limit']:.6g}; margin={item['margin']:.6g} {item['unit']}"
                )
            print(f"[{item['status']}] {item['discipline']}/{item['metric']}: {detail}")
    if report["overall_status"] == "error":
        return 1
    if report["overall_status"] == "fail":
        return 2
    if args.require_complete and report["overall_status"] == "incomplete":
        return 3
    return 0
