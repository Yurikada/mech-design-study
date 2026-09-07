from dataclasses import replace

import pytest

from mech_design.models import cantilever, tip_temperature


def test_reference_beam_against_hand_calculation(case):
    # I = 6.75e-11 m^4; EI = 4.725 N m^2; M_root = 0.1 N m.
    result = cantilever(case.beam)
    assert result["mass_kg"] == pytest.approx(0.0243)
    assert result["root_stress_pa"] == pytest.approx(2_222_222.222222)
    assert result["tip_deflection_m"] == pytest.approx(0.0000705467372)
    assert result["first_frequency_hz"] == pytest.approx(246.8, rel=0.001)


def test_thickness_scaling_predicts_competing_metrics(case):
    thin = cantilever(case.beam)
    thick = cantilever(replace(case.beam, thickness_m=2 * case.beam.thickness_m))
    assert thick["mass_kg"] == pytest.approx(2 * thin["mass_kg"])
    assert thick["root_stress_pa"] == pytest.approx(thin["root_stress_pa"] / 4)
    assert thick["tip_deflection_m"] == pytest.approx(thin["tip_deflection_m"] / 8)
    assert thick["first_frequency_hz"] == pytest.approx(2 * thin["first_frequency_hz"])


def test_static_force_does_not_become_dynamic_tip_mass(case):
    original = cantilever(case.beam)
    loaded = cantilever(replace(case.beam, tip_force_n=3 * case.beam.tip_force_n))
    assert loaded["root_stress_pa"] == pytest.approx(3 * original["root_stress_pa"])
    assert loaded["first_frequency_hz"] == original["first_frequency_hz"]


def test_thermal_energy_balance(case):
    temperature = tip_temperature(case.beam, case.thermal)
    assert temperature == pytest.approx(304.8033599468)
    gradient = (temperature - case.thermal.base_temperature_k) / case.beam.length_m
    flux = case.beam.thermal_conductivity_w_mk * gradient
    heat = flux * case.beam.width_m * case.beam.thickness_m
    assert heat == pytest.approx(case.thermal.heat_w)
