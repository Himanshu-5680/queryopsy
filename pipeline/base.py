"""Building blocks shared by all dataset adapters."""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .clean import norm_header


@dataclass
class Column:
    name: str
    type: str
    doc: str = ""
    extra: str = ""          # e.g. "PRIMARY KEY" or "REFERENCES t(c)"


@dataclass
class Table:
    name: str
    doc: str
    columns: list[Column]
    rows: list[tuple] = field(default_factory=list)

    def ddl(self) -> str:
        cols = ",\n  ".join(f"{c.name} {c.type}{(' ' + c.extra) if c.extra else ''}" for c in self.columns)
        return f"CREATE TABLE {self.name} (\n  {cols}\n);"


@dataclass
class Level:
    title: str
    task: str                 # what to return, including column order
    hints: list[str]
    solution: str
    concepts: list[str]
    ordered: bool = False
    story: str = ""
    starter: str = ""


@dataclass
class Planted:
    table: str
    key: str                  # primary key value(s) of the planted row
    why: str


class Dataset:
    """Subclass per source dataset. Column aliases are matched on normalised headers."""
    key = ""                      # short id, also the case slug
    case_no = 0
    expected_files = ()           # suggested filenames in data/raw/
    patterns = ()                 # substrings that identify the file by name
    columns: dict[str, tuple[str, ...]] = {}
    required: tuple[str, ...] = ()
    source = {}                   # {"name", "url", "licence"} of the dataset the adapter was designed for
    max_rows = 6000

    def __init__(self, seed: int = 1):
        self.rng = random.Random(f"{self.key}-{seed}")
        self.planted: list[Planted] = []

    # ---------- detection ----------
    def map_columns(self, headers: list[str]) -> dict[str, int]:
        norm = [norm_header(h) for h in headers]
        out: dict[str, int] = {}
        for canon, aliases in self.columns.items():
            al = [norm_header(a) for a in (canon,) + tuple(aliases)]
            idx = next((i for i, h in enumerate(norm) if h in al), None)
            if idx is None:
                idx = next((i for i, h in enumerate(norm) if h and any(a in h for a in al if len(a) >= 4)), None)
            if idx is not None and idx not in out.values():
                out[canon] = idx
        return out

    def score(self, headers: list[str]) -> float:
        m = self.map_columns(headers)
        if not all(r in m for r in self.required):
            return 0.0
        return len(m) / max(len(self.columns), 1)

    def records(self, headers, rows) -> list[dict]:
        m = self.map_columns(headers)
        missing = [r for r in self.required if r not in m]
        if missing:
            raise ValueError(f"{self.key}: missing required columns {missing}; found headers {headers}")
        return [{k: (r[i] if i < len(r) else "") for k, i in m.items()} for r in rows]

    def sample(self, recs: list[dict]) -> list[dict]:
        if len(recs) <= self.max_rows:
            return recs
        idx = sorted(self.rng.sample(range(len(recs)), self.max_rows))
        return [recs[i] for i in idx]

    def plant(self, table: str, key, why: str) -> None:
        self.planted.append(Planted(table, str(key), why))

    # ---------- to implement ----------
    def placeholder(self) -> tuple[list[str], list[list[str]]]:
        raise NotImplementedError

    def build(self, recs: list[dict]) -> list[Table]:
        raise NotImplementedError

    def case(self, tables: list[Table]) -> dict:
        raise NotImplementedError

    def levels(self, tables: list[Table]) -> list[Level]:
        raise NotImplementedError
