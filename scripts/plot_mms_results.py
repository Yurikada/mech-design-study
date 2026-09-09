"""Export MMS field-norm convergence from the saved 12-case regular-mesh study."""

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
        raise ValueError("Figure requires calculable study")
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
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), layout="constrained")
    for family, color, marker in [
        ("T3", "#777777", "o"),
        ("Q4", "#ad5f15", "s"),
        ("T6", "#165f86", "^"),
        ("Q9", "#057344", "D"),
    ]:
        rows = sorted(
            [
                r
                for r in report["rows"]
                if r["settings"]["family"] == family
                and r["settings"]["distortion"] == 0
                and r["settings"]["integration"] == "full"
            ],
            key=lambda r: r["settings"]["nx"],
        )
        if len(rows) != 3 or any(r["settings"]["nx"] != 4 * r["settings"]["ny"] for r in rows):
            raise ValueError("Expected the documented three regular refinements per family")
        for ax, metric in zip(axes, ("displacement_l2", "strain_energy_norm"), strict=True):
            errors = [100 * r["errors"][metric] for r in rows]
            if min(errors) <= 0:
                raise ValueError("Cannot plot nonpositive errors on log scale")
            ax.loglog(
                [r["settings"]["nx"] for r in rows],
                errors,
                color=color,
                marker=marker,
                linestyle="--" if family.startswith("Q") else "-",
                label=family,
            )
    axes[0].set_title("Displacement field: relative L2 error")
    axes[1].set_title("Strain field: relative energy-norm error")
    for ax in axes:
        ax.set(xlabel="nx (ny = nx/4); both doubled per step", ylabel="Relative error (%)")
        ax.set_xticks([4, 8, 16], labels=["4", "8", "16"])
        ax.minorticks_off()
        ax.grid(alpha=0.25, which="both")
        ax.legend()
    fig.suptitle("Body-force MMS / nu=0 / regular mesh / log-log axes")
    for extension in ("svg", "png"):
        path = args.destination / f"mms-convergence.{extension}"
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
