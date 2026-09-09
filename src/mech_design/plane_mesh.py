"""Deterministic straight-sided meshes; outer boundaries stay exactly fixed."""

import math

import numpy as np


def mesh(nx: int, ny: int, family: str, depth_ratio: float, distortion: float = 0) -> dict:
    nodes = []
    for j in range(ny + 1):
        for i in range(nx + 1):
            x, y = i / nx, depth_ratio * (j / ny - 0.5)
            if 0 < i < nx and 0 < j < ny:
                x += distortion / nx * math.sin(1.7 * i + 0.6 * j)
                y += distortion * depth_ratio / ny * math.cos(0.9 * i - 1.2 * j)
            nodes.append([x, y])
    cells, boundary = [], []
    mids = {}

    def midpoint(a: int, b: int) -> int:
        key = tuple(sorted((a, b)))
        if key not in mids:
            mids[key] = len(nodes)
            nodes.append(((np.array(nodes[a]) + nodes[b]) / 2).tolist())
        return mids[key]

    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            corners = [a, a + 1, a + nx + 2, a + nx + 1]
            polygons = [corners]
            if family.startswith("T"):
                polygons = [
                    [corners[0], corners[1], corners[2]],
                    [corners[0], corners[2], corners[3]],
                ]
            for polygon in polygons:
                cell = list(polygon)
                edges = list(zip(polygon, polygon[1:] + polygon[:1], strict=True))
                quadratic = family in {"T6", "Q9"}
                if quadratic:
                    cell += [midpoint(a, b) for a, b in edges]
                if family == "Q9":
                    cell.append(len(nodes))
                    nodes.append(np.mean([nodes[a] for a in polygon], axis=0).tolist())
                cells.append(cell)
                for a, b in edges:
                    if nodes[a][0] == nodes[b][0] == 1:
                        boundary.append([a, b, midpoint(a, b)] if quadratic else [a, b])
    return {"nodes": np.array(nodes), "cells": cells, "right_edges": boundary}


def boundary_load(nodes: np.ndarray, edges: list, depth_ratio: float) -> np.ndarray:
    """Dimensionless load f/(M/L); linear traction px=-12*y/h^3."""
    f = np.zeros(2 * len(nodes))
    gauss, weights = np.polynomial.legendre.leggauss(3)
    for edge in edges:
        xy = nodes[edge]
        jac = np.linalg.norm(xy[1] - xy[0]) / 2
        for r, weight in zip(gauss, weights, strict=True):
            n = (
                np.array([(1 - r) / 2, (1 + r) / 2])
                if len(edge) == 2
                else np.array([r * (r - 1) / 2, r * (r + 1) / 2, 1 - r * r])
            )
            y = float(n @ xy[:, 1])
            f[2 * np.array(edge)] += n * (-12 * y / depth_ratio**3) * jac * weight
    return f
