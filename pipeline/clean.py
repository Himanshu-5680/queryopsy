"""Small, well-tested cleaning helpers for messy real-world exports."""
from __future__ import annotations

import datetime as dt
import re

MOJIBAKE = {
    "\\\\xc2\\\\xa0": " ", "\\xc2\\xa0": " ", "\u00a0": " ",
    "\\\\xe2\\\\x80\\\\x99": "'", "\\xe2\\x80\\x99": "'", "\u2019": "'",
    "\\\\xe2\\\\x80\\\\x93": "-", "\\xe2\\x80\\x93": "-",
    "\\\\xe2\\\\x80\\\\x9c": '"', "\\\\xe2\\\\x80\\\\x9d": '"',
    "\\\\n": " ", "\\n": " ",
}
MISSING = {"", "nan", "n/a", "na", "null", "none", "-", "undisclosed", "unknown", "not disclosed"}


def norm_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]", "", h.lower())


def fix_text(s) -> str | None:
    """Undo escaped-UTF-8 artefacts (\\xc2\\xa0, \\xe2\\x80\\x99 ...) and collapse whitespace."""
    if s is None:
        return None
    s = str(s)
    for bad, good in MOJIBAKE.items():
        s = s.replace(bad, good)
    s = re.sub(r"\\+x[0-9a-fA-F]{2}", "", s)
    s = " ".join(s.split())
    return None if s.lower() in MISSING else s


def parse_number(s) -> float | None:
    """'20,00,00,000' / '1,51,09,500.00' / '14,342,000+' / '\u20b9 40' / '12.5%' -> float, 'N/A' -> None."""
    s = fix_text(s)
    if s is None:
        return None
    s = re.sub(r"[^\d.\-]", "", s.replace(",", ""))
    if s in ("", ".", "-") or s.count(".") > 1:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_int(s) -> int | None:
    v = parse_number(s)
    return None if v is None else int(round(v))


def parse_bool(s) -> int | None:
    s = fix_text(s)
    if s is None:
        return None
    s = s.lower()
    if s in ("1", "true", "yes", "y", "t"):
        return 1
    if s in ("0", "false", "no", "n", "f"):
        return 0
    return None


DATE_PATTERNS = [
    (r"(\d{4})-(\d{1,2})-(\d{1,2})", "ymd"),
    (r"(\d{4})(\d{2})(\d{2})", "ymd"),
    (r"(\d{1,2})[/.\-]+(\d{1,2})[/.\-]*(\d{4})", "dmy"),
    (r"(\d{1,2})[/.\-]+(\d{1,2})[/.\-]+(\d{3})", "dmy3"),
]


def parse_date(s, dayfirst: bool = True) -> str | None:
    """Messy date text -> 'YYYY-MM-DD' (or None). Handles '12/05.2015', '05/072018', '01/07/015', '20240117'."""
    s = fix_text(s)
    if s is None:
        return None
    s = s.strip()
    if re.fullmatch(r"\d{2}/\d{6}", s):          # 05/072018 -> 05/07/2018
        s = s[:5] + "/" + s[5:]
    for pat, kind in DATE_PATTERNS:
        m = re.search(pat, s)
        if not m:
            continue
        a, b, c = (int(x) for x in m.groups())
        if kind == "ymd":
            y, mo, d = a, b, c
        else:
            y = c if kind == "dmy" else 2000 + c % 1000
            d, mo = (a, b) if dayfirst else (b, a)
            if mo > 12 and d <= 12:
                d, mo = mo, d
        try:
            return dt.date(y, mo, d).isoformat()
        except ValueError:
            return None
    return None


def parse_datetime(s) -> str | None:
    s = fix_text(s)
    if s is None:
        return None
    m = re.search(r"(\d{4}-\d{2}-\d{2})[ T](\d{1,2}):(\d{2})(?::(\d{2}))?", s)
    if m:
        return f"{m.group(1)} {int(m.group(2)):02d}:{m.group(3)}:{m.group(4) or '00'}"
    d = parse_date(s)
    return f"{d} 00:00:00" if d else None
