"""Queryopsy application controller (Python, running in the browser through Pyodide)."""
from __future__ import annotations

import asyncio
import sqlite3
import time

from engine import errors, validator
from engine.runner import DISPLAY_LIMIT, CaseDB, QueryTimeout
from js import document, localStorage, window
from pyodide.http import pyfetch

from . import theme_toggle
from .dom import closest, esc, later, nn, on, qs, toast
from .editor import Editor
from .store import Store

EXHIBITS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def exhibit(i: int) -> str:
    """Findings are filed as exhibits: A, B, C ..."""
    return EXHIBITS[i] if i < len(EXHIBITS) else str(i + 1)


ICON_PLAY = '<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M2 1l11 6-11 6z" fill="currentColor"/></svg>'


class App:
    def __init__(self, data: dict):
        self.data = data
        self.cases = data["cases"]
        self.by_id = {c["id"]: c for c in self.cases}
        self.store = Store(localStorage)
        self.dbs: dict[str, CaseDB] = {}
        self.case = None
        self.level_i = 0
        self.editor = None
        self.schema_tab = "tables"
        self.busy = False

    # ================= lifecycle =================
    def start(self) -> None:
        on(document, "click", self.on_click)
        on(document, "keydown", self.on_key)
        from pyodide.ffi import create_proxy
        self._back_proxy = create_proxy(self.back)
        window.queryopsyBack = self._back_proxy          # used by the Android back button
        on(window, "hashchange", lambda e: asyncio.ensure_future(self.route()))
        theme_toggle.apply(theme_toggle.current())
        theme_toggle.watch_system()
        document.documentElement.classList.add("ready")
        st = qs("#engine-status")
        st.classList.add("ready")
        st.innerHTML = f'<span>Python {self.data.get("python", "")} + SQLite {sqlite3.sqlite_version}</span>'
        st.setAttribute("title", "SQL runs locally in your browser - Python's sqlite3 compiled to WebAssembly")
        for card in document.querySelectorAll(".case-card"):
            card.removeAttribute("aria-disabled")
        self.update_home()
        asyncio.ensure_future(self.route())
        if not self.store.get("onboarded"):
            self.show_onboarding()

    async def route(self) -> None:
        parts = [p for p in (window.location.hash or "").lstrip("#").split("/") if p]
        if len(parts) >= 2 and parts[0] == "case" and parts[1] in self.by_id:
            n = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
            await self.open_case(parts[1], n)
        else:
            self.show_home(scroll=parts[:1] != ["cases"])
            if parts[:1] == ["cases"]:
                el = qs("#cases")
                if el is not None:
                    el.scrollIntoView({"behavior": "smooth", "block": "start"})

    def go(self, hash_: str) -> None:
        if window.location.hash == hash_:
            asyncio.ensure_future(self.route())
        else:
            window.location.hash = hash_

    # ================= progress helpers =================
    def case_progress(self, case: dict) -> tuple[int, int]:
        done = sum(1 for lv in case["levels"] if self.store.solved(lv["id"]))
        return done, len(case["levels"])

    def total_progress(self) -> tuple[int, int]:
        d = t = 0
        for c in self.cases:
            a, b = self.case_progress(c)
            d, t = d + a, t + b
        return d, t

    def update_pill(self) -> None:
        d, t = self.total_progress()
        qs("#progress-count").textContent = f"{d}/{t}"
        qs("#progress-meter").style.width = f"{100 * d / max(t, 1):.0f}%"
        qs("#progress-pill").setAttribute("aria-label", f"{d} of {t} findings proven")

    def update_home(self) -> None:
        self.update_pill()
        for c in self.cases:
            card = qs(f'.case-card[data-case="{c["id"]}"]')
            if card is None:
                continue
            d, t = self.case_progress(c)
            card.querySelector(".bar > i").style.width = f"{100 * d / t:.0f}%"
            card.querySelector(".count").textContent = f"{d}/{t} findings"
            card.classList.toggle("done", d == t)
            card.querySelector(".go").textContent = "Review" if d == t else ("Continue" if d else "Open case")
        nxt = self.next_unsolved()
        cta = qs("#cta-continue")
        if cta is not None:
            if nxt and self.total_progress()[0] > 0:
                c, lv = nxt
                cta.textContent = f"Continue: {c['title']}"
                cta.dataset.case = c["id"]
                cta.hidden = False
            else:
                cta.hidden = True

    def next_unsolved(self):
        for c in self.cases:
            for lv in c["levels"]:
                if not self.store.solved(lv["id"]):
                    return c, lv
        return None

    # ================= views =================
    def show_home(self, scroll: bool = True) -> None:
        was_case = self.case is not None
        self.case = None
        qs("#view-case").hidden = True
        qs("#view-case").innerHTML = ""
        qs("#view-home").hidden = False
        document.title = "Queryopsy - Zero-Server SQL Forensics"
        self.update_home()
        if scroll and was_case:
            window.scrollTo(0, 0)

    async def load_db(self, case: dict) -> CaseDB:
        path = case["db"]
        if path not in self.dbs:
            resp = await pyfetch(path)
            if not resp.ok:
                raise RuntimeError(f"could not load {path} ({resp.status})")
            self.dbs[path] = CaseDB(await resp.bytes())
        return self.dbs[path]

    async def open_case(self, case_id: str, n: int | None) -> None:
        case = self.by_id[case_id]
        if self.case is not case:
            qs("#view-home").hidden = True
            view = qs("#view-case")
            view.hidden = False
            view.innerHTML = '<div class="wrap"><div class="card empty"><b>Opening the evidence room...</b>Loading case database</div></div>'
            try:
                self.db = await self.load_db(case)
            except Exception as e:  # noqa: BLE001
                view.innerHTML = f'<div class="wrap"><div class="card boot-error"><b>Could not open this case.</b> {esc(e)}</div></div>'
                return
            self.case = case
            self.render_case()
            window.scrollTo(0, 0)
        levels = case["levels"]
        if n is None:
            n = next((i + 1 for i, lv in enumerate(levels) if not self.store.solved(lv["id"])), 1)
        self.select_level(max(0, min(len(levels) - 1, n - 1)))

    # ---------- case layout ----------
    def render_case(self) -> None:
        c = self.case
        schema = {t["name"]: [col["name"] for col in t["columns"]] for t in c["tables"]}
        src = c["source"]
        src_chip = ('<span class="chip chip-warn" title="Synthetic sample until the real dataset is dropped into data/raw/">Placeholder data</span>'
                    if src.get("placeholder") else f'<span class="chip chip-ok" title="{esc(src["name"])}">Real dataset</span>')
        brief = "".join(f"<p>{esc(p)}</p>" for p in c["brief"])
        document.title = f"{c['title']} - Queryopsy"
        qs("#view-case").innerHTML = f"""
<div class="workspace" data-mtab="brief" id="workspace">
  <aside class="panel card dossier-panel" aria-label="Case dossier">
    <span class="clip" aria-hidden="true"></span><span class="pin" aria-hidden="true"></span>
    <span class="stamp stamp-conf" aria-hidden="true">Confidential</span>
    <div class="dossier panel-body">
      <button class="back" data-action="home" aria-label="Back to all cases">&larr; All cases <kbd>Alt</kbd><kbd>B</kbd></button>
      <div class="eyebrow">Case {c['no']:02d} &middot; {esc(c['industry'])}</div>
      <h1>{esc(c['title'])}</h1>
      <div class="fileref">File no. QX/{c['no']:02d}/{len(c['levels'])} &middot; Source <span class="redact" aria-hidden="true">XXXXXXXX</span><span class="sr-only">redacted</span></div>
      <div class="client">Client: {esc(c['client'])}</div>
      <div class="row" style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px"><span class="chip">{esc(c['difficulty'])}</span>{src_chip}</div>
      <div class="brief" id="brief">{brief}</div>
      <button class="linkish" data-action="brief-toggle" id="brief-toggle" hidden>Read full brief</button>
      <nav class="stepper" id="stepper" aria-label="Findings"></nav>
      <div id="finding"></div>
    </div>
  </aside>
  <section class="bench panel" aria-label="Query workbench">
    <div class="card">
      <span class="pin" aria-hidden="true"></span>
      <div class="toolbar">
        <button class="btn btn-primary" data-action="run" id="run-btn">{ICON_PLAY} Run <span class="label">&nbsp;<kbd>Ctrl</kbd>+<kbd>Enter</kbd></span></button>
        <span class="term" aria-hidden="true">Interrogation terminal</span>
        <span class="spacer"></span>
        <button class="btn btn-sm btn-secondary evidence-btn" data-action="evidence" aria-controls="evidence-room" aria-expanded="false" title="Evidence room (Alt+E)">Evidence</button>
        <button class="btn btn-sm" data-action="history" title="Query history (Alt+Y)">History</button>
        <button class="btn btn-sm" data-action="reset-editor" title="Restore the starter query">Clear</button>
        <button class="btn btn-sm" data-action="reset-data" title="Undo any changes you made to the tables">Reset data</button>
      </div>
      <div class="editor" id="editor">
        <div class="gutter" aria-hidden="true">1</div>
        <pre aria-hidden="true"></pre>
        <textarea id="sql" spellcheck="false" autocapitalize="off" autocomplete="off" autocorrect="off" wrap="soft"
          aria-label="SQL editor. Ctrl+Enter runs the query, Ctrl+Space shows suggestions." role="combobox" aria-autocomplete="list"
          aria-controls="ac-list" aria-expanded="false"></textarea>
        <ul class="ac" id="ac-list" role="listbox" aria-label="Suggestions" hidden></ul>
      </div>
      <div class="editor-foot"><span>Ctrl+Space suggest &middot; Tab/Enter accept &middot; click any name in the schema to insert it</span><span id="run-meta">SQLite {sqlite3.sqlite_version} &middot; in-browser</span></div>
    </div>
    <div class="card" id="results" aria-live="polite">
      <div class="empty"><b>Results appear here</b>Run a query to see rows and an instant verdict.</div>
    </div>
  </section>
  <aside class="panel card schema-panel" id="evidence-room" aria-label="Evidence room: database schema">
    <span class="pin" aria-hidden="true"></span>
    <div class="panel-head"><h2>Evidence room</h2><span class="chip">{len(c['tables'])} tables</span>
      <button class="btn btn-sm drawer-close" data-action="evidence" aria-label="Close the evidence room">Close</button></div>
    <div class="schema-tabs" role="tablist" aria-label="Schema view">
      <button role="tab" id="tab-tables" data-action="schema-tab" data-tab="tables" aria-selected="true" aria-controls="schema">Tables</button>
      <button role="tab" id="tab-diagram" data-action="schema-tab" data-tab="diagram" aria-selected="false" aria-controls="schema" tabindex="-1">ER diagram</button>
    </div>
    <div class="schema panel-body" id="schema" role="tabpanel" aria-labelledby="tab-tables"></div>
  </aside>
</div>
<nav class="mobile-tabs" aria-label="Case sections">
  <button data-action="mtab" data-tab="brief" aria-pressed="true">Dossier</button>
  <button data-action="mtab" data-tab="schema" aria-pressed="false">Evidence</button>
  <button data-action="mtab" data-tab="query" aria-pressed="false">Query</button>
</nav>"""
        self.render_schema()
        self.editor = Editor(qs("#editor"), schema, self.run, self.on_editor_change)

    def set_mtab(self, tab: str) -> None:
        ws = qs("#workspace")
        if ws is None:
            return
        ws.setAttribute("data-mtab", tab)
        for b in document.querySelectorAll(".mobile-tabs button"):
            b.setAttribute("aria-pressed", "true" if b.dataset.tab == tab else "false")
        window.scrollTo(0, 0)
        if tab == "query" and self.editor is not None:
            self.editor.refresh()

    def set_evidence(self, open_: bool | None = None) -> None:
        """Tablet layout: slide the evidence room in or out."""
        ws = qs("#workspace")
        if ws is None:
            return
        if open_ is None:
            open_ = ws.getAttribute("data-evidence") != "open"
        ws.setAttribute("data-evidence", "open" if open_ else "closed")
        for b in document.querySelectorAll(".evidence-btn"):
            b.setAttribute("aria-expanded", "true" if open_ else "false")
        if open_:
            later(lambda: qs("#evidence-room .schema-tabs button[aria-selected='true']") and qs("#evidence-room .schema-tabs button[aria-selected='true']").focus(), 60)
        elif self.editor and not self.is_mobile():
            self.editor.ta.focus()

    def evidence_is_drawer(self) -> bool:
        return bool(window.matchMedia("(max-width: 1180px) and (min-width: 861px)").matches)

    def is_mobile(self) -> bool:
        return bool(window.matchMedia("(max-width: 860px)").matches)

    # ---------- schema ----------
    def render_schema(self) -> None:
        c = self.case
        box = qs("#schema")
        for b in document.querySelectorAll(".schema-tabs button"):
            sel = b.dataset.tab == self.schema_tab
            b.setAttribute("aria-selected", "true" if sel else "false")
            b.setAttribute("tabindex", "0" if sel else "-1")
        box.setAttribute("aria-labelledby", "tab-diagram" if self.schema_tab == "diagram" else "tab-tables")
        if self.schema_tab == "diagram":
            box.innerHTML = (f'<div class="erd-wrap">{c["erd"]}</div><p class="legend">Click (or focus and press Enter on) a table or column to insert it. '
                             'Strings connect foreign keys; the dot marks the referenced column.</p>'
                             '<button class="btn btn-sm" data-action="erd-expand">Expand diagram</button>')
            return
        out = []
        for i, t in enumerate(c["tables"]):
            cols = []
            for col in t["columns"]:
                key = '<span class="key">PK</span>' if col["pk"] else (f'<span class="key fk" title="references {esc(col["fk"])}">FK</span>' if col["fk"] else "")
                cols.append(f'<li title="{esc(col["doc"])}{(" - references " + esc(col["fk"])) if col["fk"] else ""}">{key}'
                            f'<button data-action="insert" data-insert="{esc(col["name"])}">{esc(col["name"])}</button>'
                            f'<span class="ty">{esc(col["type"])}</span></li>')
            out.append(f'<details class="tbl" {"open" if i < 2 else ""}><summary>'
                       f'<button class="ins" data-action="insert" data-insert="{esc(t["name"])}" title="Insert table name">{esc(t["name"])}</button>'
                       f'<small>{t["rows"]:,} rows</small></summary><p class="doc">{esc(t["doc"])}</p>'
                       f'<ul class="cols">{"".join(cols)}</ul><div class="tools">'
                       f'<button class="btn btn-sm" data-action="preview" data-table="{esc(t["name"])}">Preview rows</button></div></details>')
        box.innerHTML = "".join(out)

    # ---------- level ----------
    def select_level(self, i: int) -> None:
        c = self.case
        self.level_i = i
        lv = c["levels"][i]
        self.render_stepper()
        self.render_finding()
        draft = self.store.draft(lv["id"])
        default = lv.get("starter") or f"-- {lv['title']}\n-- Tables: {', '.join(t['name'] for t in c['tables'])}\nSELECT \n"
        self.editor.set(draft if draft is not None else default)
        res = qs("#results")
        res.innerHTML = '<div class="empty"><b>Results appear here</b>Run a query to see rows and an instant verdict.</div>'
        want = f"#/case/{c['id']}/{i + 1}"
        if window.location.hash != want:
            window.history.replaceState(None, "", want)
        brief = qs("#brief")
        if not brief.getAttribute("data-touched"):
            brief.classList.add("collapsed")
            qs("#brief-toggle").hidden = len(c["brief"]) < 2

    def render_stepper(self) -> None:
        c = self.case
        out = []
        for i, lv in enumerate(c["levels"]):
            done = self.store.solved(lv["id"])
            cur = ' aria-current="step"' if i == self.level_i else ""
            out.append(f'<button data-action="level" data-n="{i}" class="{"done" if done else ""}"{cur} '
                       f'aria-label="Exhibit {exhibit(i)}, finding {i + 1}: {esc(lv["title"])}{" (proven)" if done else ""}" title="Exhibit {exhibit(i)}: {esc(lv["title"])}">'
                       f'{"&#10003;" if done else exhibit(i)}</button>')
        qs("#stepper").innerHTML = "".join(out)

    def render_finding(self) -> None:
        c, lv = self.case, self.case["levels"][self.level_i]
        n_h = self.store.hints(lv["id"])
        hints = []
        for k in range(n_h):
            label = "Answer walkthrough" if k == len(lv["hints"]) - 1 else f"Hint {k + 1}"
            body = lv["hints"][k]
            body = f"<code>{esc(body)}</code>" if k == len(lv["hints"]) - 1 else esc(body)
            hints.append(f'<div class="hint"><b>{label}</b>{body}</div>')
        more = ""
        if n_h < len(lv["hints"]):
            nxt = "Show the answer walkthrough" if n_h == len(lv["hints"]) - 1 else f"Need a hint? ({n_h + 1}/{len(lv['hints'])})"
            more = f'<button class="btn btn-sm" data-action="hint" title="Alt+H">{nxt}</button>'
        solved = self.store.solved(lv["id"])
        last = self.level_i == len(c["levels"]) - 1
        banner = ""
        if solved:
            nxt_btn = (f'<button class="btn btn-sm btn-primary" data-action="next">Next finding &rarr;</button>' if not last else
                       '<button class="btn btn-sm btn-primary" data-action="home">All cases</button>')
            banner = f'<div class="solved-banner">&#10003; Exhibit {exhibit(self.level_i)} proven {nxt_btn}</div>'
        concepts = "".join(f'<span class="chip">{esc(x)}</span>' for x in lv["concepts"])
        story = f'<p class="story">{esc(lv["story"])}</p>' if lv.get("story") else ""
        qs("#finding").innerHTML = f"""
<div class="finding">
  <span class="tag">Exhibit {exhibit(self.level_i)}</span>
  <div class="eyebrow">Finding {self.level_i + 1} of {len(c['levels'])}</div>
  <h3>{esc(lv['title'])}</h3>{story}
  <div class="task"><span class="eyebrow" style="display:block;margin-bottom:4px">Your task</span>{esc(lv['task'])}</div>
  <div class="concepts" aria-label="SQL concepts">{concepts}</div>
  <div class="hints">{''.join(hints)}{more}</div>
  <button class="btn btn-sm btn-primary mobile-only" data-action="mtab" data-tab="query" style="margin-top:10px">Write the query &rarr;</button>
  {banner}
</div>"""

    def on_editor_change(self, text: str) -> None:
        if self.case:
            self.store.set_draft(self.case["levels"][self.level_i]["id"], text)

    # ================= running =================
    def run(self) -> None:
        if self.case is None or self.busy:
            return
        sql = self.editor.value
        lv = self.case["levels"][self.level_i]
        btn = qs("#run-btn")
        btn.classList.add("pressed")
        later(lambda: btn.classList.remove("pressed"), 120)
        self.busy = True
        try:
            res = self.db.run(sql)
        except (sqlite3.Error, QueryTimeout) as e:
            self.store.attempt(lv["id"])
            self.store.push_history(self.case["id"], lv["id"], sql, "error")
            self.render_error(e)
            return
        finally:
            self.busy = False
        self.store.attempt(lv["id"])
        if not res.columns:
            self.store.push_history(self.case["id"], lv["id"], sql, "ran")
            qs("#results").innerHTML = (f'<div class="verdict no"><h3>Statement executed</h3><p>{esc(res.message)} '
                                        'Changes live only in this session - use <b>Reset data</b> to restore the original tables.</p></div>')
            self.after_run()
            return
        check = validator.check(res.columns, res.rows, lv["answer"], lv["salt"])
        self.store.push_history(self.case["id"], lv["id"], sql, "proven" if check["ok"] else "checked")
        first = False
        if check["ok"]:
            first = self.store.mark_solved(lv["id"])
        self.render_results(res, check, first)
        if check["ok"]:
            self.render_stepper()
            self.render_finding()
            self.update_pill()
            if first and all(self.store.solved(x["id"]) for x in self.case["levels"]):
                later(self.show_case_closed, 900)
        self.after_run()

    def after_run(self) -> None:
        res = qs("#results")
        if res is None:
            return
        if self.is_mobile():
            later(lambda: res.scrollIntoView({"behavior": "smooth", "block": "start"}), 30)
            return
        # desktop / short windows: bring the verdict into view only when it is off-screen
        r = res.getBoundingClientRect()
        if r.top > window.innerHeight - 80 or r.bottom < 80:
            later(lambda: res.scrollIntoView({"behavior": "smooth", "block": "start"}), 30)

    def table_html(self, columns, rows) -> str:
        head = '<th class="idx">#</th>' + "".join(f"<th>{esc(c)}</th>" for c in columns)
        body = []
        for i, r in enumerate(rows[:DISPLAY_LIMIT], start=1):
            cells = []
            for v in r:
                if v is None:
                    cells.append('<td class="null">NULL</td>')
                elif isinstance(v, (int, float)):
                    cells.append(f'<td class="num">{v:,}</td>' if isinstance(v, int) and abs(v) >= 10000 else f'<td class="num">{esc(v)}</td>')
                else:
                    cells.append(f'<td title="{esc(v)}">{esc(v)}</td>')
            body.append(f'<tr><td class="idx">{i}</td>{"".join(cells)}</tr>')
        return f'<div class="table-wrap" tabindex="0" aria-label="Query results"><table class="grid"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'

    def render_results(self, res, check, first: bool) -> None:
        if check["ok"]:
            last = self.level_i == len(self.case["levels"]) - 1
            nxt = ('<button class="btn btn-primary btn-sm" data-action="next">Next finding &rarr; <kbd>Alt</kbd><kbd>N</kbd></button>'
                   if not last else '<button class="btn btn-primary btn-sm" data-action="certificate">Audit certificate</button>')
            verdict = (f'<div class="verdict ok" role="status"><h3><span class="stamp">Solved</span> Proven: exhibit {exhibit(self.level_i)} confirmed</h3>'
                       f'<p>Your result matches the evidence exactly - {check["rows"][1]} row(s), {check["cols"][1]} column(s).'
                       f'{" Logged to your audit trail." if first else ""}</p><div>{nxt}</div></div>')
        else:
            def chip(label, got, want):
                cls = "chip-ok" if got == want else "chip-bad"
                return f'<span class="chip {cls}">{label} {got} / {want} {"&#10003;" if got == want else "&#10007;"}</span>'
            m_cls = "chip-ok" if check["matched"] == check["rows"][1] else "chip-warn"
            diff = (chip("Columns", *check["cols"]) + chip("Rows", *check["rows"]) +
                    f'<span class="chip {m_cls}">Matching rows {check["matched"]} / {check["rows"][1]}</span>')
            tips = "".join(f"<li>{esc(t)}</li>" for t in check["tips"])
            verdict = (f'<div class="verdict no" role="status"><h3>Not proven yet</h3><div class="diff" aria-label="Comparison with the expected result">{diff}</div>'
                       f'<ul>{tips}</ul></div>')
        more = f" &middot; showing first {DISPLAY_LIMIT}" if len(res.rows) > DISPLAY_LIMIT else ""
        meta = (f'<div class="results-meta"><span>{len(res.rows):,} row(s) &middot; {len(res.columns)} column(s){more}</span>'
                f'<span>{res.ms:.1f} ms</span></div>')
        table = self.table_html(res.columns, res.rows) if res.rows else '<div class="empty"><b>No rows</b>The query ran but returned nothing.</div>'
        qs("#results").innerHTML = verdict + meta + table

    def render_error(self, e) -> None:
        tables = self.db.tables()
        cols = sorted({c["name"] for t in self.case["tables"] for c in t["columns"]})
        info = errors.explain(str(e), tables, cols)
        qs("#results").innerHTML = (f'<div class="verdict err" role="alert"><h3>{esc(info["title"])}</h3><p>{esc(info["detail"])}</p>'
                                    f'<p><b>Try:</b> {esc(info["fix"])}</p><p class="muted mono" style="font-size:.8rem">SQLite said: {esc(e)}</p></div>')
        self.after_run()

    def preview(self, table: str) -> None:
        try:
            res = self.db.run(f'SELECT * FROM "{table}" LIMIT 25')
        except Exception as e:  # noqa: BLE001
            self.render_error(e)
            return
        qs("#results").innerHTML = (f'<div class="verdict"><h3>Preview: {esc(table)}</h3><p class="muted">First 25 rows - previews are not checked against the finding.</p></div>'
                                    + self.table_html(res.columns, res.rows))
        if self.is_mobile():
            self.set_mtab("query")
        elif self.evidence_is_drawer():
            self.set_evidence(False)
        self.after_run()

    # ================= events =================
    def on_click(self, e) -> None:
        el = closest(e.target, "[data-action]")
        if el is None:
            ins = closest(e.target, "[data-insert]")      # SVG ER diagram nodes
            if ins is not None and self.editor:
                self.insert_name(ins.getAttribute("data-insert"))
                if qs("#overlay .erd-modal") is not None:
                    self.close_overlay()
            return
        a = el.dataset.action
        if a == "open-case":
            e.preventDefault()
            if el.getAttribute("aria-disabled") == "true":
                toast("The SQL engine is still starting...")
                return
            self.go(f"#/case/{el.dataset.case}")
        elif a == "home":
            e.preventDefault()
            self.close_overlay()
            self.go("#/")
        elif a == "theme":
            theme_toggle.toggle()
        elif a == "help":
            self.show_onboarding()
        elif a == "shortcuts":
            self.show_shortcuts()
        elif a == "certificate":
            self.close_overlay()
            self.show_certificate()
        elif a == "run":
            self.run()
        elif a == "hint":
            self.reveal_hint()
        elif a == "level":
            self.select_level(int(el.dataset.n))
        elif a == "next":
            self.next_level()
        elif a == "insert":
            e.preventDefault()
            e.stopPropagation()
            self.insert_name(el.dataset.insert)
        elif a == "preview":
            self.preview(el.dataset.table)
        elif a == "evidence":
            self.set_evidence()
        elif a == "schema-tab":
            self.schema_tab = el.dataset.tab
            self.render_schema()
        elif a == "erd-expand":
            self.overlay(f'<div class="panel-head" style="padding:0 0 12px;border:0"><h2>Entity relationship diagram</h2>'
                         f'<button class="btn btn-sm" data-action="close" autofocus>Close</button></div>'
                         f'<div class="erd-wrap">{self.case["erdWide"]}</div><p class="legend">Click a name to insert it into the editor.</p>',
                         "ER diagram")
            qs("#overlay .modal").classList.add("erd-modal")
        elif a == "mtab":
            self.set_mtab(el.dataset.tab)
        elif a == "brief-toggle":
            b = qs("#brief")
            b.setAttribute("data-touched", "1")
            b.classList.toggle("collapsed")
            el.textContent = "Read full brief" if b.classList.contains("collapsed") else "Show less"
        elif a == "reset-editor":
            lv = self.case["levels"][self.level_i]
            self.editor.set(lv.get("starter") or "SELECT \n", focus=True)
            self.on_editor_change(self.editor.value)
        elif a == "reset-data":
            self.db.reset()
            toast("Case data restored to the original evidence.")
        elif a == "history":
            self.show_history()
        elif a == "history-item":
            h = self.store.data["history"][int(el.dataset.i)]
            self.close_overlay()
            if self.editor:
                self.editor.set(h["sql"], focus=True)
                self.on_editor_change(h["sql"])
        elif a == "close":
            self.close_overlay()
        elif a == "start-training":
            self.store.set("onboarded", True)
            self.close_overlay()
            self.go("#/case/case00_training/1")
        elif a == "skip-onboard":
            self.store.set("onboarded", True)
            self.close_overlay()
        elif a == "continue":
            self.go(f"#/case/{el.dataset.case}")
        elif a == "next-case":
            self.close_overlay()
            nxt = self.next_unsolved()
            self.go(f"#/case/{nxt[0]['id']}" if nxt else "#/")
        elif a == "cert-png":
            from reports import audit_certificate
            audit_certificate.download(self, "png")
        elif a == "cert-pdf":
            from reports import audit_certificate
            audit_certificate.download(self, "pdf")
        elif a == "reset-progress":
            if window.confirm("Erase all progress, drafts and history on this device?"):
                self.store.reset()
                self.close_overlay()
                self.update_home()
                toast("Progress erased.")

    def insert_name(self, name: str) -> None:
        if not self.editor:
            return
        if self.is_mobile():
            self.set_mtab("query")
        self.editor.insert(name)
        toast(f"Inserted {name}")

    def on_key(self, e) -> None:
        key = e.key
        tgt = nn(e.target)
        typing = tgt is not None and getattr(tgt, "tagName", "") in ("TEXTAREA", "INPUT")
        if key == "Escape":
            if qs("#overlay").innerHTML:
                self.close_overlay()
            elif self.case and qs("#workspace") is not None and qs("#workspace").getAttribute("data-evidence") == "open":
                self.set_evidence(False)
            return
        if key == "Tab" and qs("#overlay").innerHTML:
            self.trap_focus(e)
            return
        if tgt is not None and key in ("ArrowLeft", "ArrowRight", "Home", "End") and tgt.getAttribute("role") == "tab":
            tabs = list(tgt.parentElement.querySelectorAll('[role="tab"]'))
            i = next((k for k, t in enumerate(tabs) if t == tgt), 0)
            j = {"ArrowLeft": i - 1, "ArrowRight": i + 1, "Home": 0, "End": len(tabs) - 1}[key] % len(tabs)
            e.preventDefault()
            tabs[j].click()
            later(lambda: qs(f'.schema-tabs [data-tab="{tabs[j].dataset.tab}"]') and qs(f'.schema-tabs [data-tab="{tabs[j].dataset.tab}"]').focus(), 10)
            return
        if key in ("Enter", " ") and tgt is not None and tgt.getAttribute("data-insert") and getattr(tgt, "tagName", "").lower() != "button":
            e.preventDefault()          # keyboard access to ER diagram names (SVG text)
            self.insert_name(tgt.getAttribute("data-insert"))
            if qs("#overlay .erd-modal") is not None:
                self.close_overlay()
            return
        if self.case and (e.ctrlKey or e.metaKey) and key == "Enter" and not typing:
            e.preventDefault()
            self.run()
            return
        if e.altKey and not e.ctrlKey:
            k = (getattr(e, "code", "") or "").replace("Key", "").lower()
            if self.case and k == "h":
                e.preventDefault()
                self.reveal_hint()
            elif self.case and k == "n":
                e.preventDefault()
                self.next_level()
            elif self.case and k == "p":
                e.preventDefault()
                self.select_level(max(0, self.level_i - 1))
            elif k == "b":
                e.preventDefault()
                self.go("#/")
            elif self.case and k == "y":
                e.preventDefault()
                self.show_history()
            elif k == "t":
                e.preventDefault()
                theme_toggle.toggle()
            elif self.case and k == "e":
                e.preventDefault()
                if self.is_mobile():
                    self.set_mtab("schema")
                elif self.evidence_is_drawer():
                    self.set_evidence()
                else:
                    t = qs(".schema-tabs button[aria-selected='true']")
                    if t is not None:
                        t.focus()
            return
        if not typing and key == "?":
            self.show_shortcuts()
        elif not typing and key == "/" and self.editor and self.case:
            e.preventDefault()
            self.editor.focus_end()

    def trap_focus(self, e) -> None:
        """Keep Tab inside the open dialog or drawer."""
        box = qs("#overlay .modal") or qs("#overlay .drawer")
        if box is None:
            return
        items = [x for x in box.querySelectorAll('button, [href], input, textarea, select, [tabindex]:not([tabindex="-1"])')
                 if not x.hasAttribute("disabled") and x.offsetParent is not None]
        if not items:
            return
        first, last = items[0], items[-1]
        active = document.activeElement
        if e.shiftKey and (active == first or not box.contains(active)):
            e.preventDefault()
            last.focus()
        elif not e.shiftKey and (active == last or not box.contains(active)):
            e.preventDefault()
            first.focus()

    def back(self, *_args) -> str:
        """Android back button: close the top-most thing, then leave the case. Returns '1' if handled."""
        if qs("#overlay").innerHTML:
            self.close_overlay()
            return "1"
        ws = qs("#workspace")
        if ws is not None and ws.getAttribute("data-evidence") == "open":
            self.set_evidence(False)
            return "1"
        ac = qs("#ac-list")
        if ac is not None and not ac.hidden:
            ac.hidden = True
            return "1"
        if self.case is not None:
            if self.is_mobile() and ws is not None and ws.getAttribute("data-mtab") != "brief":
                self.set_mtab("brief")
                return "1"
            self.go("#/")
            return "1"
        return "0"

    def reveal_hint(self) -> None:
        lv = self.case["levels"][self.level_i]
        if self.store.hints(lv["id"]) >= len(lv["hints"]):
            return
        self.store.reveal_hint(lv["id"], len(lv["hints"]))
        self.render_finding()

    def next_level(self) -> None:
        if self.level_i < len(self.case["levels"]) - 1:
            self.select_level(self.level_i + 1)
            if self.is_mobile():
                self.set_mtab("brief")
                window.scrollTo(0, 0)

    # ================= overlays =================
    def overlay(self, html: str, label: str) -> None:
        box = qs("#overlay")
        box.innerHTML = (f'<div class="scrim" data-action="close"></div><div class="modal card" role="dialog" aria-modal="true" '
                         f'aria-label="{esc(label)}">{html}</div>')
        def focus():
            el = nn(box.querySelector(".modal [autofocus]")) or nn(box.querySelector(".modal button"))
            if el is not None:
                el.focus()
        later(focus, 20)

    def close_overlay(self) -> None:
        box = qs("#overlay")
        if box.innerHTML:
            box.innerHTML = ""
            if self.editor and self.case and not self.is_mobile():
                self.editor.ta.focus()

    def show_onboarding(self) -> None:
        self.overlay("""
<div class="eyebrow">Welcome, auditor</div>
<h2>Prove fraud with SQL. No server, no sign-up.</h2>
<p class="muted">Queryopsy runs a real SQLite database inside this page (Python compiled to WebAssembly). Everything stays on your device and works offline.</p>
<ol class="onboard-steps">
 <li><div><b>Read the dossier.</b> Every case is a real-world dataset with a story and a list of findings to prove.</div></li>
 <li><div><b>Explore the evidence room.</b> Browse tables or the ER diagram - click any name to insert it into the editor. Suggestions pop up as you type.</div></li>
 <li><div><b>Run and get a verdict.</b> <kbd>Ctrl</kbd>+<kbd>Enter</kbd> runs your query. You instantly see how many columns and rows match - never the answer itself.</div></li>
 <li><div><b>Stuck?</b> Hints unlock one at a time. Finish a case to download your audit certificate.</div></li>
</ol>
<div class="actions"><button class="btn" data-action="skip-onboard">Explore on my own</button>
<button class="btn btn-primary" data-action="start-training" autofocus>Start orientation</button></div>""", "Welcome")

    def show_shortcuts(self) -> None:
        rows = [("Run query", "<kbd>Ctrl</kbd>+<kbd>Enter</kbd> (<kbd>&#8984;</kbd>+<kbd>Enter</kbd> on Mac)"),
                ("Show suggestions", "<kbd>Ctrl</kbd>+<kbd>Space</kbd>"), ("Accept suggestion", "<kbd>Tab</kbd> or <kbd>Enter</kbd>"),
                ("Next hint", "<kbd>Alt</kbd>+<kbd>H</kbd>"), ("Next / previous finding", "<kbd>Alt</kbd>+<kbd>N</kbd> / <kbd>Alt</kbd>+<kbd>P</kbd>"),
                ("Query history", "<kbd>Alt</kbd>+<kbd>Y</kbd>"), ("Focus editor", "<kbd>/</kbd>"), ("Toggle theme", "<kbd>Alt</kbd>+<kbd>T</kbd>"),
                ("All cases", "<kbd>Alt</kbd>+<kbd>B</kbd>"), ("Evidence room", "<kbd>Alt</kbd>+<kbd>E</kbd>"), ("Close dialog", "<kbd>Esc</kbd>"), ("This list", "<kbd>?</kbd>")]
        body = "".join(f"<tr><td>{a}</td><td style='text-align:right'>{b}</td></tr>" for a, b in rows)
        self.overlay(f"""<h2>Keyboard shortcuts</h2><table class="shortcuts">{body}</table>
<div class="actions"><button class="btn btn-sm" data-action="reset-progress">Erase my progress</button>
<button class="btn" data-action="help">Show tutorial</button><button class="btn btn-primary" data-action="close" autofocus>Done</button></div>""", "Keyboard shortcuts")

    def show_history(self) -> None:
        items = []
        for i, h in enumerate(self.store.data["history"]):
            c = self.by_id.get(h["case"], {"title": h["case"]})
            when = time.strftime("%d %b %H:%M", time.localtime(h["at"]))
            items.append(f'<li><button data-action="history-item" data-i="{i}"><div class="meta"><span>{esc(c["title"])} &middot; {esc(h["outcome"])}</span>'
                         f'<span>{when}</span></div>{esc(h["sql"])}</button></li>')
        empty = '<p class="empty">No queries yet.</p>'
        qs("#overlay").innerHTML = (f'<div class="scrim" data-action="close"></div><aside class="drawer" role="dialog" aria-label="Query history">'
                                    f'<div class="panel-head"><h2>Query history</h2><button class="btn btn-sm" data-action="close" autofocus>Close</button></div>'
                                    f'<ol>{"".join(items) or empty}</ol></aside>')
        later(lambda: qs("#overlay .drawer button") and qs("#overlay .drawer button").focus(), 20)

    def show_case_closed(self) -> None:
        c = self.case
        hints = sum(self.store.hints(lv["id"]) for lv in c["levels"])
        self.overlay(f"""<div class="closed-stamp"><span class="stamp ok">Case closed</span></div>
<h2 style="margin-top:18px">{esc(c['title'])}</h2><p>All {len(c['levels'])} findings proven with SQL{', using ' + str(hints) + ' hint(s)' if hints else ' without a single hint'}.</p>
<div class="actions"><button class="btn" data-action="certificate">Audit certificate</button>
<button class="btn btn-primary" data-action="next-case" autofocus>Next case &rarr;</button></div>""", "Case closed")

    def show_certificate(self) -> None:
        from reports import audit_certificate
        name = self.store.get("name", "")
        self.overlay(f"""<span class="tag">Form QX-1 &middot; Official</span><h2 style="margin-top:12px">Forensic audit report</h2>
<p class="muted">Typed up on your device from your saved progress. Nothing is uploaded.</p>
<label class="field"><span><b>Lead investigator (name on report)</b></span><input id="cert-name" maxlength="40" value="{esc(name)}" placeholder="Your name" autocomplete="name"></label>
<canvas id="cert-canvas" class="cert-preview" width="1600" height="1130" role="img" aria-label="Forensic audit report preview"></canvas>
<div class="actions"><button class="btn" data-action="close">Close</button><button class="btn btn-secondary" data-action="cert-pdf">Download PDF</button>
<button class="btn btn-primary" data-action="cert-png">Download PNG</button></div>""", "Audit certificate")
        inp = qs("#cert-name")
        on(inp, "input", lambda e: (self.store.set("name", inp.value.strip()), audit_certificate.draw(self, qs("#cert-canvas"))))
        audit_certificate.draw(self, qs("#cert-canvas"))
        audit_certificate.when_fonts_ready(lambda: nn(qs("#cert-canvas")) and audit_certificate.draw(self, qs("#cert-canvas")))
