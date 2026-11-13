import sqlite3

import pytest

from engine import errors, sqltools
from engine.runner import CaseDB, QueryTimeout, split_statements


@pytest.fixture()
def db():
    con = sqlite3.connect(":memory:")
    con.executescript("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT); INSERT INTO t VALUES (1,'a'),(2,'b');"
                      "CREATE TABLE u (t_id INTEGER REFERENCES t(id), v REAL); INSERT INTO u VALUES (1, 2.5);")
    return CaseDB(con.serialize())


def test_split_statements():
    assert split_statements("select 1; select ';' ; -- x;\n select 2 /* ; */") == ["select 1", "select ';'", "select 2"]


def test_run_returns_last_statement(db):
    r = db.run("SELECT 1; SELECT name FROM t ORDER BY id")
    assert r.columns == ["name"] and r.rows == [("a",), ("b",)] and r.statements == 2


def test_reset_restores_data(db):
    db.run("DROP TABLE t")
    assert "t" not in db.tables()
    db.reset()
    assert db.count("t") == 2


def test_introspection(db):
    cols = db.columns("u")
    assert cols[0]["fk"] == "t.id" and db.columns("t")[0]["pk"]


def test_timeout_stops_runaway_query(db):
    with pytest.raises(QueryTimeout):
        db.run("WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT COUNT(*) FROM c", max_seconds=0.3)


@pytest.mark.parametrize("sql,needle", [
    ("SELECT * FROM tt", "Did you mean 't'"),
    ("SELECT nme FROM t", "Did you mean 'name'"),
    ("SELEC * FROM t", "SELECT"),
    ("SELECT * FROM t WHERE", "ends too early"),
    ("SELECT id FROM t JOIN u ON u.t_id = t.id WHERE id = 1 AND t_id = id GROUP BY name HAVING 1", None),
    ("SELECT * FROM t WHERE COUNT(*) > 1", "HAVING"),
    ("SELECT DATEDIFF(1, 2)", "SQLite has no function"),
])
def test_friendly_errors(db, sql, needle):
    try:
        db.run(sql)
    except sqlite3.Error as e:
        info = errors.explain(str(e), db.tables(), ["id", "name", "t_id", "v"])
        text = " ".join(info.values())
        assert needle is None or needle in text, text
        assert info["title"] and info["fix"]


def test_highlight_escapes_html():
    out = sqltools.highlight("SELECT '<b>' FROM t", ["t"], [])
    assert "<b>" not in out.replace('<span class="t-kw">', "") or "&lt;b&gt;" in out
    assert 't-kw' in out and 't-tbl' in out


def test_autocomplete_contexts():
    schema = {"funding_rounds": ["round_id", "startup"], "round_investors": ["round_id", "investor"]}
    assert sqltools.complete("SELECT * FROM fu", 16, schema)["items"][0]["label"] == "funding_rounds"
    r = sqltools.complete("SELECT ri.inv FROM round_investors ri", 13, schema)
    assert [i["label"] for i in r["items"]] == ["investor"]
    labels = [i["label"] for i in sqltools.complete("SELECT sta", 10, schema)["items"]]
    assert "startup" in labels
