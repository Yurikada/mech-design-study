"""Versioned, explicit-unit inputs; reject typos and nonphysical scalar inputs."""

import math
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path


def require_positive(instance: object) -> None:
    for field in fields(instance):
        value = getattr(instance, field.name)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{field.name} must be a finite positive number")


@dataclass(frozen=True)
class Beam:
    length_m: float
    width_m: float
    thickness_m: float
    young_modulus_pa: float
    density_kg_m3: float
    thermal_conductivity_w_mk: float
    tip_force_n: float

    def __post_init__(self) -> None:
        require_positive(self)
        if self.length_m / self.thickness_m < 10:
            raise ValueError("Educational beam model requires length/thickness >= 10")


@dataclass(frozen=True)
class Thermal:
    heat_w: float
    base_temperature_k: float

    def __post_init__(self) -> None:
        require_positive(self)


@dataclass(frozen=True)
class Limits:
    max_stress_pa: float
    max_tip_deflection_m: float
    min_first_frequency_hz: float
    max_tip_temperature_k: float

    def __post_init__(self) -> None:
        require_positive(self)


@dataclass(frozen=True)
class Case:
    name: str
    beam: Beam
    thermal: Thermal
    limits: Limits


def load_case(path: Path) -> Case:
    with path.open("rb") as stream:
        raw = tomllib.load(stream)
    expected = {"schema_version", "name", "beam", "thermal", "limits"}
    if raw.keys() != expected:
        raise ValueError(f"Case fields must be exactly {sorted(expected)}")
    if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
        raise ValueError("Only schema_version = 1 is supported")
    if not isinstance(raw["name"], str) or not raw["name"].strip():
        raise ValueError("name must be a nonempty string")
    try:
        return Case(
            raw["name"], Beam(**raw["beam"]), Thermal(**raw["thermal"]), Limits(**raw["limits"])
        )
    except TypeError as exc:
        raise ValueError(f"Invalid case section or field: {exc}") from exc
