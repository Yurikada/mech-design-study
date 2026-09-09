"""Export actual plane-bending errors versus free DOFs; no error clipping."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    if report["status"] != "ok":
        raise ValueError("This figure expects the normal, calculable study")
    args.destination.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "svg.fonttype": "none",
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), layout="constrained")
    for family, color, marker, style in [
        ("T3", "#165f86", "o", "-"),
        ("Q4", "#555555", "s", "--"),
        ("T6", "#165f86", "^", "-"),
        ("Q9", "#555555", "D", "--"),
    ]:
        rows = sorted(
            [
                r
                for r in report["rows"]
                if r["settings"]["family"] == family
                and r["settings"]["distortion"] == 0
                and r["settings"]["integration"] == "full"
            ],
            key=lambda r: r["free_dofs"],
        )
        ax = axes[0 if family in {"T3", "Q4"} else 1]
        ax.plot(
            [r["free_dofs"] for r in rows],
            [100 * r["errors"]["tip"] for r in rows],
            color=color,
            marker=marker,
            linestyle=style,
            label=family,
        )
    axes[0].set(
        ylim=(0, 100), title="Linear elements: refinement", ylabel="Tip displacement error (%)"
    )
    axes[0].axhline(0.1, color="#777777", linestyle=":", label="Tolerance 0.1%")
    axes[1].set(
        ylim=(0, None),
        title="Quadratic elements: roundoff scale",
        ylabel="Tip displacement error (%)",
    )
    axes[1].ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
    for ax in axes:
        ax.set_xlabel("Free displacement DOFs")
        ax.grid(alpha=0.2)
        ax.legend()
    fig.suptitle("Pure bending, nu=0, regular mesh / Different vertical scales")
    for extension in ["svg", "png"]:
        path = args.destination / f"plane-convergence.{extension}"
        fig.savefig(
            path, dpi=180, metadata={"Creator": "mech-design-study"} if extension == "svg" else None
        )
        if extension == "svg":
            path.write_text(
                "\n".join(line.rstrip() for line in path.read_text(encoding="utf-8").splitlines())
                + "\n",
                encoding="utf-8",
            )
    plt.close(fig)


if __name__ == "__main__":
    main()
