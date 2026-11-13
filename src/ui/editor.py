"""SQL editor: a textarea with a syntax-highlighted overlay, line numbers and autocomplete."""
from __future__ import annotations

from engine import sqltools
from js import document, window

from .dom import closest, esc, later, on

KIND_LABEL = {"tbl": "T", "col": "C", "fn": "F", "kw": "K"}


class Editor:
    def __init__(self, root, schema: dict, on_run, on_change):
        self.root, self.schema = root, schema
        self.on_run, self.on_change = on_run, on_change
        self.ta = root.querySelector("textarea")
        self.pre = root.querySelector("pre")
        self.gutter = root.querySelector(".gutter")
        self.ac = root.querySelector(".ac")
        self.items, self.sel, self.ac_start = [], 0, 0
        self.tables = list(schema)
        self.columns = sorted({c for cols in schema.values() for c in cols})
        self.char_w = self._measure()
        on(self.ta, "input", self._on_input)
        on(self.ta, "keydown", self._on_key)
        on(self.ta, "blur", lambda e: later(self.close_ac, 150))
        on(self.ta, "click", lambda e: self.close_ac())
        on(self.ac, "mousedown", self._on_ac_click)
        self.refresh()

    # ---------- basics ----------
    @property
    def value(self) -> str:
        return self.ta.value

    def set(self, text: str, focus: bool = False) -> None:
        self.ta.value = text
        self.refresh()
        if focus:
            self.focus_end()

    def focus_end(self) -> None:
        self.ta.focus()
        n = len(self.ta.value)
        self.ta.setSelectionRange(n, n)

    def _measure(self) -> float:
        span = document.createElement("span")
        span.textContent = "M" * 20
        span.style.cssText = "position:absolute;visibility:hidden;font:15px 'JetBrains Mono',monospace;white-space:pre"
        document.body.appendChild(span)
        w = span.getBoundingClientRect().width / 20 or 9.0
        span.remove()
        return w

    def refresh(self) -> None:
        text = self.ta.value
        self.pre.innerHTML = sqltools.highlight(text, self.tables, self.columns)
        lines = text.count("\n") + 1
        self.gutter.textContent = "\n".join(str(i) for i in range(1, lines + 1))
        self.ta.style.height = "auto"
        self.ta.style.height = f"{max(190, self.ta.scrollHeight)}px"

    def insert(self, text: str) -> None:
        ta = self.ta
        s, e = ta.selectionStart, ta.selectionEnd
        before = ta.value[:s]
        if before and (before[-1].isalnum() or before[-1] in "_)") and text[:1].isalnum():
            text = " " + text
        ta.setRangeText(text, s, e, "end")
        ta.focus()
        self.refresh()
        self.on_change(ta.value)

    # ---------- events ----------
    def _on_input(self, event) -> None:
        self.refresh()
        self.on_change(self.ta.value)
        kind = getattr(event, "inputType", "") or ""
        data = getattr(event, "data", None)
        if kind.startswith("insert") and data and (data[-1].isalnum() or data[-1] in "_."):
            self.update_ac()
        else:
            self.close_ac()

    def _on_key(self, e) -> None:
        key = e.key
        mod = e.ctrlKey or e.metaKey
        if mod and key == "Enter":
            e.preventDefault()
            self.close_ac()
            self.on_run()
            return
        if mod and key == " ":
            e.preventDefault()
            self.update_ac(force=True)
            return
        if self.items and not self.ac.hidden:
            if key in ("ArrowDown", "ArrowUp"):
                e.preventDefault()
                self.sel = (self.sel + (1 if key == "ArrowDown" else -1)) % len(self.items)
                self.render_ac()
                return
            if key in ("Enter", "Tab"):
                e.preventDefault()
                self.accept(self.sel)
                return
            if key == "Escape":
                e.preventDefault()
                e.stopPropagation()
                self.close_ac()
                return
        if key == "Tab" and not e.shiftKey and not mod:
            e.preventDefault()
            self.insert("  ")

    def _on_ac_click(self, e) -> None:
        li = closest(e.target, "li")
        if li is not None:
            e.preventDefault()
            self.accept(int(li.dataset.i))

    # ---------- autocomplete ----------
    def update_ac(self, force: bool = False) -> None:
        pos = self.ta.selectionStart
        res = sqltools.complete(self.ta.value, pos, self.schema)
        items = res["items"]
        if not items:
            self.close_ac()
            return
        self.items, self.sel, self.ac_start = items, 0, res["start"]
        self.render_ac()
        self.position_ac()

    def render_ac(self) -> None:
        html = []
        for i, it in enumerate(self.items):
            html.append(f'<li role="option" id="ac-{i}" data-i="{i}" aria-selected="{"true" if i == self.sel else "false"}">'
                        f'<span><span class="k" aria-hidden="true">{KIND_LABEL[it["kind"]]}</span>{esc(it["label"])}</span>'
                        f'<small>{esc(it["detail"])}</small></li>')
        self.ac.innerHTML = "".join(html)
        self.ac.hidden = False
        self.ta.setAttribute("aria-expanded", "true")
        self.ta.setAttribute("aria-activedescendant", f"ac-{self.sel}")

    def position_ac(self) -> None:
        text = self.ta.value[: self.ta.selectionStart]
        line = text.count("\n")
        col = len(text) - (text.rfind("\n") + 1)
        width = self.root.clientWidth
        usable = max(1, int((width - 70) / self.char_w))
        line += col // usable          # account for soft-wrapped lines
        col = col % usable
        top = 14 + (line + 1) * 24 + 4
        left = min(56 + col * self.char_w, max(8, width - 250))
        self.ac.style.top = f"{top}px"
        self.ac.style.left = f"{left}px"

    def accept(self, i: int) -> None:
        it = self.items[i]
        label = it["label"]
        end = self.ta.selectionStart
        self.ta.setRangeText(label, self.ac_start, end, "end")
        if label.endswith("("):
            p = self.ta.selectionStart
            self.ta.setRangeText(")", p, p, "start")
        self.close_ac()
        self.ta.focus()
        self.refresh()
        self.on_change(self.ta.value)

    def close_ac(self) -> None:
        self.items = []
        self.ac.hidden = True
        self.ta.setAttribute("aria-expanded", "false")
        self.ta.removeAttribute("aria-activedescendant")
