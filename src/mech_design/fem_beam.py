"""Cubic Hermite beam, exact element matrices and consistent translational mass.

Solve on x/L with qbar=[w/L, theta], so mixed SI units do not pollute residuals.
The unit-load static solution is dimensionalized only after solving.
"""

import warnings

import numpy as np
from scipy.linalg import LinAlgWarning, cholesky, eigh, solve

from mech_design.case import Beam


def element_matrices(h: float) -> tuple[np.ndarray, np.ndarray]:
    if not np.isfinite(h) or h <= 0:
        raise ValueError("Element length must be finite and positive")
    k = (
        np.array(
            [
                [12, 6 * h, -12, 6 * h],
                [6 * h, 4 * h * h, -6 * h, 2 * h * h],
                [-12, -6 * h, 12, -6 * h],
                [6 * h, 2 * h * h, -6 * h, 4 * h * h],
            ]
        )
        / h**3
    )
    m = (
        h
        / 420
        * np.array(
            [
                [156, 22 * h, 54, -13 * h],
                [22 * h, 4 * h * h, 13 * h, -3 * h * h],
                [54, 13 * h, 156, -22 * h],
                [-13 * h, -3 * h * h, -22 * h, 4 * h * h],
            ]
        )
    )
    return k, m


def assemble(nodes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    nodes = np.asarray(nodes, dtype=float)
    if (
        nodes.ndim != 1
        or not 2 <= nodes.size <= 65
        or not np.isfinite(nodes).all()
        or nodes[0] != 0
        or nodes[-1] != 1
        or np.any(np.diff(nodes) <= 0)
    ):
        raise ValueError("Mesh must have 2..65 increasing finite nodes spanning [0,1]")
    k = np.zeros((2 * nodes.size, 2 * nodes.size))
    m = np.zeros_like(k)
    for i, h in enumerate(np.diff(nodes)):
        dofs = np.arange(2 * i, 2 * i + 4)
        ke, me = element_matrices(h)
        k[np.ix_(dofs, dofs)] += ke
        m[np.ix_(dofs, dofs)] += me
    return k, m


def interpolate(nodes: np.ndarray, q: np.ndarray, x: np.ndarray) -> np.ndarray:
    indices = np.clip(np.searchsorted(nodes, x, side="right") - 1, 0, len(nodes) - 2)
    h = nodes[indices + 1] - nodes[indices]
    s = (x - nodes[indices]) / h
    return (
        (1 - 3 * s * s + 2 * s**3) * q[2 * indices]
        + h * (s - 2 * s * s + s**3) * q[2 * indices + 1]
        + (3 * s * s - 2 * s**3) * q[2 * indices + 2]
        + h * (-s * s + s**3) * q[2 * indices + 3]
    )


def normalized_residual(a: np.ndarray, x: np.ndarray, b: np.ndarray) -> float:
    denominator = np.linalg.norm(a) * np.linalg.norm(x) + np.linalg.norm(b)
    if denominator == 0:
        raise ValueError("Residual normalization is undefined")
    return float(np.linalg.norm(a @ x - b) / denominator)


def solve_beam(beam: Beam, elements: int, mode_count: int = 3) -> dict:
    if type(elements) is not int or not 1 <= elements <= 64:
        raise ValueError("elements must be an integer in [1,64]")
    if type(mode_count) is not int or not 1 <= mode_count <= 3:
        raise ValueError("mode_count must be an integer in [1,3]")
    nodes = np.linspace(0, 1, elements + 1)
    k, m = assemble(nodes)
    kf, mf = k[2:, 2:], m[2:, 2:]
    for matrix in (kf, mf):
        if not np.isfinite(matrix).all() or not np.allclose(matrix, matrix.T, rtol=0, atol=1e-12):
            raise ValueError("Nonfinite or asymmetric assembled matrix")
        cholesky(matrix)  # Reject mechanisms and non-positive mass instead of filtering modes.
    force = np.zeros(2 * (elements + 1))
    force[-2] = 1
    u = np.zeros_like(force)
    with warnings.catch_warnings():
        warnings.simplefilter("error", LinAlgWarning)
        u[2:] = solve(kf, force[2:], assume_a="pos")
        eigenvalues, vectors = eigh(kf, mf, driver="gvd")
    if not np.isfinite(eigenvalues).all() or np.any(eigenvalues <= 0):
        raise ValueError("Non-positive or nonfinite eigenvalue; check supports and connectivity")
    area = beam.width_m * beam.thickness_m
    rigidity = beam.young_modulus_pa * beam.width_m * beam.thickness_m**3 / 12
    displacement_scale = beam.tip_force_n * beam.length_m**3 / rigidity
    if not np.isfinite(displacement_scale) or displacement_scale <= 0:
        raise ValueError("Invalid dimensional scale")
    w = u[::2] * displacement_scale
    theta = u[1::2] * displacement_scale / beam.length_m
    if w[-1] / beam.length_m > 0.05:
        raise ValueError("Deflection/length exceeds educational small-deflection limit 0.05")
    reaction = k @ u - force
    h = nodes[1] - nodes[0]
    curvature0 = -6 * u[0] / h**2 - 4 * u[1] / h + 6 * u[2] / h**2 - 2 * u[3] / h
    stress = abs(
        beam.young_modulus_pa
        * beam.thickness_m
        / 2
        * displacement_scale
        / beam.length_m**2
        * curvature0
    )
    frequency_scale = np.sqrt(rigidity / (beam.density_kg_m3 * area * beam.length_m**4))
    modes = []
    sample_x = np.linspace(0, 1, 201)
    for i in range(mode_count):
        if i >= len(eigenvalues):
            modes.append(
                {
                    "mode": i + 1,
                    "status": "not_evaluated",
                    "reason": "Insufficient free degrees of freedom",
                }
            )
            continue
        vector = np.zeros_like(force)
        vector[2:] = vectors[:, i]
        samples = interpolate(nodes, vector, sample_x)
        scale = np.max(np.abs(samples)) * (1 if samples[-1] >= 0 else -1)
        vector /= scale
        samples /= scale
        modes.append(
            {
                "mode": i + 1,
                "status": "computed",
                "frequency_hz": float(np.sqrt(eigenvalues[i]) * frequency_scale / (2 * np.pi)),
                "residual": normalized_residual(kf, vector[2:], eigenvalues[i] * mf @ vector[2:]),
                "node_w_normalized": vector[::2].tolist(),
                "node_ltheta_normalized": vector[1::2].tolist(),
                "shape_x_over_l": sample_x.tolist(),
                "shape_w_normalized": samples.tolist(),
            }
        )
    result = {
        "elements": elements,
        "free_dofs": 2 * elements,
        "nodes_m": (nodes * beam.length_m).tolist(),
        "connectivity": [[i, i + 1] for i in range(elements)],
        "fixed_dofs": [0, 1],
        "dof_order": "w0,theta0,w1,theta1,...",
        "node_w_m": w.tolist(),
        "node_theta_rad": theta.tolist(),
        "root_force_n": float(reaction[0] * beam.tip_force_n),
        "root_moment_nm": float(reaction[1] * beam.tip_force_n * beam.length_m),
        "root_stress_pa": float(stress),
        "tip_deflection_m": float(w[-1]),
        "static_residual": normalized_residual(kf, u[2:], force[2:]),
        "matrices_symmetric_positive_definite_after_constraints": True,
        "mass_kg": float(beam.density_kg_m3 * area * beam.length_m),
        "modes": modes,
    }
    return result
