"""Progress, drafts, history and preferences in localStorage (one JSON document)."""
from __future__ import annotations

import json
import time

KEY = "queryopsy.progress.v1"


class Store:
    def __init__(self, storage):
        self.ls = storage
        try:
            self.data = json.loads(self.ls.getItem(KEY) or "{}")
        except Exception:
            self.data = {}
        for k, v in (("solved", {}), ("hints", {}), ("drafts", {}), ("history", []), ("attempts", {})):
            self.data.setdefault(k, v)

    def save(self) -> None:
        try:
            self.ls.setItem(KEY, json.dumps(self.data, separators=(",", ":")))
        except Exception:
            pass  # storage full or disabled (private mode): app keeps working in memory

    # --- solved / hints / attempts ---
    def solved(self, level_id: str) -> bool:
        return level_id in self.data["solved"]

    def mark_solved(self, level_id: str) -> bool:
        if level_id in self.data["solved"]:
            return False
        self.data["solved"][level_id] = {"at": int(time.time()), "hints": self.hints(level_id),
                                         "attempts": self.data["attempts"].get(level_id, 0)}
        self.save()
        return True

    def hints(self, level_id: str) -> int:
        return int(self.data["hints"].get(level_id, 0))

    def reveal_hint(self, level_id: str, total: int) -> int:
        n = min(total, self.hints(level_id) + 1)
        self.data["hints"][level_id] = n
        self.save()
        return n

    def attempt(self, level_id: str) -> None:
        self.data["attempts"][level_id] = self.data["attempts"].get(level_id, 0) + 1

    # --- drafts & history ---
    def draft(self, level_id: str) -> str | None:
        return self.data["drafts"].get(level_id)

    def set_draft(self, level_id: str, sql: str) -> None:
        self.data["drafts"][level_id] = sql[:20000]
        self.save()

    def push_history(self, case_id: str, level_id: str, sql: str, outcome: str) -> None:
        h = [x for x in self.data["history"] if x["sql"] != sql]
        h.insert(0, {"case": case_id, "level": level_id, "sql": sql[:4000], "outcome": outcome, "at": int(time.time())})
        self.data["history"] = h[:40]
        self.save()

    # --- prefs ---
    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value) -> None:
        self.data[key] = value
        self.save()

    def reset(self) -> None:
        self.data = {"solved": {}, "hints": {}, "drafts": {}, "history": [], "attempts": {}, "onboarded": True}
        self.save()
