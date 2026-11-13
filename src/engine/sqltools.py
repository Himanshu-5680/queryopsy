"""SQL tokenizer used for syntax highlighting and context-aware autocomplete."""
from __future__ import annotations

import html
import re

KEYWORDS = """SELECT FROM WHERE GROUP BY HAVING ORDER LIMIT OFFSET JOIN LEFT RIGHT INNER OUTER FULL CROSS ON USING AS AND OR
NOT IN IS NULL LIKE GLOB BETWEEN DISTINCT ALL UNION INTERSECT EXCEPT WITH RECURSIVE CASE WHEN THEN ELSE END ASC DESC
EXISTS OVER PARTITION ROWS RANGE PRECEDING FOLLOWING UNBOUNDED CURRENT ROW FILTER INSERT INTO VALUES UPDATE SET DELETE
CREATE TABLE VIEW DROP ALTER INDEX PRAGMA EXPLAIN QUERY PLAN CAST COLLATE NOCASE TRUE FALSE""".split()
FUNCTIONS = """COUNT SUM AVG MIN MAX ROUND ABS LENGTH LOWER UPPER TRIM LTRIM RTRIM SUBSTR REPLACE INSTR COALESCE IFNULL NULLIF
DATE TIME DATETIME JULIANDAY STRFTIME UNIXEPOCH PRINTF FORMAT TOTAL GROUP_CONCAT ROW_NUMBER RANK DENSE_RANK NTILE LAG LEAD
FIRST_VALUE LAST_VALUE PERCENT_RANK CUME_DIST TYPEOF IIF""".split()
KW, FN = set(KEYWORDS), set(FUNCTIONS)

TOKEN = re.compile(r"""
 (?P<comment>--[^\n]*|/\*.*?(?:\*/|$))
|(?P<string>'(?:[^']|'')*'?)
|(?P<ident>"(?:[^"]|"")*"?|`[^`]*`?)
|(?P<number>\b\d+(?:\.\d+)?\b)
|(?P<word>[A-Za-z_][A-Za-z0-9_]*)
|(?P<op>[(),;.*=<>!+\-/%|]+)
|(?P<ws>\s+)
|(?P<other>.)
""", re.S | re.X)


def tokens(sql: str):
    for m in TOKEN.finditer(sql):
        yield m.lastgroup, m.group()


def highlight(sql: str, tables=(), columns=()) -> str:
    """Return HTML with <span class="t-..."> wrappers (escaped, safe for innerHTML)."""
    tset = {t.lower() for t in tables}
    cset = {c.lower() for c in columns}
    out = []
    for kind, text in tokens(sql):
        esc = html.escape(text, quote=False)
        if kind == "word":
            up = text.upper()
            if up in KW:
                kind = "kw"
            elif up in FN:
                kind = "fn"
            elif text.lower() in tset:
                kind = "tbl"
            elif text.lower() in cset:
                kind = "col"
            else:
                kind = None
        elif kind in ("ws", "other", "op"):
            kind = "op" if kind == "op" else None
        out.append(f'<span class="t-{kind}">{esc}</span>' if kind else esc)
    # trailing newline needs a visible character so the overlay keeps the same height
    return "".join(out) + ("\n " if sql.endswith("\n") else "")


ALIAS = re.compile(r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s+(?:AS\s+)?([A-Za-z_][A-Za-z0-9_]*))?", re.I)


def aliases(sql: str, schema: dict) -> dict:
    """Map alias/table name (lower-case) -> table for tables present in schema."""
    names = {t.lower(): t for t in schema}
    out = {}
    for m in ALIAS.finditer(sql):
        t = names.get(m.group(1).lower())
        if not t:
            continue
        out[t.lower()] = t
        a = m.group(2)
        if a and a.upper() not in KW:
            out[a.lower()] = t
    return out


def word_before(sql: str, pos: int) -> tuple[str, str | None, int]:
    """(prefix, qualifier, start) of the identifier ending at pos; qualifier is 'x' in 'x.col'."""
    i = pos
    while i > 0 and (sql[i - 1].isalnum() or sql[i - 1] == "_"):
        i -= 1
    prefix = sql[i:pos]
    qual = None
    if i > 0 and sql[i - 1] == ".":
        j = i - 1
        while j > 0 and (sql[j - 1].isalnum() or sql[j - 1] == "_"):
            j -= 1
        qual = sql[j:i - 1]
    return prefix, qual, i


def complete(sql: str, pos: int, schema: dict, limit: int = 8) -> dict:
    """Suggestions for the cursor position. schema = {table: [column, ...]}.

    Returns {"start": index, "items": [{"label", "kind", "detail"}]}.
    """
    prefix, qual, start = word_before(sql, pos)
    al = aliases(sql, schema)
    items = []
    if qual is not None:
        t = al.get(qual.lower()) or next((x for x in schema if x.lower() == qual.lower()), None)
        if t:
            items = [{"label": c, "kind": "col", "detail": t} for c in schema[t] if c.lower().startswith(prefix.lower())]
        return {"start": start, "items": items[:limit]}
    if len(prefix) < 1:
        return {"start": start, "items": []}
    p = prefix.lower()
    before = sql[:start].upper().split()
    last = before[-1] if before else ""
    in_scope = {t for t in al.values()}
    want_table = last in ("FROM", "JOIN", "INTO", "UPDATE", "TABLE")
    for t in schema:
        if t.lower().startswith(p):
            items.append({"label": t, "kind": "tbl", "detail": f"{len(schema[t])} columns"})
    if not want_table:
        seen = set()
        tables = sorted(schema, key=lambda t: t not in in_scope)
        for t in tables:
            for c in schema[t]:
                if c.lower().startswith(p) and c not in seen:
                    seen.add(c)
                    items.append({"label": c, "kind": "col", "detail": t})
        for f in FUNCTIONS:
            if f.lower().startswith(p):
                items.append({"label": f + "(", "kind": "fn", "detail": "function"})
        for k in KEYWORDS:
            if k.lower().startswith(p) and len(p) >= 2:
                items.append({"label": k, "kind": "kw", "detail": "keyword"})
    items = [i for i in items if i["label"].rstrip("(").lower() != p or i["kind"] == "fn"]
    return {"start": start, "items": items[:limit]}
