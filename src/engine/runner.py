"""Runs player SQL against an in-memory copy of a case database (Python sqlite3).

Each case database ships as a prebuilt .sqlite file. It is deserialised into an
in-memory connection, so a bad UPDATE/DROP only affects the session and "Reset data"
restores it instantly. A progress handler stops runaway queries (e.g. accidental
cross joins) so the page never freezes.
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field

MAX_SECONDS = 4.0
DISPLAY_LIMIT = 500


@dataclass
class Result:
    columns: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    ms: float = 0.0
    statements: int = 0
    message: str = ""


class QueryTimeout(Exception):
    pass


def split_statements(sql: str) -> list[str]:
    """Split on semicolons that are outside quotes and comments."""
    out, buf, i, n = [], [], 0, len(sql)
    quote = None
    while i < n:
        c = sql[i]
        if quote:
            buf.append(c)
            if c == quote:
                quote = None
        elif c in ("'", '"', "`"):
            quote = c
            buf.append(c)
        elif c == "-" and sql.startswith("--", i):
            j = sql.find("\n", i)
            i = n if j < 0 else j
            continue
        elif c == "/" and sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        elif c == ";":
            stmt = "".join(buf).strip()
            if stmt:
                out.append(stmt)
            buf = []
        else:
            buf.append(c)
        i += 1
    stmt = "".join(buf).strip()
    if stmt:
        out.append(stmt)
    return out


class CaseDB:
    def __init__(self, image: bytes):
        self.image = bytes(image)
        self.conn = None
        self.reset()

    def reset(self) -> None:
        if self.conn is not None:
            self.conn.close()
        self.conn = sqlite3.connect(":memory:")
        self.conn.deserialize(self.image)

    # ---- schema introspection (drives the schema explorer and autocomplete) ----
    def tables(self) -> list[str]:
        q = "SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY name"
        return [r[0] for r in self.conn.execute(q)]

    def columns(self, table: str) -> list[dict]:
        cols = [{"name": r[1], "type": r[2] or "ANY", "pk": bool(r[5])}
                for r in self.conn.execute(f'PRAGMA table_info("{table}")')]
        fks = {r[3]: f"{r[2]}.{r[4]}" for r in self.conn.execute(f'PRAGMA foreign_key_list("{table}")')}
        for c in cols:
            c["fk"] = fks.get(c["name"])
        return cols

    def count(self, table: str) -> int:
        return self.conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]

    # ---- execution ----
    def run(self, sql: str, max_seconds: float = MAX_SECONDS) -> Result:
        stmts = split_statements(sql)
        if not stmts:
            raise sqlite3.OperationalError("empty query")
        deadline = time.monotonic() + max_seconds

        def guard():
            return 1 if time.monotonic() > deadline else 0

        self.conn.set_progress_handler(guard, 20000)
        t0 = time.perf_counter()
        try:
            res = Result(statements=len(stmts))
            for i, s in enumerate(stmts):
                try:
                    cur = self.conn.execute(s)
                except sqlite3.OperationalError as e:
                    if "interrupted" in str(e):
                        raise QueryTimeout(f"Stopped after {max_seconds:.0f} s") from e
                    raise
                if i == len(stmts) - 1:
                    if cur.description:
                        res.columns = [d[0] for d in cur.description]
                        res.rows = cur.fetchall()
                    else:
                        res.message = f"Statement ran. {max(cur.rowcount, 0)} row(s) changed."
            res.ms = (time.perf_counter() - t0) * 1000
            return res
        finally:
            self.conn.set_progress_handler(None, 0)
