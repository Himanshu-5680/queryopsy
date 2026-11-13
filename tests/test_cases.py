"""Every official solution passes, every walkthrough hint passes, and wrong answers fail."""
import pathlib

import pytest

from engine import validator
from engine.runner import CaseDB

ROOT = pathlib.Path(__file__).resolve().parents[1]
_dbs = {}


def db_for(case):
    if case["db"] not in _dbs:
        _dbs[case["db"]] = CaseDB((ROOT / case["db"]).read_bytes())
    return _dbs[case["db"]]


def all_levels():
    import json
    cases = json.loads((ROOT / "data" / "cases.json").read_text(encoding="utf-8"))["cases"]
    return [(c, lv) for c in cases for lv in c["levels"]]


LEVELS = all_levels()
IDS = [lv["id"] for _, lv in LEVELS]


def run_check(case, lv, sql):
    res = db_for(case).run(sql)
    return validator.check(res.columns, res.rows, lv["answer"], lv["salt"])


@pytest.mark.parametrize("case,lv", LEVELS, ids=IDS)
def test_official_solution_passes(case, lv, solutions):
    assert run_check(case, lv, solutions[lv["id"]])["ok"]


@pytest.mark.parametrize("case,lv", LEVELS, ids=IDS)
def test_walkthrough_hint_passes(case, lv):
    assert run_check(case, lv, lv["hints"][-1])["ok"], "the final hint must be a working query"


@pytest.mark.parametrize("case,lv", LEVELS, ids=IDS)
def test_wrong_answers_fail(case, lv, solutions):
    sol = solutions[lv["id"]].rstrip(";")
    first_table = case["tables"][0]["name"]
    assert not run_check(case, lv, f"SELECT * FROM {first_table} LIMIT 3")["ok"]
    assert not run_check(case, lv, f"SELECT *, 1 AS extra FROM ({sol})")["ok"]
    n = lv["answer"]["rows"]
    if n > 1:
        res = run_check(case, lv, f"SELECT * FROM ({sol}) LIMIT {n - 1}")
        assert not res["ok"] and res["matched"] == n - 1


def test_case_catalogue(cases):
    assert cases[0]["id"] == "case00_training"
    slugs = [c["id"] for c in cases]
    assert len(slugs) == len(set(slugs)) and len(cases) >= 6
    for c in cases:
        assert c["levels"], c["id"]
        assert (ROOT / c["db"]).exists() and (ROOT / c["sql"]).exists()
        for lv in c["levels"]:
            assert set(lv["answer"]) == {"cols", "rows", "ordered", "hash", "rowHashes"}
            assert len(lv["hints"]) == 3


def test_total_data_size_under_budget(cases):
    total = sum((ROOT / p).stat().st_size for p in {c["db"] for c in cases})
    assert total < 5 * 1024 * 1024


def test_planted_rows_documented(root):
    import json
    planted = json.loads((root / "data" / "planted.json").read_text())
    assert all(planted[k] for k in planted)
    doc = (root / "docs" / "PLANTED.md").read_text()
    for rows in planted.values():
        for p in rows:
            assert p["why"] in doc
