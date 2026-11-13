"""Read CSV or XLSX files with only the standard library (no pandas/openpyxl needed)."""
from __future__ import annotations

import csv
import io
import pathlib
import re
import zipfile
import xml.etree.ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def read_csv(path: pathlib.Path) -> tuple[list[str], list[list[str]]]:
    text = _decode(path.read_bytes())
    try:
        dialect = csv.Sniffer().sniff(text[:20000], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = [r for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]
    return [h.strip() for h in rows[0]], rows[1:]


def _col_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref).group()
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_xlsx(path: pathlib.Path) -> tuple[list[str], list[list[str]]]:
    """First worksheet of an .xlsx file as strings (shared strings + inline + numbers)."""
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
                shared.append("".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])))
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        first = wb.find("m:sheets/m:sheet", NS).get(REL)
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        target = next(r.get("Target") for r in rels if r.get("Id") == first)
        target = target.lstrip("/")
        sheet = ET.fromstring(z.read(target if target.startswith("xl/") else "xl/" + target))
        out = []
        for row in sheet.iter("{%s}row" % NS["m"]):
            vals: dict[int, str] = {}
            for c in row.findall("m:c", NS):
                t, v = c.get("t"), c.find("m:v", NS)
                if t == "s" and v is not None:
                    val = shared[int(v.text)]
                elif t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter("{%s}t" % NS["m"]))
                elif t == "b" and v is not None:
                    val = "TRUE" if v.text == "1" else "FALSE"
                else:
                    val = v.text if v is not None and v.text is not None else ""
                    if re.fullmatch(r"-?\d+\.0", val):
                        val = val[:-2]
                vals[_col_index(c.get("r"))] = val
            if vals:
                width = max(vals) + 1
                out.append([vals.get(i, "") for i in range(width)])
    out = [r for r in out if any(x.strip() for x in r)]
    head = [h.strip() for h in out[0]]
    return head, [r + [""] * (len(head) - len(r)) for r in out[1:]]


def read_table(path: pathlib.Path) -> tuple[list[str], list[list[str]]]:
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        return read_xlsx(path)
    if suffix in (".csv", ".txt", ".tsv"):
        return read_csv(path)
    raise ValueError(f"unsupported file type: {path.name}")
