"""Dimensionless manufactured solution; x=X/L, y=Y/L, h=H/L, nu=0.

Displacement scale M0/(E*s*L); force scale M0/L. Reference fields are
polynomials in physical coordinates, also on distorted isoparametric meshes.
"""

import numpy as np

from mech_design.plane_elements import kinematics, quadrature

D_BAR = np.diag([1.0, 1.0, 0.5])
INTEGRATION = "high"  # 5x5 Gauss: tensor product or triangle Duffy transform


def reference_fields(x: float, y: float, h: float) -> tuple:
    c = 12 / h**3
    return (
        c * np.array([-y * (x - x**2 / 2), x**2 / 2 - x**3 / 6]),
        c * np.array([-y * (1 - x), 0.0, 0.0]),
    )


def reference_norms(h: float) -> tuple:
    """Exact integrals of |q*|^2 and eps* D_bar eps* on the rectangle."""
    return 144 / h**6 * (h**3 / 90 + 11 * h / 420), 4 / h**3


def body_load(family: str, xy: np.ndarray, h: float) -> np.ndarray:
    """Consistent area load; multiplying by M0/L yields nodal forces [N]."""
    f = np.zeros((len(xy), 2))
    for r, s, weight in quadrature(family, INTEGRATION):
        n, _, det, _ = kinematics(family, xy, r, s)
        y = (n @ xy)[1]
        f[:, 0] += n * (-12 * y / h**3) * det * weight
    return f.ravel()


def error_integrals(family: str, xy: np.ndarray, q: np.ndarray, h: float) -> np.ndarray:
    """L2 error squared, energy error squared, and integrated FEM energy (twice)."""
    integrals = np.zeros(3)
    for r, s, weight in quadrature(family, INTEGRATION):
        n, b, det, _ = kinematics(family, xy, r, s)
        exact_q, exact_eps = reference_fields(*(n @ xy), h)
        eps = b @ q
        dq, de = n @ q.reshape(-1, 2) - exact_q, eps - exact_eps
        integrals += np.array([dq @ dq, de @ D_BAR @ de, eps @ D_BAR @ eps]) * det * weight
    return integrals
