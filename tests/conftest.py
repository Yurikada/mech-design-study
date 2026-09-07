from pathlib import Path

import pytest

from mech_design.case import load_case


@pytest.fixture
def case_path():
    return Path(__file__).resolve().parents[1] / "cases" / "heated_cantilever.toml"


@pytest.fixture
def case(case_path):
    return load_case(case_path)
