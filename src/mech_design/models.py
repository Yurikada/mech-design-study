"""Analytical reference models, deliberately separate from acceptance decisions."""

from math import pi, sqrt

from mech_design.case import Beam, Thermal


def cantilever(beam: Beam) -> dict[str, float]:
    """Uniform Euler-Bernoulli beam; static end force, no dynamic tip mass."""
    area = beam.width_m * beam.thickness_m
    inertia = beam.width_m * beam.thickness_m**3 / 12
    rigidity = beam.young_modulus_pa * inertia
    return {
        "mass_kg": beam.density_kg_m3 * area * beam.length_m,
        "root_stress_pa": beam.tip_force_n * beam.length_m * beam.thickness_m / (2 * inertia),
        "tip_deflection_m": beam.tip_force_n * beam.length_m**3 / (3 * rigidity),
        "first_frequency_hz": (1.875104068711961**2 / (2 * pi * beam.length_m**2))
        * sqrt(rigidity / (beam.density_kg_m3 * area)),
    }


def tip_temperature(beam: Beam, thermal: Thermal) -> float:
    """Steady 1D conduction: fixed-temperature root, heated tip, insulated sides."""
    area = beam.width_m * beam.thickness_m
    resistance = beam.length_m / (beam.thermal_conductivity_w_mk * area)
    return thermal.base_temperature_k + thermal.heat_w * resistance
