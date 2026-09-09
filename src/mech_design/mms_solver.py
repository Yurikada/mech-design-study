"""Body-force MMS solve, separate from the versioned pure-bending solver."""

from time import perf_counter

import numpy as np
from scipy.linalg import eigh, solve

from mech_design.mms_model import body_load, error_integrals, reference_norms
from mech_design.plane_elements import stiffness
from mech_design.plane_mesh import mesh


def solve_mms(model: dict, design: dict) -> dict:
    length, depth, thickness = (model[k] for k in ("length_m", "depth_m", "thickness_m"))
    young, moment = model["young_modulus_pa"], model["root_moment_scale_nm"]
    h = depth / length
    family = design["family"]
    grid = mesh(design["nx"], design["ny"], family, h, design["distortion"])
    nodes, cells = grid["nodes"], grid["cells"]
    if design.get("fault") == "reverse_first_element":
        permutations = {
            "T3": [0, 2, 1],
            "T6": [0, 2, 1, 5, 4, 3],
            "Q4": [0, 3, 2, 1],
            "Q9": [0, 3, 2, 1, 7, 6, 5, 4, 8],
        }
        cells[0] = [cells[0][i] for i in permutations[family]]
    start = perf_counter()
    k = np.zeros((2 * len(nodes), 2 * len(nodes)))
    f = np.zeros(2 * len(nodes))
    min_det, max_cond = float("inf"), 0.0
    for cell in cells:
        local, det, cond = stiffness(family, nodes[cell], design["integration"])
        dofs = np.array([[2 * i, 2 * i + 1] for i in cell]).ravel()
        k[np.ix_(dofs, dofs)] += local
        f[dofs] += body_load(family, nodes[cell], h)
        min_det, max_cond = min(min_det, det), max(max_cond, cond)
    fixed = np.repeat(nodes[:, 0] == 0, 2)
    free = np.flatnonzero(~fixed)
    assembly_s = perf_counter() - start
    start = perf_counter()
    reduced = k[np.ix_(free, free)]
    eigenvalues = eigh(reduced, eigvals_only=True)
    eigen_ratio = float(eigenvalues[0] / eigenvalues[-1])
    if not np.isfinite(eigen_ratio) or eigen_ratio <= 1e-12:
        raise ValueError("zero_energy_or_ill_conditioned_system")
    q = np.zeros(len(f))
    q[free] = solve(reduced, f[free], assume_a="pos")
    solve_s = perf_counter() - start
    start = perf_counter()
    residual = k @ q - f
    residual_error = float(np.linalg.norm(residual[free]) / max(np.linalg.norm(f), 1.0))
    if not np.all(np.isfinite(q)) or residual_error > 1e-8:
        raise ValueError("invalid_solution_or_residual")
    q_scale = moment / (young * thickness * length)
    energy_scale = moment**2 / (young * thickness * length**2)
    integrals = np.zeros(3)
    for cell in cells:
        integrals += error_integrals(family, nodes[cell], q.reshape(-1, 2)[cell].ravel(), h)
    denominators = reference_norms(h)
    norms = np.sqrt(integrals[:2] / denominators)
    # Evaluate the right-edge centre using its 1D trace, including meshes with odd ny.
    tip_values = []
    for edge in grid["right_edges"]:
        y0, y1 = nodes[edge[:2], 1]
        if min(y0, y1) <= 0 <= max(y0, y1):
            t = -y0 / (y1 - y0)
            weights = (
                np.array([1 - t, t])
                if len(edge) == 2
                else np.array([(1 - t) * (1 - 2 * t), t * (2 * t - 1), 4 * t * (1 - t)])
            )
            tip_values.append(float(weights @ q.reshape(-1, 2)[edge, 1] * q_scale))
    if not tip_values:
        raise ValueError("tip_point_not_found")
    inertia = thickness * depth**3 / 12
    tip_ref = moment * length**2 / (3 * young * inertia)
    energy_ref = moment**2 * length / (6 * young * inertia)
    energy = float(0.5 * integrals[2] * energy_scale)
    assembled_energy = float(0.5 * q @ k @ q * energy_scale)
    root = nodes[:, 0] == 0
    reactions = residual.reshape(-1, 2)[root] * moment / length
    root_moment = float(-np.sum(nodes[root, 1] * length * reactions[:, 0]))
    force = f.reshape(-1, 2) * moment / length
    body_moment = float(np.sum((nodes[:, 0] * force[:, 1] - nodes[:, 1] * force[:, 0]) * length))
    diagnostics = {
        "residual": residual_error,
        "body_force_balance": float(np.linalg.norm(force.sum(axis=0)) / (moment / depth)),
        "body_moment_balance": abs(body_moment / moment - 1),
        "reaction_force_balance": float(np.linalg.norm(reactions.sum(axis=0)) / (moment / depth)),
        "reaction_moment_balance": abs(root_moment / moment + 1),
    }
    checks = {key: value <= 1e-8 for key, value in diagnostics.items()}
    return {
        "status": "computed" if all(checks.values()) else "fail",
        "accuracy_status": "not_evaluated",
        "accuracy_note": "Field accuracy tolerance and asymptotic convergence gate are not set",
        "errors": {
            "displacement_l2": float(norms[0]),
            "strain_energy_norm": float(norms[1]),
            "tip": max(abs(v / tip_ref - 1) for v in tip_values),
            "total_energy": abs(energy / energy_ref - 1),
        },
        "diagnostics": diagnostics,
        "diagnostic_tolerance": 1e-8,
        "checks": checks,
        "nodes": len(nodes),
        "elements": len(cells),
        "free_dofs": len(free),
        "tip_deflection_m": tip_values[0],
        "energy_j": energy,
        "assembled_energy_j": assembled_energy,
        "body_force_n": force.sum(axis=0).tolist(),
        "body_moment_nm": body_moment,
        "root_force_n": reactions.sum(axis=0).tolist(),
        "root_moment_nm": root_moment,
        "reference": {"tip_deflection_m": tip_ref, "energy_j": energy_ref},
        "quality": {
            "min_det_j_dimensionless": min_det,
            "max_jacobian_condition": max_cond,
            "reduced_eigenvalue_ratio": eigen_ratio,
        },
        "mesh": {
            "nodes_m": (nodes * length).tolist(),
            "cells": cells,
            "fixed_dofs": np.flatnonzero(fixed).tolist(),
        },
        "displacements_m": (q.reshape(-1, 2) * q_scale).tolist(),
        "nodal_body_forces_n": force.tolist(),
        "timing_s": {
            "assembly": assembly_s,
            "solve_including_rank_check": solve_s,
            "postprocess": perf_counter() - start,
        },
    }
