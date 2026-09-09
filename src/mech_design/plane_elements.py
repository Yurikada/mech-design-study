"""Small-strain displacement elements. Derivatives use engineering shear strain."""

import numpy as np
from numpy.polynomial.legendre import leggauss

FAMILIES = {"T3", "T6", "Q4", "Q9"}
Q_NODES = [(-1, -1), (1, -1), (1, 1), (-1, 1), (0, -1), (1, 0), (0, 1), (-1, 0), (0, 0)]


def shape(family: str, r: float, s: float) -> tuple[np.ndarray, np.ndarray]:
    if family not in FAMILIES:
        raise ValueError("Unsupported plane element")
    if family.startswith("T"):
        bary = np.array([1 - r - s, r, s])
        dl = np.array([[-1.0, -1.0], [1.0, 0.0], [0.0, 1.0]])
        if family == "T3":
            return bary, dl
        n = list(bary * (2 * bary - 1))
        dn = list((4 * bary - 1)[:, None] * dl)
        for a, b in [(0, 1), (1, 2), (2, 0)]:
            n.append(4 * bary[a] * bary[b])
            dn.append(4 * (dl[a] * bary[b] + bary[a] * dl[b]))
        return np.array(n), np.array(dn)
    if family == "Q4":
        corners = np.array(Q_NODES[:4])
        a, b = corners.T
        return (1 + a * r) * (1 + b * s) / 4, np.column_stack(
            [a * (1 + b * s), b * (1 + a * r)]
        ) / 4

    def lagrange(t: float) -> tuple[dict, dict]:
        return {-1: t * (t - 1) / 2, 0: 1 - t * t, 1: t * (t + 1) / 2}, {
            -1: t - 0.5,
            0: -2 * t,
            1: t + 0.5,
        }

    a, da = lagrange(r)
    b, db = lagrange(s)
    return np.array([a[i] * b[j] for i, j in Q_NODES]), np.array(
        [[da[i] * b[j], a[i] * db[j]] for i, j in Q_NODES]
    )


def quadrature(family: str, integration: str = "full") -> list[tuple[float, float, float]]:
    if family not in FAMILIES or integration not in {"full", "high", "reduced"}:
        raise ValueError("Unsupported integration")
    if integration == "reduced" and family != "Q4":
        raise ValueError("Reduced integration is only supported for Q4")
    if family.startswith("T") and integration == "full":
        if family == "T3":
            return [(1 / 3, 1 / 3, 0.5)]
        return [(1 / 6, 1 / 6, 1 / 6), (2 / 3, 1 / 6, 1 / 6), (1 / 6, 2 / 3, 1 / 6)]
    order = (
        5
        if integration == "high"
        else 1
        if integration == "reduced"
        else 2
        if family == "Q4"
        else 3
    )
    x, w = leggauss(order)
    if family.startswith("T"):
        # Duffy transform of a tensor Gauss rule; independent of the three-point rule.
        return [
            ((r + 1) / 2, (1 - r) * (s + 1) / 4, wr * ws * (1 - r) / 8)
            for r, wr in zip(x, w, strict=True)
            for s, ws in zip(x, w, strict=True)
        ]
    return [(r, s, wr * ws) for r, wr in zip(x, w, strict=True) for s, ws in zip(x, w, strict=True)]


def kinematics(family: str, xy: np.ndarray, r: float, s: float) -> tuple:
    n, dn = shape(family, r, s)
    jac = xy.T @ dn
    determinant = float(np.linalg.det(jac))
    if not np.isfinite(determinant) or determinant <= 0:
        raise ValueError("negative_or_zero_jacobian")
    condition = float(np.linalg.cond(jac))
    if not np.isfinite(condition) or condition > 1e6:
        raise ValueError("ill_conditioned_jacobian")
    grad = dn @ np.linalg.inv(jac)
    b = np.zeros((3, 2 * len(n)))
    b[0, ::2] = grad[:, 0]
    b[1, 1::2] = grad[:, 1]
    b[2, ::2] = grad[:, 1]
    b[2, 1::2] = grad[:, 0]
    return n, b, determinant, condition


def validation_points(family: str) -> list[tuple[float, float]]:
    if family.startswith("T"):
        return [(0, 0), (1, 0), (0, 1), (0.5, 0), (0.5, 0.5), (0, 0.5), (1 / 3, 1 / 3)]
    return [(r, s) for r in [-1, 0, 1] for s in [-1, 0, 1]]


def stiffness(family: str, xy: np.ndarray, integration: str) -> tuple:
    # E and out-of-plane thickness factor out; this benchmark requires nu=0.
    d = np.diag([1.0, 1.0, 0.5])
    k = np.zeros((2 * len(xy), 2 * len(xy)))
    determinants, conditions = [], []
    for r, s in validation_points(family):
        _, _, det, cond = kinematics(family, xy, r, s)
        determinants.append(det)
        conditions.append(cond)
    for r, s, weight in quadrature(family, integration):
        _, b, det, cond = kinematics(family, xy, r, s)
        k += (b.T @ d @ b) * det * weight
        determinants.append(det)
        conditions.append(cond)
    return k, min(determinants), max(conditions)
