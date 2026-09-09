import copy
import json
from pathlib import Path

import numpy as np
import pytest

from mech_design.cli import main
from mech_design.mms_model import (
    D_BAR,
    body_load,
    error_integrals,
    reference_fields,
    reference_norms,
)
from mech_design.mms_solver import solve_mms
from mech_design.mms_study import (
    load_study,
    observed_rate,
    parse_study,
    provenance,
    refinement_pairs,
    replay_study,
    run_study,
)
from mech_design.plane_elements import kinematics, quadrature
from mech_design.plane_mesh import mesh

ROOT = Path(__file__).resolve().parents[1]


def case(family="Q9", nx=4, ny=1, distortion=0, integration="full"):
    raw = load_study(ROOT / "cases/plane_mms.toml")
    raw["repetitions"] = 1
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
    return raw


def test_exact_fields_equilibrium_and_boundary():
    h, x, y, step = 0.1, 0.37, 0.021, 1e-6
    du = (reference_fields(x + step, y, h)[0] - reference_fields(x - step, y, h)[0]) / (2 * step)
    dv = (reference_fields(x, y + step, h)[0] - reference_fields(x, y - step, h)[0]) / (2 * step)
    np.testing.assert_allclose(
        [du[0], dv[1], du[1] + dv[0]], reference_fields(x, y, h)[1], atol=1e-6
    )
    stress_gradient = (
        D_BAR @ reference_fields(x + step, y, h)[1] - D_BAR @ reference_fields(x - step, y, h)[1]
    ) / (2 * step)
    assert stress_gradient[0] - 12 * y / h**3 == pytest.approx(0, abs=1e-6)
    np.testing.assert_allclose(reference_fields(0, y, h)[0], 0)
    np.testing.assert_allclose(reference_fields(1, y, h)[1], 0)
    assert reference_fields(x, h / 2, h)[1][1:].tolist() == [0, 0]


@pytest.mark.parametrize("family", ["T3", "T6", "Q4", "Q9"])
def test_reference_norms_and_body_resultants(family):
    h = 0.1
    grid = mesh(2, 2, family, h, 0.2)
    nodes = grid["nodes"]
    force = np.zeros_like(nodes)
    integrated = np.zeros(2)
    for cell in grid["cells"]:
        xy = nodes[cell]
        force[cell] += body_load(family, xy, h).reshape(-1, 2)
        for r, s, w in quadrature(family, "high"):
            n, b, det, _ = kinematics(family, xy, r, s)
            q, eps = reference_fields(*(n @ xy), h)
            integrated += np.array([q @ q, eps @ D_BAR @ eps]) * det * w
    np.testing.assert_allclose(integrated, reference_norms(h), rtol=1e-12)
    np.testing.assert_allclose(force.sum(axis=0), 0, atol=1e-12)
    assert np.sum(nodes[:, 0] * force[:, 1] - nodes[:, 1] * force[:, 0]) == pytest.approx(1)


def test_t6_body_force_quadratic_virtual_work_needs_cubic_exactness():
    # A triangle on x>=0,y>=0 with vertices (0,0),(1,0),(0,h).
    # Virtual u=x*y is exactly T6 representable. Integral x*y^2 dA=h^3/60,
    # so integral u*bx dA = -12/h^3 * h^3/60 = -1/5.
    h = 0.1
    xy = np.array([[0, 0], [1, 0], [0, h], [0.5, 0], [0.5, h / 2], [0, h / 2]])
    virtual = np.column_stack([xy[:, 0] * xy[:, 1], np.zeros(6)]).ravel()
    assert virtual @ body_load("T6", xy, h) == pytest.approx(-0.2, abs=1e-14)
    low = np.zeros(12)
    for r, s, w in quadrature("T6", "full"):
        n, _, det, _ = kinematics("T6", xy, r, s)
        low[::2] += n * (-12 * (n @ xy)[1] / h**3) * det * w
    assert abs(virtual @ low + 0.2) > 1e-4


@pytest.mark.parametrize("family", ["T6", "Q9"])
def test_interpolated_exact_nodes_still_have_nonzero_field_error(family):
    h = 0.1
    grid = mesh(1, 1, family, h)
    nodes = grid["nodes"]
    q = np.array([reference_fields(x, y, h)[0] for x, y in nodes])
    errors = sum(
        (error_integrals(family, nodes[c], q[c].ravel(), h) for c in grid["cells"]),
        start=np.zeros(3),
    )
    assert errors[0] > 0
    assert errors[1] > 0
    # For zero FE displacement, both relative field errors must equal one.
    zero = sum(
        (error_integrals(family, nodes[c], np.zeros(2 * len(c)), h) for c in grid["cells"]),
        start=np.zeros(3),
    )
    np.testing.assert_allclose(zero[:2], reference_norms(h), rtol=1e-12)


@pytest.mark.parametrize("family", ["T3", "Q4", "T6", "Q9"])
def test_refinement_balance_and_energy_identity(family):
    raw = case(family)
    rows = []
    for nx, ny in [(4, 1), (8, 2), (16, 4)]:
        design = {**raw["designs"][0], "id": f"n{nx}", "nx": nx, "ny": ny}
        row = solve_mms(raw["model"], design)
        assert row["status"] == "computed"
        assert row["accuracy_status"] == "not_evaluated"
        assert row["reference"]["tip_deflection_m"] == pytest.approx(0.0000571428571428571)
        assert row["reference"]["energy_j"] == pytest.approx(2.85714285714286e-5)
        assert row["root_moment_nm"] == pytest.approx(-0.1, abs=1e-9)
        assert row["body_moment_nm"] == pytest.approx(0.1)
        assert row["energy_j"] == pytest.approx(row["assembled_energy_j"], rel=1e-9)
        # Galerkin orthogonality with exact integration: e_E^2 = (U*-Uh)/U*.
        assert row["errors"]["strain_energy_norm"] ** 2 == pytest.approx(
            1 - row["energy_j"] / row["reference"]["energy_j"], abs=1e-9
        )
        rows.append({**row, "id": design["id"], "settings": design})
    for metric in ("displacement_l2", "strain_energy_norm"):
        assert (
            rows[0]["errors"][metric] > rows[1]["errors"][metric] > rows[2]["errors"][metric] > 1e-8
        )
    assert len(refinement_pairs(rows)) == 2


def test_physical_scaling_and_high_stiffness():
    raw = case("Q9", 4, 2, distortion=0.2)
    row = solve_mms(raw["model"], raw["designs"][0])
    for field, factor, displacement_factor, energy_factor in [
        ("root_moment_scale_nm", 2, 2, 4),
        ("young_modulus_pa", 2, 0.5, 0.5),
        ("thickness_m", 2, 0.5, 0.5),
    ]:
        m = {**raw["model"], field: raw["model"][field] * factor}
        scaled = solve_mms(m, raw["designs"][0])
        assert scaled["tip_deflection_m"] == pytest.approx(
            row["tip_deflection_m"] * displacement_factor
        )
        assert scaled["energy_j"] == pytest.approx(row["energy_j"] * energy_factor)
        assert scaled["errors"]["strain_energy_norm"] == pytest.approx(
            row["errors"]["strain_energy_norm"]
        )
    high = solve_mms(raw["model"], {**raw["designs"][0], "integration": "high"})
    assert high["status"] == "computed"


def test_failed_geometry_and_hourglass_keep_valid_rows():
    raw = case()
    raw["designs"] += [
        {**raw["designs"][0], "id": "inverted", "fault": "reverse_first_element"},
        {**raw["designs"][0], "id": "hourglass", "family": "Q4", "integration": "reduced"},
    ]
    report = run_study(raw)
    assert report["status"] == "error"
    assert report["rows"][0]["status"] == "computed"
    for row in report["rows"][1:]:
        assert row["status"] == "error"
        assert row["results"] is None
        assert "errors" not in row
    assert "jacobian" in report["rows"][1]["error"]
    assert "zero_energy" in report["rows"][2]["error"]


def test_rate_filters_and_roundoff():
    assert observed_rate(0.08, 0.02)["value"] == pytest.approx(2)
    for fine in [0, 1e-13, float("nan")]:
        assert observed_rate(0.08, fine)["value"] is None
    assert observed_rate(0.02, 0.08)["value"] == -2
    raw = case()
    base = {
        "id": "coarse",
        "settings": raw["designs"][0],
        "status": "computed",
        "errors": {"displacement_l2": 0.08, "strain_energy_norm": 0.08},
    }
    fine = {**copy.deepcopy(base), "id": "fine"}
    fine["settings"].update(nx=8, ny=2)
    assert len(refinement_pairs([base, fine])) == 1
    for change in [{"ny": 1}, {"family": "T6"}, {"integration": "high"}, {"distortion": 0.1}]:
        changed = copy.deepcopy(fine)
        changed["settings"].update(change)
        assert refinement_pairs([base, changed]) == []
    fine["status"] = "error"
    del fine["errors"]
    assert refinement_pairs([base, fine])[0]["observed_orders"]["displacement_l2"]["value"] is None


@pytest.mark.parametrize("version", [True, 1.0, "1", None, 2])
def test_strict_schema(version):
    raw = case()
    raw["schema_version"] = version
    with pytest.raises(ValueError):
        parse_study(raw)


@pytest.mark.parametrize(
    "field,value",
    [
        ("poisson_ratio", 0.3),
        ("root_moment_scale_nm", 0),
        ("root_moment_scale_nm", float("nan")),
        ("length_m", True),
    ],
)
def test_invalid_model(field, value):
    raw = case()
    raw["model"][field] = value
    with pytest.raises(ValueError):
        parse_study(raw)


def test_replay_recomputes_and_rejects_legacy(tmp_path):
    report = run_study(case())
    report["rows"][0]["tip_deflection_m"] = 999
    target = tmp_path / "saved.json"
    target.write_text(json.dumps(report), encoding="utf-8")
    assert replay_study(target)["rows"][0]["tip_deflection_m"] != 999
    report["provenance"]["code_sha256"] = "tampered"
    target.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="matching MMS"):
        replay_study(target)
    with pytest.raises(ValueError):
        replay_study(ROOT / "docs/learning/assets/plane-results.json")
    raw = case()
    raw["model"]["moment_nm"] = raw["model"].pop("root_moment_scale_nm")
    with pytest.raises(ValueError):
        parse_study(raw)


def test_cli_snapshot_no_overwrite_and_failure(tmp_path, capsys, monkeypatch):
    import mech_design.mms_cli as cli

    report = run_study(case())
    monkeypatch.setattr(cli, "run_study", lambda raw: report)
    dest = tmp_path / "result.json"
    assert main(["mms", str(ROOT / "cases/plane_mms.toml"), "--output", str(dest)]) == 0
    assert "not_evaluated" in capsys.readouterr().out
    original = dest.read_bytes()
    assert main(["mms", str(ROOT / "cases/plane_mms.toml"), "--output", str(dest)]) == 1
    assert dest.read_bytes() == original
    report["status"] = "fail"
    assert main(["mms", str(ROOT / "cases/plane_mms.toml")]) == 2
    report["status"] = "error"
    assert main(["mms", str(ROOT / "cases/plane_mms.toml")]) == 1


def test_published_snapshot():
    snapshot = ROOT / "docs/learning/assets/mms-results.json"
    saved = json.loads(snapshot.read_text(encoding="utf-8"))
    assert saved["input"] == load_study(ROOT / "cases/plane_mms.toml")
    assert saved["provenance"] == provenance()
