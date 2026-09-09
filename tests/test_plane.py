import copy
import json
from pathlib import Path

import numpy as np
import pytest

from mech_design.cli import main
from mech_design.plane_elements import Q_NODES, kinematics, quadrature, shape, stiffness
from mech_design.plane_mesh import boundary_load, mesh
from mech_design.plane_solver import solve_plane
from mech_design.plane_study import load_study, parse_study, provenance, replay_study, run_study

ROOT = Path(__file__).resolve().parents[1]


def test_published_plane_snapshot_matches_current_input_and_solver():
    saved = json.loads(
        (ROOT / "docs/learning/assets/plane-results.json").read_text(encoding="utf-8")
    )
    assert saved["input"] == load_study(ROOT / "cases/plane_bending.toml")
    assert saved["provenance"] == provenance()


def case(family="T6", nx=4, ny=1, distortion=0, integration="full"):
    raw = load_study(ROOT / "cases/plane_bending.toml")
    raw["designs"] = [
        {
            "id": "test",
            "family": family,
            "nx": nx,
            "ny": ny,
            "distortion": distortion,
            "integration": integration,
        }
    ]
    raw["repetitions"] = 1
    return raw


@pytest.mark.parametrize("family", ["T3", "T6", "Q4", "Q9"])
def test_interpolation_and_derivatives(family):
    natural = {
        "T3": [(0, 0), (1, 0), (0, 1)],
        "T6": [(0, 0), (1, 0), (0, 1), (0.5, 0), (0.5, 0.5), (0, 0.5)],
        "Q4": Q_NODES[:4],
        "Q9": Q_NODES,
    }[family]
    for i, point in enumerate(natural):
        np.testing.assert_allclose(shape(family, *point)[0], np.eye(len(natural))[i], atol=1e-14)
    n, dn = shape(family, 0.2, 0.3)
    assert sum(n) == pytest.approx(1)
    np.testing.assert_allclose(dn.sum(axis=0), 0, atol=1e-14)
    eps = 1e-6
    for axis in range(2):
        plus, minus = np.array([0.2, 0.3]), np.array([0.2, 0.3])
        plus[axis] += eps
        minus[axis] -= eps
        numerical = (shape(family, *plus)[0] - shape(family, *minus)[0]) / (2 * eps)
        np.testing.assert_allclose(dn[:, axis], numerical, atol=1e-9)
    for rule in ["full", "high"]:
        assert sum(w for _, _, w in quadrature(family, rule)) == pytest.approx(
            0.5 if family.startswith("T") else 4.0
        )


@pytest.mark.parametrize("family", ["T3", "T6", "Q4", "Q9"])
def test_rigid_motion_constant_strain_and_mesh(family):
    grid = mesh(8, 2, family, 0.1, 0.2)
    expected_nodes = 85 if family in {"T6", "Q9"} else 27
    assert len(grid["nodes"]) == expected_nodes
    assert len(grid["cells"]) == (32 if family.startswith("T") else 16)
    baseline = mesh(8, 2, family, 0.1)
    boundary = (
        (baseline["nodes"][:, 0] == 0)
        | (baseline["nodes"][:, 0] == 1)
        | (abs(baseline["nodes"][:, 1]) == 0.05)
    )
    np.testing.assert_allclose(grid["nodes"][boundary], baseline["nodes"][boundary], atol=1e-15)
    for cell in grid["cells"]:
        xy = grid["nodes"][cell]
        k, _, _ = stiffness(family, xy, "full")
        rotation = np.column_stack([-xy[:, 1], xy[:, 0]]).ravel()
        for rigid in [rotation, np.tile([1.0, 0.0], len(cell)), np.tile([0.0, 1.0], len(cell))]:
            np.testing.assert_allclose(k @ rigid, 0, atol=1e-12)
        displacement = np.column_stack(
            [2 * xy[:, 0] + 3 * xy[:, 1], 4 * xy[:, 0] + 5 * xy[:, 1]]
        ).ravel()
        for r, s, _ in quadrature(family):
            _, b, _, _ = kinematics(family, xy, r, s)
            np.testing.assert_allclose(b @ displacement, [2, 5, 7], atol=1e-11)


def test_cst_closed_form_stiffness():
    xy = np.array([[0.0, 0.0], [2.0, 0.0], [0.0, 1.0]])
    b = np.array([[-0.5, 0, 0.5, 0, 0, 0], [0, -1, 0, 0, 0, 1], [-1, -0.5, 0, 0.5, 1, 0]])
    expected = b.T @ np.diag([1.0, 1.0, 0.5]) @ b  # area=1
    actual, _, _ = stiffness("T3", xy, "full")
    np.testing.assert_allclose(actual, expected, atol=1e-14)


@pytest.mark.parametrize("family", ["T3", "T6", "Q4", "Q9"])
def test_assembled_constant_strain_patch(family):
    grid = mesh(3, 2, family, 0.3, 0.2)
    xy = grid["nodes"]
    k = np.zeros((2 * len(xy), 2 * len(xy)))
    for cell in grid["cells"]:
        local, _, _ = stiffness(family, xy[cell], "full")
        dofs = np.array([[2 * i, 2 * i + 1] for i in cell]).ravel()
        k[np.ix_(dofs, dofs)] += local
    q = np.column_stack([2 * xy[:, 0] + 3 * xy[:, 1], 4 * xy[:, 0] + 5 * xy[:, 1]]).ravel()
    interior = np.repeat((xy[:, 0] > 0) & (xy[:, 0] < 1) & (abs(xy[:, 1]) < 0.15 - 1e-12), 2)
    np.testing.assert_allclose((k @ q)[interior], 0, atol=1e-11)


def test_quadratic_boundary_work_on_half_edge():
    h = 0.1
    xy = np.array([[1, 0], [1, h / 2], [1, h / 4]])
    f = boundary_load(xy, [[0, 1, 2]], h)
    # Independent polynomial integral: integral_0^(h/2) -12*y^3/h^3 dy.
    assert f[::2] @ xy[:, 1] ** 2 == pytest.approx(-3 * h / 16)


@pytest.mark.parametrize("family", ["T3", "T6", "Q4", "Q9"])
def test_load_balance_and_quadratic_virtual_work(family):
    grid = mesh(4, 2, family, 0.1)
    xy = grid["nodes"]
    f = boundary_load(xy, grid["right_edges"], 0.1).reshape(-1, 2)
    np.testing.assert_allclose(f.sum(axis=0), 0, atol=1e-12)
    assert np.sum(-xy[:, 1] * f[:, 0]) == pytest.approx(1.0)
    if family in {"T6", "Q9"}:
        # Exact work against u=y+y^2: integral[-12*y*(y+y^2)/h^3]dy = -1.
        assert np.sum(f[:, 0] * (xy[:, 1] + xy[:, 1] ** 2)) == pytest.approx(-1.0)


@pytest.mark.parametrize("family", ["T6", "Q9"])
@pytest.mark.parametrize("distortion", [0, 0.2])
def test_quadratic_pure_bending(family, distortion):
    raw = case(family, 8, 2, distortion)
    row = solve_plane(raw["model"], raw["designs"][0])
    assert row["status"] == "pass"
    assert row["tip_deflection_m"] == pytest.approx(0.0000857142857142857, rel=1e-8)
    assert row["energy_j"] == pytest.approx(0.0000857142857142857, rel=1e-8)
    assert row["root_moment_nm"] == pytest.approx(-0.1, abs=1e-9)
    xy = np.array(row["mesh"]["nodes_m"])
    curvature = 0.01714285714285714
    exact = np.column_stack([-curvature * xy[:, 0] * xy[:, 1], curvature * xy[:, 0] ** 2 / 2])
    np.testing.assert_allclose(row["displacements_m"], exact, atol=1e-12)
    assert row["stress_probe"]["element_sided_values"][0]["stress_pa"][0] == pytest.approx(
        -6e6, rel=1e-8
    )


@pytest.mark.parametrize("family", ["T3", "Q4"])
def test_linear_refinement(family):
    errors = []
    for nx, ny in [(4, 1), (8, 2), (16, 4)]:
        raw = case(family, nx, ny)
        row = solve_plane(raw["model"], raw["designs"][0])
        assert row["status"] == "fail"
        errors.append(row["errors"]["tip"])
    assert errors[0] > errors[1] > errors[2] > 0.001


def test_diagnostics_are_errors_not_accuracy_failures():
    report = run_study(load_study(ROOT / "cases/plane_diagnostics.toml"))
    assert report["status"] == "error"
    assert report["qualified_ids"] == report["computed_tip_accuracy_order"] == []
    assert "zero_energy" in report["rows"][0]["error"]
    assert "jacobian" in report["rows"][1]["error"]
    for row in report["rows"]:
        assert row["results"] is None
        assert "tip_deflection_m" not in row


@pytest.mark.parametrize(
    "key,value",
    [("poisson_ratio", 0.3), ("moment_nm", float("nan")), ("length_m", True), ("extra", 1)],
)
def test_invalid_model(key, value):
    raw = case()
    raw["model"][key] = value
    with pytest.raises(ValueError):
        parse_study(raw)


@pytest.mark.parametrize(
    "key,value",
    [
        ("nx", True),
        ("ny", 9),
        ("family", "T9"),
        ("integration", "reduced"),
        ("distortion", float("nan")),
        ("loads", 1),
    ],
)
def test_invalid_design(key, value):
    raw = case()
    raw["designs"][0][key] = value
    with pytest.raises(ValueError):
        parse_study(raw)


def test_replay_recomputes_and_rejects_version(tmp_path):
    report = run_study(case())
    report["rows"][0]["tip_deflection_m"] = -999
    path = tmp_path / "saved.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    replayed = replay_study(path)
    assert replayed["rows"][0]["tip_deflection_m"] > 0
    assert replayed["rows"][0]["timing_s"] != report["rows"][0]["timing_s"]
    report["provenance"]["model_version"] = "wrong"
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="Replay"):
        replay_study(path)


@pytest.mark.parametrize("version", [True, 1.0, "1", None])
def test_replay_rejects_noninteger_schema_version(tmp_path, version):
    report = run_study(case())
    report["schema_version"] = version
    path = tmp_path / "invalid-schema.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="Replay"):
        replay_study(path)


def test_mixed_error_preserves_valid_rows():
    raw = case()
    bad = copy.deepcopy(raw["designs"][0])
    bad.update(id="bad", fault="reverse_first_element")
    raw["designs"].append(bad)
    report = run_study(raw)
    assert report["status"] == "error"
    assert report["qualified_ids"] == report["computed_tip_accuracy_order"] == ["test"]


def test_cli_exit_codes_and_new_file_only(tmp_path, capsys):
    raw = run_study(case())
    snapshot = tmp_path / "input.json"
    snapshot.write_text(json.dumps(raw), encoding="utf-8")
    output = tmp_path / "result.json"
    assert main(["plane", "--replay", str(snapshot), "--output", str(output)]) == 0
    before = output.read_bytes()
    assert main(["plane", "--replay", str(snapshot), "--output", str(output)]) == 1
    assert output.read_bytes() == before
    assert main(["plane", str(ROOT / "cases/plane_diagnostics.toml")]) == 1
    fail = run_study(case("Q4"))
    snapshot.write_text(json.dumps(fail), encoding="utf-8")
    assert main(["plane", "--replay", str(snapshot)]) == 2
    assert "Outside tolerance" in capsys.readouterr().out
