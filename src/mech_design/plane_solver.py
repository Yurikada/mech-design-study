"""Plane-stress pure bending benchmark (nu=0), using dimensionless assembly."""

from time import perf_counter

import numpy as np
from scipy.linalg import eigh, solve

from mech_design.plane_elements import kinematics, quadrature, shape, stiffness, validation_points
from mech_design.plane_mesh import boundary_load, mesh


def solve_plane(model: dict, design: dict) -> dict:
    length, depth, thickness = (model[k] for k in ("length_m", "depth_m", "thickness_m"))
    young, moment = model["young_modulus_pa"], model["moment_nm"]
    h = depth / length
    family, integration = design["family"], design["integration"]
    grid = mesh(design["nx"], design["ny"], family, h, design["distortion"])
    nodes, cells = grid["nodes"], grid["cells"]
    if design.get("fault") == "reverse_first_element":
        # Diagnostic fixture: deliberately reverse the complete local node ordering.
        permutations = {
            "T3": [0, 2, 1],
            "T6": [0, 2, 1, 5, 4, 3],
            "Q4": [0, 3, 2, 1],
            "Q9": [0, 3, 2, 1, 7, 6, 5, 4, 8],
        }
        cells[0] = [cells[0][i] for i in permutations[family]]
    start = perf_counter()
    k = np.zeros((2 * len(nodes), 2 * len(nodes)))
    min_det, max_cond = float("inf"), 0.0
    for cell in cells:
        local, det, cond = stiffness(family, nodes[cell], integration)
        dofs = np.array([[2 * i, 2 * i + 1] for i in cell]).ravel()
        k[np.ix_(dofs, dofs)] += local
        min_det, max_cond = min(min_det, det), max(max_cond, cond)
    f = boundary_load(nodes, grid["right_edges"], h)
    fixed = np.repeat(nodes[:, 0] == 0, 2)
    free = np.flatnonzero(~fixed)
    assembly_s = perf_counter() - start
    start = perf_counter()
    reduced = k[np.ix_(free, free)]
    eigenvalues = eigh(reduced, eigvals_only=True)
    eigen_ratio = float(eigenvalues[0] / eigenvalues[-1])
    if eigen_ratio <= 1e-12:
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
    stress_scale = moment / (thickness * length**2)
    stress_ref = 6 * moment / (thickness * depth**2)
    d = np.diag([1.0, 1.0, 0.5])

    def point_values(point: tuple) -> list:
        values = []
        for index, cell in enumerate(cells):
            xy = nodes[cell]
            if np.any(np.array(point) < xy.min(axis=0) - 1e-10) or np.any(
                np.array(point) > xy.max(axis=0) + 1e-10
            ):
                continue
            rs = np.array([1 / 3, 1 / 3] if family.startswith("T") else [0.0, 0.0])
            for _ in range(20):
                n, dn = shape(family, *rs)
                delta = np.linalg.solve(xy.T @ dn, np.array(point) - n @ xy)
                rs += delta
                if np.linalg.norm(delta) < 1e-12:
                    break
            inside = (
                (min(rs) >= -1e-9 and sum(rs) <= 1 + 1e-9)
                if family.startswith("T")
                else max(abs(rs)) <= 1 + 1e-9
            )
            n, b, _, _ = kinematics(family, xy, *rs)
            if inside and np.linalg.norm(n @ xy - point) < 1e-9:
                local_q = q.reshape(-1, 2)[cell].ravel()
                values.append(
                    {
                        "element": index,
                        "displacement_m": (n @ local_q.reshape(-1, 2) * q_scale).tolist(),
                        "stress_pa": (d @ b @ local_q * stress_scale).tolist(),
                    }
                )
        if not values:
            raise ValueError("evaluation_point_not_found")
        return values

    tip = point_values((1.0, 0.0))
    stress = point_values((0.45, h / 2))
    zero_stress = np.zeros(2)
    for cell in cells:
        local_q = q.reshape(-1, 2)[cell].ravel()
        points = validation_points(family) + [(r, s) for r, s, _ in quadrature(family, integration)]
        for r, s in points:
            _, b, _, _ = kinematics(family, nodes[cell], r, s)
            sigma = d @ b @ local_q * stress_scale
            zero_stress = np.maximum(zero_stress, abs(sigma[1:]) / stress_ref)
    inertia = thickness * depth**3 / 12
    tip_ref = moment * length**2 / (2 * young * inertia)
    energy_ref = moment**2 * length / (2 * young * inertia)
    energy = float(0.5 * q @ k @ q * moment**2 / (young * thickness * length**2))
    reactions = residual.reshape(-1, 2)[nodes[:, 0] == 0] * moment / length
    root_nodes = nodes[nodes[:, 0] == 0] * length
    root_moment = float(
        np.sum(root_nodes[:, 0] * reactions[:, 1] - root_nodes[:, 1] * reactions[:, 0])
    )
    errors = {
        "tip": max(abs(v["displacement_m"][1] / tip_ref - 1) for v in tip),
        "energy": abs(energy / energy_ref - 1),
        "stress_x": max(abs(v["stress_pa"][0] / (-stress_ref) - 1) for v in stress),
        "sampled_stress_y": float(zero_stress[0]),
        "sampled_shear": float(zero_stress[1]),
        "reaction_force": float(np.linalg.norm(reactions.sum(axis=0)) / (moment / depth)),
        "reaction_moment": abs(root_moment / moment + 1),
        "residual": residual_error,
    }
    tolerances = {
        "tip": 0.001,
        "energy": 0.001,
        "stress_x": 0.01,
        "sampled_stress_y": 0.01,
        "sampled_shear": 0.01,
        "reaction_force": 1e-8,
        "reaction_moment": 1e-8,
        "residual": 1e-8,
    }
    checks = {key: value <= tolerances[key] for key, value in errors.items()}
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "errors": errors,
        "tolerances": tolerances,
        "checks": checks,
        "nodes": len(nodes),
        "elements": len(cells),
        "free_dofs": len(free),
        "tip_deflection_m": tip[0]["displacement_m"][1],
        "energy_j": energy,
        "root_force_n": reactions.sum(axis=0).tolist(),
        "root_moment_nm": root_moment,
        "reference": {
            "tip_deflection_m": tip_ref,
            "energy_j": energy_ref,
            "stress_scale_pa": stress_ref,
        },
        "stress_probe": {"point_m": [0.45 * length, depth / 2], "element_sided_values": stress},
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
        "timing_s": {
            "assembly": assembly_s,
            "solve_including_rank_check": solve_s,
            "postprocess": perf_counter() - start,
        },
    }
