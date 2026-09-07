"""Export standalone scientific figures from a saved FEM report (Matplotlib 3.10.7).

Chart contract: convergence versus element count (5 mesh levels, not a time trend),
relative frequency error in percent on a log axis; 3 line styles distinguish modes.
Second figure: 201 spatial samples per mode, 16-element FEM versus analytical shape.
One blue palette root and neutral references; SVG/PNG files for the GitHub lesson.
"""

import argparse
import json
import math
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
    if report["input"]["settings"]["mode_count"] != 3 or report["input"]["settings"][
        "elements"
    ] != [1, 2, 4, 8, 16]:
        raise ValueError("This lecture plot expects 3 modes on meshes [1,2,4,8,16]")
    if report["verification_status"] != "pass":
        raise ValueError("Publish verified results only")
    args.destination.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.fonttype": "none",
        }
    )
    fig, ax = plt.subplots(figsize=(7.4, 4.4), layout="constrained")
    for i, (style, marker, color) in enumerate(
        [("-", "o", "#165f86"), ("--", "s", "#367da5"), (":", "^", "#182933")]
    ):
        points = [
            (r["elements"], r["modes"][i]["relative_error"] * 100)
            for r in report["meshes"]
            if r["modes"][i]["status"] == "computed"
        ]
        ax.plot(
            *zip(*points, strict=True),
            linestyle=style,
            marker=marker,
            color=color,
            label=f"Mode {i + 1}",
        )
    ax.set(
        xscale="log",
        yscale="log",
        xlabel="Number of elements",
        ylabel="Relative frequency error (%)",
        title="Beam FEM: mesh convergence",
    )
    ax.set_xticks([1, 2, 4, 8, 16], labels=[1, 2, 4, 8, 16])
    ax.axhline(0.1, color=".4", lw=1, ls="-.", label="Verification target: 0.1%")
    ax.grid(axis="y", alpha=0.2)
    ax.legend(fontsize=9)
    fig.supxlabel("Cubic Hermite / consistent mass; mode 3 unavailable at 1 element", fontsize=9)
    for ext in ("svg", "png"):
        fig.savefig(args.destination / f"fem-convergence.{ext}", dpi=160)
    plt.close(fig)
    fig, axes = plt.subplots(3, 1, figsize=(7.4, 7.2), layout="constrained", sharex=True)
    for i, (ax, mode) in enumerate(zip(axes, report["meshes"][-1]["modes"], strict=True)):
        beta = report["reference"]["beta_roots"][i]
        c = (math.cosh(beta) + math.cos(beta)) / (math.sinh(beta) + math.sin(beta))
        x = mode["shape_x_over_l"]
        y = [
            math.cosh(beta * t)
            - math.cos(beta * t)
            - c * (math.sinh(beta * t) - math.sin(beta * t))
            for t in x
        ]
        scale = max(abs(v) for v in y) * (1 if y[-1] >= 0 else -1)
        ax.plot(x, [v / scale for v in y], color=".25", lw=2, label="Analytical")
        ax.plot(x, mode["shape_w_normalized"], color="#165f86", ls="--", label="FEM")
        ax.set(
            title=f"Mode {i + 1}: {mode['frequency_hz']:.3f} Hz",
            ylim=(-1.1, 1.1),
            ylabel="Normalized w",
        )
        ax.axhline(0, color=".7", lw=0.6)
        ax.legend(loc="upper left", fontsize=9)
    axes[-1].set_xlabel("Position x / L")
    fig.suptitle("Beam mode shapes: 16 elements")
    fig.supxlabel(
        "Arbitrary amplitude: max sampled |w| = 1, tip positive; not forced response", fontsize=9
    )
    for ext in ("svg", "png"):
        fig.savefig(args.destination / f"fem-modes.{ext}", dpi=160)
    plt.close(fig)
    (args.destination / "fem-results.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    for name in ("fem-convergence.svg", "fem-modes.svg"):
        path = args.destination / name
        path.write_text(
            "\n".join(line.rstrip() for line in path.read_text(encoding="utf-8").splitlines())
            + "\n",
            encoding="utf-8",
        )
    print(f"Exported verified figures with Matplotlib {matplotlib.__version__}")


if __name__ == "__main__":
    main()
