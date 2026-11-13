import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def root():
    return ROOT


@pytest.fixture(scope="session")
def cases():
    return json.loads((ROOT / "data" / "cases.json").read_text(encoding="utf-8"))["cases"]


@pytest.fixture(scope="session")
def solutions():
    return json.loads((ROOT / "tests" / "fixtures" / "solutions.json").read_text(encoding="utf-8"))
