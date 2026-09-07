import copy
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from mech_design.fem_beam import assemble, element_matrices, interpolate, solve_beam
from mech_design.fem_study import load_fem, replay_fem, run_fem, validate

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "cases/cantilever_fem.toml"


@pytest.mark.parametrize("h", [1.0, 0.25])
def test_element_matrices_against_independent_gauss_integration(h):
    # Five-point Gauss integrates the sixth-degree mass integrand exactly.
    points, weights = np.polynomial.legendre.leggauss(5)
    k = np.zeros((4, 4))
    m = np.zeros_like(k)
    for point, weight in zip(points, weights, strict=True):
        s = (point + 1) / 2
        shape = np.array(
            [
                1 - 3 * s * s + 2 * s**3,
                h * (s - 2 * s * s + s**3),
                3 * s * s - 2 * s**3,
                h * (-s * s + s**3),
            ]
        )
        second = np.array(
            [(-6 + 12 * s) / h**2, (-4 + 6 * s) / h, (6 - 12 * s) / h**2, (-2 + 6 * s) / h]
        )
        k += weight * h / 2 * np.outer(second, second)
        m += weight * h / 2 * np.outer(shape, shape)
    ke, me = element_matrices(h)
    np.testing.assert_allclose(ke, k, rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(me, m, rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(ke @ [1, 0, 1, 0], 0, atol=1e-12)
    np.testing.assert_allclose(ke @ [0, 1, h, 1], 0, atol=1e-12)


def test_assembly_shares_nodes_and_preserves_total_mass():
    nodes = np.array([0, 0.25, 1.0])
    k, m = assemble(nodes)
    assert k.shape == (6, 6)
    rigid = np.array([1, 0, 1, 0, 1, 0])
    assert rigid @ m @ rigid == pytest.approx(1)
    np.testing.assert_allclose(k @ rigid, 0, atol=1e-12)


@pytest.mark.parametrize("n", [1, 2, 4, 8, 16])
def test_static_solution_reactions_and_curvature(case, n):
    r = solve_beam(case.beam, n)
    b = case.beam
    ei = b.young_modulus_pa * b.width_m * b.thickness_m**3 / 12
    assert r["tip_deflection_m"] == pytest.approx(
        b.tip_force_n * b.length_m**3 / (3 * ei), rel=1e-8
    )
    assert r["root_force_n"] == pytest.approx(-b.tip_force_n, rel=1e-8)
    assert r["root_moment_nm"] == pytest.approx(-b.tip_force_n * b.length_m, rel=1e-8)
    assert r["root_stress_pa"] == pytest.approx(
        6 * b.tip_force_n * b.length_m / (b.width_m * b.thickness_m**2)
    )
    z = np.empty(2 * (n + 1))
    z[::2] = np.array(r["node_w_m"]) / b.length_m
    z[1::2] = r["node_theta_rad"]
    xi = np.linspace(0, 1, 37)
    expected = b.tip_force_n * b.length_m**2 / (6 * ei) * xi**2 * (3 - xi)
    np.testing.assert_allclose(interpolate(np.linspace(0, 1, n + 1), z, xi), expected, atol=1e-12)


def test_modes_converge_and_keep_insufficient_dofs_explicit():
    report = run_fem(load_fem(STUDY))
    assert report["verification_status"] == "pass"
    assert report["meshes"][0]["modes"][2]["status"] == "not_evaluated"
    errors = [r["modes"][0]["relative_error"] for r in report["meshes"]]
    assert all(a > b for a, b in zip(errors, errors[1:], strict=False))
    assert errors[0] > 0.004
    assert errors[-1] < 2e-7
    assert report["design_evaluation"]["overall_status"] == "incomplete"
    assert (
        sum(r["status"] == "not_evaluated" for r in report["design_evaluation"]["evaluations"]) == 9
    )
    assert all(c["status"] == "pass" for c in report["verification_checks"])


def test_modal_boundary_conditions_and_mass_orthogonality(case):
    r = solve_beam(case.beam, 8)
    _, mass = assemble(np.linspace(0, 1, 9))
    vectors = []
    for mode in r["modes"]:
        assert mode["node_w_normalized"][0] == mode["node_ltheta_normalized"][0] == 0
        assert max(abs(v) for v in mode["shape_w_normalized"]) == pytest.approx(1)
        v = np.empty(18)
        v[::2], v[1::2] = mode["node_w_normalized"], mode["node_ltheta_normalized"]
        vectors.append(v / np.sqrt(v @ mass @ v))
    v = np.array(vectors).T
    np.testing.assert_allclose(v.T @ mass @ v, np.eye(3), atol=1e-10)


def test_density_stiffness_and_static_load_scaling(case):
    base = solve_beam(case.beam, 4)
    for field, factor, ratio in [
        ("density_kg_m3", 2, 1 / np.sqrt(2)),
        ("young_modulus_pa", 2, np.sqrt(2)),
        ("tip_force_n", 2, 1),
    ]:
        beam = replace(case.beam, **{field: getattr(case.beam, field) * factor})
        r = solve_beam(beam, 4)
        assert r["modes"][0]["frequency_hz"] / base["modes"][0]["frequency_hz"] == pytest.approx(
            ratio
        )


@pytest.mark.parametrize("nodes", [[0, 0, 1], [0, 1, 0.5], [0, float("nan"), 1], [0, 0.5]])
def test_degenerate_mesh_rejected(nodes):
    with pytest.raises(ValueError, match="Mesh"):
        assemble(nodes)


@pytest.mark.parametrize(
    "field,value",
    [
        ("elements", [0]),
        ("elements", [True]),
        ("elements", [1, 3]),
        ("elements", [128]),
        ("mode_count", 0),
        ("element_type", "linear"),
        ("mass_matrix", "lumped"),
        ("boundary", "free_free"),
    ],
)
def test_unsupported_settings_rejected(field, value):
    snapshot = load_fem(STUDY)
    snapshot["settings"][field] = value
    with pytest.raises(ValueError):
        validate(snapshot)


def test_solver_failure_is_error_not_success(monkeypatch):
    import mech_design.fem_beam as module

    def broken(nodes):
        n = 2 * len(nodes)
        return np.zeros((n, n)), np.eye(n)

    monkeypatch.setattr(module, "assemble", broken)
    report = run_fem(load_fem(STUDY))
    assert report["verification_status"] == "error"
    assert report["design_evaluation"] is None
    assert all(r["status"] == "error" for r in report["meshes"])


def test_coarse_only_study_cannot_pass():
    snapshot = load_fem(STUDY)
    snapshot["settings"]["elements"] = [1]
    assert run_fem(snapshot)["verification_status"] != "pass"


def test_replay_uses_inputs_and_rejects_drift():
    report = run_fem(load_fem(STUDY))
    modified = copy.deepcopy(report)
    modified["meshes"] = []
    assert replay_fem(modified) == report
    modified["input"]["case"]["beam"]["density_kg_m3"] *= 2
    with pytest.raises(ValueError, match="digest"):
        replay_fem(modified)
    report["provenance"]["scipy"] = "different"
    with pytest.raises(ValueError, match="versions"):
        replay_fem(report)


def test_published_results_match_current_inputs_and_solver():
    saved = json.loads((ROOT / "docs/learning/assets/fem-results.json").read_text(encoding="utf-8"))
    snapshot = load_fem(STUDY)
    assert saved["input"] == snapshot
    current = replay_fem(saved)
    assert current["verification_status"] == saved["verification_status"] == "pass"
    for a, b in zip(current["meshes"], saved["meshes"], strict=True):
        for ma, mb in zip(a["modes"], b["modes"], strict=True):
            assert ma["status"] == mb["status"]
            if ma["status"] == "computed":
                assert ma["frequency_hz"] == pytest.approx(mb["frequency_hz"], rel=1e-8)
                np.testing.assert_allclose(
                    ma["shape_w_normalized"], mb["shape_w_normalized"], atol=1e-7
                )


def test_cli_outside_repo_save_replay_and_exit_codes(tmp_path):
    output = tmp_path / "fem.json"

    def invoke(*args):
        return subprocess.run(
            [sys.executable, "-m", "mech_design", "fem", *map(str, args)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )

    result = invoke(STUDY, "--output", output, "--json")
    assert result.returncode == 0, result.stderr
    repeated = invoke("--replay", output, "--json", "--require-complete")
    assert repeated.returncode == 3, repeated.stderr
    assert json.loads(result.stdout) == json.loads(repeated.stdout)
    assert invoke(STUDY, "--output", output).returncode == 1
    assert invoke(tmp_path / "missing.toml").returncode == 1
