"""Result-set validator.

The same module runs at build time (CPython, to hash the official answers) and in the
browser (Pyodide, to check the player's result).  Answers are never stored in plain
text: only salted SHA-256 fingerprints of the canonical result and of each canonical
row are shipped, which is enough to say "3 of your 5 rows are right" without
revealing what the right rows are.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any, Iterable, Sequence

NUMERIC = re.compile(r"^\s*-?\d+(\.\d+)?\s*$")
ROW_SEP, COL_SEP = "\x1e", "\x1f"


def canon_value(v: Any) -> str:
    """Canonical text for one cell: NULL, numbers rounded half-up to 2 dp, trimmed text."""
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        v = int(v)
    if isinstance(v, (bytes, bytearray)):
        return "0x" + bytes(v).hex()
    if isinstance(v, str):
        if not NUMERIC.match(v):
            return " ".join(v.split())
        v = v.strip()
    try:
        d = Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return str(v)
    if d == d.to_integral_value():
        return str(int(d))
    return format(d.normalize(), "f")


def canon_row(row: Sequence[Any]) -> str:
    return COL_SEP.join(canon_value(v) for v in row)


def _h(salt: str, text: str) -> str:
    return hashlib.sha256((salt + "|" + text).encode("utf-8")).hexdigest()


def fingerprint(rows: Iterable[Sequence[Any]], ncols: int, salt: str, ordered: bool) -> dict:
    """Fingerprint of an official answer (stored in cases.json)."""
    canon = [canon_row(r) for r in rows]
    body = canon if ordered else sorted(canon)
    return {
        "cols": ncols,
        "rows": len(canon),
        "ordered": ordered,
        "hash": _h(salt, f"{ncols}{ROW_SEP}" + ROW_SEP.join(body)),
        "rowHashes": sorted(_h(salt, c)[:20] for c in canon),
    }


def check(columns: Sequence[str], rows: Sequence[Sequence[Any]], answer: dict, salt: str) -> dict:
    """Compare a player's result with an answer fingerprint.

    Returns {"ok": bool, "cols": (got, want), "rows": (got, want), "matched": n,
             "orderOnly": bool, "tips": [...]} - never the expected values themselves.
    """
    ncols = len(columns)
    canon = [canon_row(r) for r in rows]
    ordered = bool(answer.get("ordered"))
    body = canon if ordered else sorted(canon)
    ok = ncols == answer["cols"] and _h(salt, f"{ncols}{ROW_SEP}" + ROW_SEP.join(body)) == answer["hash"]
    want = Counter(answer["rowHashes"])
    got = Counter(_h(salt, c)[:20] for c in canon)
    matched = sum(min(n, want[h]) for h, n in got.items())
    order_only = (not ok and ordered and ncols == answer["cols"] and matched == answer["rows"] == len(canon))
    tips: list[str] = []
    if not ok:
        if ncols != answer["cols"]:
            tips.append(f"Return exactly {answer['cols']} column(s) in the order the task lists them (you returned {ncols}).")
        if len(canon) != answer["rows"]:
            more = len(canon) > answer["rows"]
            tips.append(f"Expected {answer['rows']} row(s), you returned {len(canon)} - "
                        + ("tighten a filter or remove duplicates." if more else "a filter may be too strict, or a join is dropping rows."))
        if order_only:
            tips.append("All the right rows are there - only the ORDER BY is off.")
        elif ncols == answer["cols"] and matched == 0 and canon:
            tips.append("None of your rows match yet. Check the column order, rounding and units the task asks for.")
        elif matched:
            tips.append(f"{matched} of your rows are correct.")
    return {"ok": ok, "cols": [ncols, answer["cols"]], "rows": [len(canon), answer["rows"]],
            "matched": matched, "orderOnly": order_only, "tips": tips}
