"""Synchronize lecture 5 result tables with its saved MMS calculation."""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START, END = "<!-- BEGIN MMS RESULTS -->", "<!-- END MMS RESULTS -->"


def tables(report):
    headings = ["要素", "nx × ny", "自由DOF", "e_u [%]", "e_E [%]", "先端誤差 [%]"]
    data = []
    for r in report["rows"]:
        v = r["settings"]
        if r["status"] != "computed":
            raise ValueError("Published MMS table expects calculable, balanced cases")
        data.append(
            [v["family"], f"{v['nx']} × {v['ny']}", str(r["free_dofs"])]
            + [
                f"{100 * r['errors'][m]:.6f}"
                for m in ("displacement_l2", "strain_energy_norm", "tip")
            ]
        )
    rate_headings = ["要素", "細分化", "p_obs（e_u）", "p_obs（e_E）"]
    rates = []
    for pair in report["refinement_pairs"]:
        coarse, fine = pair["coarse_id"], pair["fine_id"]
        rates.append(
            [coarse.split("-")[0], f"{coarse.split('-')[1]} → {fine.split('-')[1]}"]
            + [
                f"{r['value']:.4f}" if r["value"] is not None else "N/A"
                for r in pair["observed_orders"].values()
            ]
        )
    return [
        ("12条件の場の誤差と先端誤差", headings, data),
        ("hを半減した各区間の観測収束次数", rate_headings, rates),
    ]


def render(report, suffix):
    blocks = []
    for title, headings, data in tables(report):
        if suffix == ".md":
            blocks.append(
                title
                + "\n\n"
                + "\n".join(
                    "| " + " | ".join(row) + " |"
                    for row in [headings, ["---"] * len(headings), *data]
                )
            )
        else:
            head = "".join(f"<th>{s}</th>" for s in headings)
            body = "".join("<tr>" + "".join(f"<td>{s}</td>" for s in row) + "</tr>" for row in data)
            blocks.append(
                f'<div class="table-wrap"><table><caption>{title}</caption>'
                f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"
            )
    return START + "\n" + "\n\n".join(blocks) + "\n" + END


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = json.loads(
        (ROOT / "docs/learning/assets/mms-results.json").read_text(encoding="utf-8")
    )
    for suffix in (".md", ".html"):
        path = ROOT / f"docs/learning/05-mesh-convergence{suffix}"
        text = path.read_text(encoding="utf-8")
        start, end = text.index(START), text.index(END) + len(END)
        updated = text[:start] + render(report, suffix) + text[end:]
        if args.check:
            if text != updated:
                raise SystemExit(f"Stale MMS table: {path.name}")
        else:
            path.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()
