from engine import validator as v


def test_canon_values():
    assert v.canon_value(None) == "NULL"
    assert v.canon_value(3) == "3"
    assert v.canon_value(3.0) == "3"
    assert v.canon_value("3.0") == "3"
    assert v.canon_value(2.345) == "2.35"          # half-up, not banker's rounding
    assert v.canon_value(2.5) == "2.5"
    assert v.canon_value(-1.005) in ("-1.01", "-1")  # float repr edge; must be deterministic
    assert v.canon_value("  Bengaluru  ") == "Bengaluru"
    assert v.canon_value("a  b") == "a b"
    assert v.canon_value(True) == "1"


def test_roundtrip_unordered():
    rows = [(1, "a"), (2, "b"), (3, "c")]
    fp = v.fingerprint(rows, 2, "s", ordered=False)
    assert v.check(["x", "y"], list(reversed(rows)), fp, "s")["ok"]
    assert not v.check(["x", "y"], rows, fp, "other-salt")["ok"]


def test_roundtrip_ordered_detects_order():
    rows = [(1, "a"), (2, "b")]
    fp = v.fingerprint(rows, 2, "s", ordered=True)
    assert v.check(["x", "y"], rows, fp, "s")["ok"]
    res = v.check(["x", "y"], rows[::-1], fp, "s")
    assert not res["ok"] and res["orderOnly"]
    assert any("ORDER BY" in t for t in res["tips"])


def test_diff_feedback_without_revealing():
    fp = v.fingerprint([(1,), (2,), (3,)], 1, "s", ordered=False)
    res = v.check(["n"], [(1,), (2,), (9,), (10,)], fp, "s")
    assert res == {**res, "ok": False, "cols": [1, 1], "rows": [4, 3], "matched": 2}
    assert "1" not in "".join(fp["rowHashes"][:0])
    wrong_cols = v.check(["a", "b"], [(1, 1)], fp, "s")
    assert wrong_cols["cols"] == [2, 1] and "column" in wrong_cols["tips"][0]


def test_numeric_type_tolerance():
    fp = v.fingerprint([(10, 2.5)], 2, "s", ordered=False)
    assert v.check(["a", "b"], [(10.0, "2.50")], fp, "s")["ok"]


def test_duplicates_matter():
    fp = v.fingerprint([(1,), (1,)], 1, "s", ordered=False)
    assert not v.check(["a"], [(1,)], fp, "s")["ok"]
    assert v.check(["a"], [(1,), (1,)], fp, "s")["ok"]


def test_fingerprint_has_no_plaintext():
    fp = v.fingerprint([("Vikram Shell Corp", 95000)], 2, "s", ordered=False)
    blob = repr(fp)
    assert "Vikram" not in blob and "95000" not in blob
