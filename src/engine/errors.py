"""Turns raw SQLite errors into short, friendly explanations with a concrete next step."""
from __future__ import annotations

import difflib
import re

KEYWORDS = ["SELECT", "FROM", "WHERE", "GROUP BY", "HAVING", "ORDER BY", "LIMIT", "JOIN", "LEFT JOIN",
            "ON", "AS", "AND", "OR", "NOT", "IN", "LIKE", "BETWEEN", "IS NULL", "DISTINCT", "WITH", "OVER"]


def _closest(word: str, options) -> str | None:
    m = difflib.get_close_matches(word.lower(), [o.lower() for o in options], n=1, cutoff=0.6)
    if not m:
        return None
    for o in options:
        if o.lower() == m[0]:
            return o
    return None


def explain(message: str, tables: list[str], columns: list[str]) -> dict:
    """Return {"title", "detail", "fix"} for an sqlite3 error message."""
    msg = str(message)
    low = msg.lower()
    m = re.search(r"no such table: (?:main\.)?(\S+)", msg)
    if m:
        name = m.group(1)
        s = _closest(name, tables)
        return {"title": f"There is no table called '{name}'",
                "detail": "Table names must match the schema exactly.",
                "fix": f"Did you mean '{s}'?" if s else "Open the Schema panel and click a table name to insert it."}
    m = re.search(r"no such column: (\S+)", msg)
    if m:
        name = m.group(1)
        bare = name.split(".")[-1]
        s = _closest(bare, columns)
        return {"title": f"Unknown column '{name}'",
                "detail": "Either the column is spelled differently or it belongs to another table (or the alias is wrong).",
                "fix": f"Did you mean '{s}'?" if s else "Check the Schema panel; text values need 'single quotes', not \"double\"."}
    m = re.search(r'near "([^"]*)": syntax error', msg)
    if m:
        tok = m.group(1)
        hint = "Look just before this word: a missing comma, bracket or keyword is the usual cause."
        kw = _closest(tok.upper(), KEYWORDS)
        if kw and kw != tok.upper():
            hint = f"'{tok}' looks like a typo of {kw}."
        return {"title": f"Syntax error near '{tok}'", "detail": "SQLite could not parse the query at this point.", "fix": hint}
    if "incomplete input" in low:
        return {"title": "The query ends too early",
                "detail": "A clause, bracket or quote was opened but never finished.",
                "fix": "Check for an unclosed ( or ' and make sure the query does not end with AND / , / WHERE."}
    if "ambiguous column name" in low:
        col = msg.split(":")[-1].strip()
        return {"title": f"'{col}' exists in more than one table",
                "detail": "After a JOIN, SQLite needs to know which table's column you mean.",
                "fix": f"Prefix it with the table or alias, e.g. t.{col}."}
    if "misuse of aggregate" in low or "aggregate functions are not allowed" in low:
        return {"title": "Aggregate used in the wrong place",
                "detail": "COUNT/SUM/AVG cannot go inside WHERE.",
                "fix": "Filter groups with HAVING after GROUP BY, or compute the aggregate in a subquery/CTE."}
    if "group by" in low and "having" in low:
        return {"title": "HAVING needs GROUP BY", "detail": "HAVING filters groups, so the query must group first.",
                "fix": "Add GROUP BY <column> before HAVING, or use WHERE for row filters."}
    if "misuse of window function" in low:
        return {"title": "Window function in the wrong place",
                "detail": "Window functions (ROW_NUMBER, RANK, LAG...) are computed after WHERE/GROUP BY.",
                "fix": "Compute it in a CTE or subquery, then filter on it in the outer query."}
    if "no such function" in low:
        fn = msg.split(":")[-1].strip()
        return {"title": f"SQLite has no function '{fn}'",
                "detail": "This engine is SQLite: some MySQL/PostgreSQL functions differ.",
                "fix": "Try strftime() for dates, substr() for text, CAST(x AS REAL) for decimals, || to join strings."}
    if "result columns" in low or "selects to the left and right" in low:
        return {"title": "UNION parts don't line up", "detail": "Every SELECT in a UNION must return the same number of columns.",
                "fix": "Make both sides select the same count of columns, in the same order."}
    if "empty query" in low:
        return {"title": "Nothing to run", "detail": "The editor is empty.", "fix": "Write a SELECT statement, then press Ctrl+Enter."}
    if "stopped after" in low:
        return {"title": "Query took too long and was stopped",
                "detail": "This usually means a JOIN without an ON condition (every row matched with every row).",
                "fix": "Add the join condition, filter earlier, or add LIMIT while exploring."}
    if "readonly" in low or "read-only" in low:
        return {"title": "This table is read-only", "detail": msg, "fix": "Use SELECT to investigate."}
    return {"title": "SQLite error", "detail": msg, "fix": "Read the message, fix the clause it mentions and run again."}
