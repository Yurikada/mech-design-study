"""One common case and explicit geometry variants; no silent condition overrides."""

import math
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

from mech_design.case import Case, load_case, parse_case


def exact_keys(value: object, required: set[str], optional: set[str], label: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a table/object")
    missing = required - value.keys()
    extra = value.keys() - required - optional
    if missing or extra:
        raise ValueError(f"{label}: missing {sorted(missing)}, unsupported fields {sorted(extra)}")


def positive(value: object, label: str) -> None:
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be a finite positive number")


def nonempty(value: object, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")


@dataclass(frozen=True)
class Design:
    id: str
    length_m: float
    width_m: float
    thickness_m: float

    def __post_init__(self) -> None:
        nonempty(self.id, "design id")
        if (
            self.id != self.id.strip()
            or not self.id.isascii()
            or not all(char.isalnum() or char in "_-" for char in self.id)
        ):
            raise ValueError("design id must contain only ASCII letters, digits, '_' or '-'")
        for key in ("length_m", "width_m", "thickness_m"):
            positive(getattr(self, key), f"{self.id}.{key}")


@dataclass(frozen=True)
class Requirements:
    required_length_m: float
    max_width_m: float
    max_thickness_m: float
    max_mass_kg: float | None = None

    def __post_init__(self) -> None:
        for key, value in asdict(self).items():
            if key != "max_mass_kg" or value is not None:
                positive(value, key)


@dataclass(frozen=True)
class Study:
    name: str
    requirements_version: str
    common_case: Case
    requirements: Requirements
    designs: tuple[Design, ...]

    def snapshot(self) -> dict:
        return {
            "schema_version": 1,
            "name": self.name,
            "requirements_version": self.requirements_version,
            "objective": "minimize_mass",
            "common_case": {"schema_version": 1, **asdict(self.common_case)},
            "requirements": {
                key: value for key, value in asdict(self.requirements).items() if value is not None
            },
            "designs": [asdict(design) for design in self.designs],
        }


FIELDS = {"schema_version", "name", "requirements_version", "objective", "requirements", "designs"}


def study_from_snapshot(raw: dict) -> Study:
    exact_keys(raw, FIELDS | {"common_case"}, set(), "comparison snapshot")
    if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
        raise ValueError("Only comparison schema_version = 1 is supported")
    nonempty(raw["name"], "name")
    nonempty(raw["requirements_version"], "requirements_version")
    if raw["objective"] != "minimize_mass":
        raise ValueError("Only objective = 'minimize_mass' is supported")
    exact_keys(
        raw["requirements"],
        {"required_length_m", "max_width_m", "max_thickness_m"},
        {"max_mass_kg"},
        "requirements",
    )
    if "max_mass_kg" in raw["requirements"]:
        positive(raw["requirements"]["max_mass_kg"], "max_mass_kg")
    if not isinstance(raw["designs"], list) or not raw["designs"]:
        raise ValueError("designs must be a nonempty array of tables")
    designs = []
    for item in raw["designs"]:
        exact_keys(
            item,
            {"id", "length_m", "width_m", "thickness_m"},
            set(),
            "design (only geometry may vary; loads/materials/limits are shared via base_case)",
        )
        designs.append(Design(**item))
    if len({item.id for item in designs}) != len(designs):
        raise ValueError("design ids must be unique")
    return Study(
        raw["name"],
        raw["requirements_version"],
        parse_case(raw["common_case"]),
        Requirements(**raw["requirements"]),
        tuple(designs),
    )


def load_study(path: Path) -> Study:
    with path.open("rb") as stream:
        raw = tomllib.load(stream)
    exact_keys(raw, FIELDS | {"base_case"}, set(), "comparison")
    nonempty(raw["base_case"], "base_case")
    # Relative paths are anchored to the study file, never the process working directory.
    base = load_case(path.parent / raw.pop("base_case"))
    return study_from_snapshot({**raw, "common_case": {"schema_version": 1, **asdict(base)}})
