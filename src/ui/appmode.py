"""App mode: a native-feeling (iOS-style) shell for the Android app, installed PWAs and phones (<= 760 px).

Same engine, validator, editor and progress store as the website - only the chrome changes:
large-title navigation bars, a bottom tab bar, push/pop screens with an edge swipe-back gesture,
bottom sheets with a grabber, segmented controls, switches and haptic feedback.
"""
from __future__ import annotations

import asyncio

from js import Date, Object, document, window
from pyodide.ffi import to_js

from . import theme_toggle
from .app import App, exhibit
from .dom import closest, esc, later, nn, on, qs, toast

# screen name -> (family, depth, tab)
SCREENS = {
    "home": ("cases", 0, "cases"), "case": ("cases", 1, "cases"), "investigate": ("cases", 2, "investigate"),
    "evidence": ("evidence", 0, "evidence"), "progress": ("progress", 0, "progress"), "report": ("progress", 1, "progress"),
}
TILE = {"orange": "#C2410C", "purple": "#7E3FB0", "cyan": "#0E7490", "lime": "#2F7D4F"}


def _svg(body: str, size: int = 26, cls: str = "") -> str:
    return (f'<svg class="ic {cls}" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{body}</svg>')


IC = {
    "cases": _svg('<path class="fillable" d="M3 7.6C3 6.7 3.7 6 4.6 6h4.3l2.1 2.2h8.4c.9 0 1.6.7 1.6 1.6v8.6c0 .9-.7 1.6-1.6 1.6H4.6c-.9 0-1.6-.7-1.6-1.6z"/>'),
    "investigate": _svg('<circle class="fillable" cx="10.5" cy="10.5" r="6.2"/><path d="M15.2 15.2 20.5 20.5"/><path d="M8 10.5h5M10.5 8v5" stroke-width="1.6"/>'),
    "evidence": _svg('<rect class="fillable" x="3" y="4" width="18" height="5" rx="1.3"/><path d="M4.8 9v9.4c0 .9.7 1.6 1.6 1.6h11.2c.9 0 1.6-.7 1.6-1.6V9"/><path d="M10 13h4"/>'),
    "progress": _svg('<path d="M12 3a9 9 0 1 1-8.5 6"/><path class="fillable" d="M12 7v5l3.2 2"/>'),
    "back": _svg('<path d="M15 4.5 7.5 12 15 19.5"/>', 24, "chev"),
    "chev": _svg('<path d="M9.5 6 15.5 12l-6 6"/>', 16, "chev-r"),
    "play": _svg('<path d="M7 4.8v14.4L19 12z" fill="currentColor" stroke="none"/>', 16),
    "box": _svg('<rect x="3" y="4" width="18" height="5" rx="1.3"/><path d="M4.8 9v9.4c0 .9.7 1.6 1.6 1.6h11.2c.9 0 1.6-.7 1.6-1.6V9"/><path d="M10 13h4"/>', 22),
    "help": _svg('<circle cx="12" cy="12" r="8.5"/><path d="M9.6 9.6a2.5 2.5 0 1 1 3.4 2.3c-.6.3-1 .8-1 1.5v.4"/><circle cx="12" cy="16.6" r=".4" fill="currentColor"/>', 24),
    "clock": _svg('<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>', 22),
    "bulb": _svg('<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.6 10.8c.7.6 1.1 1.3 1.1 2.2h5c0-.9.4-1.6 1.1-2.2A6 6 0 0 0 12 3z"/>', 18),
    "folder": _svg('<path d="M3 7.6C3 6.7 3.7 6 4.6 6h4.3l2.1 2.2h8.4c.9 0 1.6.7 1.6 1.6v8.6c0 .9-.7 1.6-1.6 1.6H4.6c-.9 0-1.6-.7-1.6-1.6z" fill="currentColor" stroke="none"/>', 20),
    "check": _svg('<path d="m5 12.5 4.5 4.5L19 7.5"/>', 18),
    "doc": _svg('<path d="M7 3h7l5 5v11.5c0 .8-.7 1.5-1.5 1.5h-10C6.7 21 6 20.3 6 19.5v-15C6 3.7 6.7 3 7.5 3z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>', 22),
}


def _opts(**kw):
    return to_js(kw, dict_converter=Object.fromEntries)


def ring(done: int, total: int, size: int = 76, stroke: int = 8, label: bool = True) -> str:
    r = (size - stroke) / 2
    circ = 2 * 3.14159265 * r
    frac = done / total if total else 0
    text = (f'<text x="50%" y="50%" text-anchor="middle" dominant-baseline="central" class="ring-text">{round(100 * frac)}%</text>'
            if label else "")
    return (f'<svg class="ring" width="{size}" height="{size}" viewBox="0 0 {size} {size}" role="img" aria-label="{done} of {total} findings proven">'
            f'<circle cx="{size / 2}" cy="{size / 2}" r="{r:.2f}" class="ring-track" stroke-width="{stroke}" fill="none"/>'
            f'<circle cx="{size / 2}" cy="{size / 2}" r="{r:.2f}" class="ring-fill" stroke-width="{stroke}" fill="none" stroke-linecap="round" '
            f'stroke-dasharray="{circ * frac:.2f} {circ:.2f}" transform="rotate(-90 {size / 2} {size / 2})"/>{text}</svg>')


class IOSApp(App):
    """App-mode controller. Inherits all case logic from App and replaces the page chrome."""

    def __init__(self, data: dict):
        super().__init__(data)
        self.screen = None
        self.hist: list[str] = []
        self.sheet_kind = None
        self._skip_anim = False
        self._collapsed: dict[str, bool] = {}
        self._swipe = None
        self._drag = None

    # ================= lifecycle =================
    def start(self) -> None:
        self.build_shell()
        super().start()
        on(document, "focusin", self.on_focus_in)
        on(document, "focusout", self.on_focus_out)
        stack = qs("#stack")
        on(stack, "pointerdown", self.swipe_start)
        on(window, "pointermove", self.on_pointer_move, _opts(passive=True))
        on(window, "pointerup", self.on_pointer_up)
        on(window, "pointercancel", self.on_pointer_up)
        vv = nn(getattr(window, "visualViewport", None))
        if vv is not None:
            on(vv, "resize", lambda e: self.sync_keyboard_offset())
        theme_toggle.watch_system(self.on_theme_changed)
        self.apply_prefs()
        splash = qs("#splash")
        if splash is not None:
            splash.classList.add("gone")
            later(lambda: splash.remove(), 450)

    def build_shell(self) -> None:
        tabs = [("cases", "Cases"), ("investigate", "Investigate"), ("evidence", "Evidence"), ("progress", "Progress")]
        tabbar = "".join(f'<button class="tab" data-action="tab" data-tab="{k}" aria-label="{v}">{IC[k]}<span>{v}</span></button>'
                         for k, v in tabs)
        screens = "".join(f'<section class="screen" data-screen="{k}" id="scr-{k}" inert></section>' for k in SCREENS)
        tokens = ["SELECT", "FROM", "WHERE", "JOIN", "ON", "GROUP BY", "HAVING", "ORDER BY", "COUNT(*)", "AS", "AND", "LIMIT", "*", "=", "'", ",", "(", ")", ";"]
        keys = "".join(f'<button class="kb-key" data-action="kb-insert" data-t="{esc(t)}" tabindex="-1">{esc(t)}</button>' for t in tokens)
        shell = document.createElement("div")
        shell.id = "ios"
        shell.className = "ios"
        shell.innerHTML = f"""
<div class="stack" id="stack">{screens}</div>
<div class="kbbar" id="kbbar" aria-label="SQL keyboard shortcuts">
  <div class="kb-keys">{keys}</div>
  <button class="kb-run" data-action="run" tabindex="-1" aria-label="Run query">{IC['play']}<span>Run</span></button>
</div>
<nav class="tabbar" id="tabbar" aria-label="Main">{tabbar}</nav>
<div class="sheet-host" id="sheet-host" hidden>
  <div class="sheet-scrim" data-action="sheet-close"></div>
  <section class="sheet" id="sheet" role="dialog" aria-modal="true" aria-labelledby="sheet-title" data-detent="large">
    <div class="sheet-head" id="sheet-head"><span class="grabber" aria-hidden="true"></span>
      <h2 id="sheet-title">Sheet</h2><button class="nav-btn" data-action="sheet-close">Done</button></div>
    <div class="sheet-body" id="sheet-body"></div>
  </section>
</div>"""
        document.body.insertBefore(shell, qs("#overlay"))
        for k in SCREENS:
            scr = qs(f"#scr-{k}")
            on(scr, "scroll", lambda e, k=k: self.on_scroll(k), _opts(passive=True, capture=True))
        kb = qs("#kbbar")
        on(kb, "pointerdown", lambda e: e.preventDefault())          # keep the editor (and keyboard) focused
        on(kb, "mousedown", lambda e: e.preventDefault())
        sh = qs("#sheet-head")
        on(sh, "pointerdown", self.sheet_drag_start)

    # ================= screens & navigation =================
    def screen_html(self, name: str, title: str, body: str, back: str = "", actions: str = "", large: bool = True) -> str:
        back_btn = (f'<button class="nav-back" data-action="nav-back" aria-label="Back to {esc(back)}">{IC["back"]}<span>{esc(back)}</span></button>'
                    if back else "")
        lt = f'<h1 class="large-title">{esc(title)}</h1>' if large else ""
        return (f'<header class="nav{"" if large else " inline"}"><div class="nav-row"><div class="nav-l">{back_btn}</div>'
                f'<h2 class="nav-title">{esc(title)}</h2><div class="nav-r">{actions}</div></div></header>'
                f'<div class="scroller" data-scroller="{name}">{lt}{body}</div>')

    def set_screen_html(self, name: str, html: str) -> None:
        qs(f"#scr-{name}").innerHTML = html
        self._collapsed[name] = None
        self.on_scroll(name)

    def on_scroll(self, name: str) -> None:
        scr = qs(f"#scr-{name}")
        sc = nn(scr.querySelector(".scroller")) if scr is not None else None
        nav = nn(scr.querySelector(".nav")) if scr is not None else None
        if sc is None or nav is None:
            return
        lt = nn(sc.querySelector(".large-title"))
        limit = (lt.offsetTop + lt.offsetHeight - nav.offsetHeight) if lt is not None else 0
        col = sc.scrollTop > max(4, limit)
        if self._collapsed.get(name) != col:
            self._collapsed[name] = col
            nav.classList.toggle("collapsed", col)

    def show_screen(self, name: str) -> None:
        old = self.screen
        new_el = qs(f"#scr-{name}")
        if old == name:
            new_el.classList.add("is-active")
            new_el.removeAttribute("inert")
            self.update_tabbar()
            return
        old_el = qs(f"#scr-{old}") if old else None
        self.screen = name
        fam_n, dep_n, _ = SCREENS[name]
        mode = "fade"
        if old and SCREENS[old][0] == fam_n and SCREENS[old][1] != dep_n:
            mode = "push" if dep_n > SCREENS[old][1] else "pop"
        reduced = bool(window.matchMedia("(prefers-reduced-motion: reduce)").matches)
        if self._skip_anim or reduced or old_el is None:
            mode = "none"
        self._skip_anim = False
        for el in document.querySelectorAll(".screen"):
            el.classList.remove("anim-in-push", "anim-out-push", "anim-in-pop", "anim-out-pop", "peek", "swiping")
            el.style.transform = ""
        new_el.classList.add("is-active")
        new_el.removeAttribute("inert")
        if old_el is not None:
            old_el.classList.remove("is-active")
            old_el.setAttribute("inert", "")
            if mode in ("push", "pop"):
                new_el.classList.add(f"anim-in-{mode}")
                old_el.classList.add(f"anim-out-{mode}")

                def done(a=new_el, b=old_el, m=mode):
                    a.classList.remove(f"anim-in-{m}")
                    b.classList.remove(f"anim-out-{m}")
                later(done, 420)
        self.update_tabbar()
        later(lambda: self.on_scroll(name), 30)

    def update_tabbar(self) -> None:
        tab = SCREENS.get(self.screen, ("", 0, "cases"))[2]
        for b in document.querySelectorAll("#tabbar .tab"):
            on_ = b.dataset.tab == tab
            b.classList.toggle("on", on_)
            if on_:
                b.setAttribute("aria-current", "page")
            else:
                b.removeAttribute("aria-current")

    def go(self, hash_: str) -> None:
        if window.location.hash == hash_:
            asyncio.ensure_future(self.route())
        else:
            window.location.hash = hash_

    def parent_hash(self) -> str | None:
        if self.screen == "investigate" and self.case:
            return f"#/case/{self.case['id']}"
        if self.screen == "case":
            return "#/"
        if self.screen == "report":
            return "#/progress"
        return None

    def nav_back(self, animate: bool = True) -> None:
        parent = self.parent_hash()
        if parent is None:
            return
        self._skip_anim = not animate
        if len(self.hist) >= 2 and self.hist[-2] == parent:
            window.history.back()
        else:
            window.location.replace(window.location.href.split("#")[0] + parent)

    async def route(self) -> None:
        h = window.location.hash or "#/"
        if not self.hist or self.hist[-1] != h:
            if len(self.hist) >= 2 and self.hist[-2] == h:
                self.hist.pop()
            else:
                self.hist.append(h)
                self.hist = self.hist[-50:]
        parts = [p for p in h.lstrip("#").split("/") if p]
        if self.sheet_kind:
            self.close_sheet()
        if len(parts) >= 2 and parts[0] == "case" and parts[1] in self.by_id:
            n = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
            ok = await self.open_case(parts[1], n)
            if not ok:
                return
            target = "investigate" if n is not None else "case"
            if target == "case":
                self.refresh_case_screen()
        elif parts[:1] == ["evidence"]:
            self.render_evidence_screen()
            target = "evidence"
        elif parts[:1] == ["progress"]:
            if parts[1:2] == ["report"]:
                self.render_report()
                target = "report"
            else:
                self.render_progress()
                target = "progress"
        else:
            self.render_home()
            target = "home"
        document.title = {"home": "Queryopsy", "progress": "Progress - Queryopsy", "report": "Audit report - Queryopsy",
                          "evidence": "Evidence - Queryopsy"}.get(target, f"{self.case['title']} - Queryopsy" if self.case else "Queryopsy")
        self.show_screen(target)

    # ================= home =================
    def show_home(self, scroll: bool = True) -> None:
        self.go("#/")

    def update_home(self) -> None:
        self.update_pill()
        if self.screen in (None, "home"):
            self.render_home()
        if self.screen == "progress":
            self.render_progress()

    def update_pill(self) -> None:
        super().update_pill()
        if self.case is not None and qs("#exhibit-list") is not None:
            self.render_exhibit_list()

    def case_row(self, c: dict, action: str = "open-case") -> str:
        d, t = self.case_progress(c)
        tile = TILE.get(c.get("accent", "orange"), "#C2410C")
        end = ('<span class="pill ok">Closed</span>' if d == t else f'<span class="pill">{d}/{t}</span>')
        return (f'<li><button class="row" data-action="{action}" data-case="{c["id"]}" aria-label="Case {c["no"]:02d}: {esc(c["title"])}, {d} of {t} findings proven">'
                f'<span class="tile" style="--tile:{tile}">{IC["folder"]}<b>{c["no"]:02d}</b></span>'
                f'<span class="row-main"><span class="row-title">{esc(c["title"])}</span>'
                f'<span class="row-sub">{esc(c["industry"])} &middot; {esc(c["difficulty"])}</span>'
                f'<span class="mini-bar" aria-hidden="true"><i style="width:{100 * d / max(t, 1):.0f}%"></i></span></span>'
                f'<span class="row-end">{end}{IC["chev"]}</span></button></li>')

    def render_home(self) -> None:
        d, t = self.total_progress()
        closed = sum(1 for c in self.cases if self.case_progress(c)[0] == self.case_progress(c)[1])
        hour = int(Date.new().getHours())
        greet = "Good morning" if hour < 12 else ("Good afternoon" if hour < 17 else "Good evening")
        name = (self.store.get("name") or "").strip().split(" ")[0] or "Investigator"
        nxt = self.next_unsolved()
        if nxt is None:
            cont = ('<div class="hero-card done"><span class="eyebrow">All cases closed</span><h3>Every finding proven</h3>'
                    '<p>Your forensic audit report is ready.</p><button class="btn-ios filled" data-action="report">View report</button></div>')
        else:
            c, lv = nxt
            i = c["levels"].index(lv)
            started = d > 0
            cont = (f'<button class="hero-card" data-action="resume" data-case="{c["id"]}" data-n="{i + 1}">'
                    f'<span class="eyebrow">{"Continue investigation" if started else "Your first case"}</span>'
                    f'<span class="hero-title">{esc(c["title"])}</span>'
                    f'<span class="hero-sub"><span class="tag">Exhibit {exhibit(i)}</span> {esc(lv["title"])}</span>'
                    f'<span class="btn-ios filled as-span">{IC["play"]} {"Resume" if started else "Start"}</span>'
                    f'<span class="stamp-ghost" aria-hidden="true">Confidential</span></button>')
        rows = "".join(self.case_row(c) for c in self.cases)
        body = f"""
<div class="summary card-ios">
  {ring(d, t)}
  <div class="summary-text"><p class="greet">{greet}, {esc(name)}.</p>
  <p class="muted">{d} of {t} findings proven &middot; {closed} of {len(self.cases)} cases closed</p></div>
</div>
{cont}
<h3 class="group-head">Case files</h3>
<ul class="group list cases-list">{rows}</ul>
<p class="group-foot">Progress is saved on this device. Everything runs offline.</p>"""
        actions = f'<button class="nav-icon" data-action="help" aria-label="How it works">{IC['help']}</button>'
        self.set_screen_html("home", self.screen_html("home", "Cases", body, actions=actions))

    # ================= case =================
    async def open_case(self, case_id: str, n: int | None) -> bool:
        case = self.by_id[case_id]
        if self.case is case and n is None:     # back on the case screen: keep the exhibit the player was on
            self.render_exhibit_list()
            return True
        if self.case is not case:
            self.set_screen_html("case", self.screen_html("case", case["title"], '<div class="loading"><span class="spinner"></span>Opening the evidence room&hellip;</div>', back="Cases"))
            if self.screen != "case":
                self.show_screen("case")
            try:
                self.db = await self.load_db(case)
            except Exception as e:  # noqa: BLE001
                self.set_screen_html("case", self.screen_html("case", case["title"], f'<div class="card-ios error"><b>Could not open this case.</b> {esc(e)}</div>', back="Cases"))
                return False
            self.case = case
            self.render_case()
        levels = case["levels"]
        if n is None:
            n = next((i + 1 for i, lv in enumerate(levels) if not self.store.solved(lv["id"])), 1)
            self.select_level(max(0, min(len(levels) - 1, n - 1)), keep_hash=True)
        else:
            self.select_level(max(0, min(len(levels) - 1, n - 1)))
        return True

    def render_case(self) -> None:
        c = self.case
        schema = {t["name"]: [col["name"] for col in t["columns"]] for t in c["tables"]}
        src = c["source"]
        chip = '<span class="chip-ios warn">Placeholder data</span>' if src.get("placeholder") else '<span class="chip-ios ok">Real dataset</span>'
        brief = "".join(f"<p>{esc(p)}</p>" for p in c["brief"])
        tile = TILE.get(c.get("accent", "orange"), "#C2410C")
        body = f"""
<div class="case-head">
  <span class="tile big" style="--tile:{tile}">{IC['folder']}<b>{c['no']:02d}</b></span>
  <div><span class="eyebrow">Case {c['no']:02d} &middot; {esc(c['industry'])}</span>
  <span class="fileref">File no. QX/{c['no']:02d}/{len(c['levels'])} &middot; {esc(c['client'])}</span>
  <span class="chips"><span class="chip-ios">{esc(c['difficulty'])}</span>{chip}</span></div>
</div>
<div class="card-ios brief-card"><div class="brief collapsed" id="brief">{brief}</div>
  <button class="linkish" data-action="brief-toggle" id="brief-toggle" hidden>Read full brief</button></div>
<h3 class="group-head">Exhibits to prove</h3>
<ul class="group list" id="exhibit-list"></ul>
<ul class="group list">
  <li><button class="row" data-action="tab" data-tab="evidence"><span class="tile sm" style="--tile:#5B6B7F">{IC['box']}</span>
    <span class="row-main"><span class="row-title">Evidence room</span><span class="row-sub">{len(c['tables'])} tables &middot; ER diagram</span></span><span class="row-end">{IC['chev']}</span></button></li>
  <li><button class="row" data-action="history"><span class="tile sm" style="--tile:#6B5B7F">{IC['clock']}</span>
    <span class="row-main"><span class="row-title">Query history</span><span class="row-sub">Your last 40 queries</span></span><span class="row-end">{IC['chev']}</span></button></li>
</ul>
<div class="cta-wrap"><button class="btn-ios filled block" data-action="investigate">{IC['play']} Investigate</button></div>"""
        self.set_screen_html("case", self.screen_html("case", c["title"], body, back="Cases"))
        actions = (f'<button class="nav-icon" data-action="evidence" aria-label="Open the evidence room" aria-controls="sheet">{IC["box"]}</button>'
                   f'<button class="nav-icon" data-action="history" aria-label="Query history">{IC["clock"]}</button>')
        inv = f"""
<nav class="ex-strip stepper" id="stepper" aria-label="Exhibits"></nav>
<div id="finding"></div>
<div class="card-ios editor-card">
  <div class="editor" id="editor">
    <div class="gutter" aria-hidden="true">1</div>
    <pre aria-hidden="true"></pre>
    <textarea id="sql" spellcheck="false" autocapitalize="off" autocomplete="off" autocorrect="off" wrap="soft"
      aria-label="SQL editor" role="combobox" aria-autocomplete="list" aria-controls="ac-list" aria-expanded="false"></textarea>
    <ul class="ac" id="ac-list" role="listbox" aria-label="Suggestions" hidden></ul>
  </div>
  <div class="editor-actions">
    <button class="btn-ios filled" data-action="run" id="run-btn">{IC['play']} Run</button>
    <button class="btn-ios tinted" data-action="evidence" aria-controls="sheet">{IC['box']} Tables</button>
    <span class="spacer"></span>
    <button class="btn-ios plain" data-action="reset-editor">Clear</button>
    <button class="btn-ios plain" data-action="reset-data" aria-label="Reset data">Reset</button>
  </div>
</div>
<div class="card-ios results" id="results" aria-live="polite"></div>"""
        self.set_screen_html("investigate", self.screen_html("investigate", "Exhibit A", inv, back="Case", actions=actions, large=False))
        self.render_evidence_screen()
        self.editor = Editor(qs("#editor"), schema, self.run, self.on_editor_change)

    def refresh_case_screen(self) -> None:
        if self.case is not None:
            self.render_exhibit_list()

    def render_exhibit_list(self) -> None:
        box = qs("#exhibit-list")
        if box is None or self.case is None:
            return
        out = []
        for i, lv in enumerate(self.case["levels"]):
            done = self.store.solved(lv["id"])
            status = '<span class="pill ok">Proven</span>' if done else ('<span class="pill cur">Open</span>' if i == self.level_i else "")
            out.append(f'<li><button class="row" data-action="open-level" data-n="{i}" aria-label="Exhibit {exhibit(i)}: {esc(lv["title"])}{", proven" if done else ""}">'
                       f'<span class="ex-tag{" done" if done else ""}">{IC["check"] if done else exhibit(i)}</span>'
                       f'<span class="row-main"><span class="row-title">{esc(lv["title"])}</span><span class="row-sub">{esc(", ".join(lv["concepts"][:3]))}</span></span>'
                       f'<span class="row-end">{status}{IC["chev"]}</span></button></li>')
        box.innerHTML = "".join(out)

    def select_level(self, i: int, keep_hash: bool = False) -> None:
        super().select_level(i)
        res = qs("#results")
        if res is not None:
            res.innerHTML = '<div class="empty"><b>No verdict yet</b>Write a query and tap Run.</div>'
        t = qs("#scr-investigate .nav-title")
        if t is not None:
            t.textContent = f"Exhibit {exhibit(i)}"
        back = qs("#scr-investigate .nav-back span")
        if back is not None and self.case:
            back.textContent = self.case["title"] if len(self.case["title"]) <= 16 else "Case"
        self.render_exhibit_list()
        if keep_hash:
            want = f"#/case/{self.case['id']}"
            if window.location.hash != want:
                window.history.replaceState(None, "", want)
                if self.hist:
                    self.hist[-1] = want
        elif self.hist and self.hist[-1].startswith("#/case/"):
            self.hist[-1] = window.location.hash

    def render_finding(self) -> None:
        c, lv = self.case, self.case["levels"][self.level_i]
        n_h, total_h = self.store.hints(lv["id"]), len(lv["hints"])
        solved = self.store.solved(lv["id"])
        last = self.level_i == len(c["levels"]) - 1
        story = f'<p class="story">{esc(lv["story"])}</p>' if lv.get("story") else ""
        concepts = "".join(f'<span class="chip-ios">{esc(x)}</span>' for x in lv["concepts"])
        nxt = ""
        if solved:
            nxt = (f'<button class="btn-ios filled" data-action="next">Next exhibit {IC["chev"]}</button>' if not last else
                   '<button class="btn-ios filled" data-action="report">View report</button>')
        stamp = '<span class="stamp ok mini" aria-hidden="true">Solved</span>' if solved else ""
        hint_label = f"Hints {n_h}/{total_h}" if n_h else "Need a hint?"
        qs("#finding").innerHTML = f"""
<div class="card-ios task-card">
  <div class="task-top"><span class="tag">Exhibit {exhibit(self.level_i)}</span><span class="muted sm">Finding {self.level_i + 1} of {len(c['levels'])}</span>{stamp}</div>
  <h2 class="task-title">{esc(lv['title'])}</h2>{story}
  <p class="task-text">{esc(lv['task'])}</p>
  <div class="chips" aria-label="SQL concepts">{concepts}</div>
  <div class="task-actions"><button class="btn-ios tinted" data-action="hints-sheet">{IC['bulb']} {hint_label}</button>{nxt}</div>
  {'<div class="solved-banner sr-only">Exhibit ' + exhibit(self.level_i) + ' proven</div>' if solved else ''}
</div>"""
        if self.sheet_kind == "hints":
            self.render_hints_sheet()

    def next_level(self) -> None:
        if self.level_i < len(self.case["levels"]) - 1:
            self.select_level(self.level_i + 1)
            sc = qs("#scr-investigate .scroller")
            if sc is not None:
                sc.scrollTo(_opts(top=0, behavior="smooth"))

    # ================= evidence =================
    def render_evidence_screen(self) -> None:
        if self.case is None:
            nxt = self.next_unsolved() or (self.cases[0], self.cases[0]["levels"][0])
            body = (f'<div class="empty-state">{IC["box"]}<h3>No case open</h3><p>Open a case file to examine its tables and ER diagram.</p>'
                    f'<button class="btn-ios filled" data-action="resume" data-case="{nxt[0]["id"]}" data-n="{nxt[0]["levels"].index(nxt[1]) + 1}">Open {esc(nxt[0]["title"])}</button></div>')
            self.set_screen_html("evidence", self.screen_html("evidence", "Evidence", body))
            return
        if qs("#evidence-block") is not None and qs(f'#evidence-block[data-case="{self.case["id"]}"]') is not None:
            return
        body = f"""<p class="sub-title">{esc(self.case['title'])} &middot; {len(self.case['tables'])} tables</p>
<div id="evidence-slot"><div class="evidence-block" id="evidence-block" data-case="{self.case['id']}">
  <div class="segmented schema-tabs" role="tablist" aria-label="Evidence view">
    <button role="tab" id="tab-tables" data-action="schema-tab" data-tab="tables" aria-selected="true" aria-controls="schema">Tables</button>
    <button role="tab" id="tab-diagram" data-action="schema-tab" data-tab="diagram" aria-selected="false" aria-controls="schema" tabindex="-1">ER diagram</button>
  </div>
  <div class="schema" id="schema" role="tabpanel" aria-labelledby="tab-tables"></div>
</div></div>"""
        self.set_screen_html("evidence", self.screen_html("evidence", "Evidence", body))
        self.render_schema()

    def set_evidence(self, open_: bool | None = None) -> None:
        if open_ is None:
            open_ = self.sheet_kind != "evidence"
        if open_:
            self.open_sheet("evidence")
        elif self.sheet_kind == "evidence":
            self.close_sheet()

    def evidence_is_drawer(self) -> bool:
        return False

    def is_mobile(self) -> bool:
        return True

    def set_mtab(self, tab: str) -> None:
        if tab == "schema":
            self.open_sheet("evidence")
            return
        if self.sheet_kind:
            self.close_sheet()
        if self.case is None:
            return
        if tab == "query" and self.screen != "investigate":
            self.go(f"#/case/{self.case['id']}/{self.level_i + 1}")
        elif tab == "brief" and self.screen != "case":
            self.go(f"#/case/{self.case['id']}")
        if tab == "query" and self.editor is not None:
            later(self.editor.refresh, 60)

    # ================= sheets =================
    def open_sheet(self, kind: str) -> None:
        if self.case is None and kind in ("evidence", "hints", "history"):
            if kind != "history":
                return
        host, body = qs("#sheet-host"), qs("#sheet-body")
        self.restore_evidence_block()          # never destroy the evidence block when another sheet replaces it
        self.sheet_kind = kind
        sheet = qs("#sheet")
        sheet.style.transform = ""
        if kind == "evidence":
            self.render_evidence_screen()
            blk = qs("#evidence-block")
            body.innerHTML = ""
            body.appendChild(blk)
            title, detent = f"Evidence &middot; {esc(self.case['title'])}", "large"
        elif kind == "hints":
            title, detent = "Hints", "medium"
            self.render_hints_sheet()
        else:
            title, detent = "Query history", "large"
            self.render_history_sheet()
        qs("#sheet-title").innerHTML = title
        sheet.setAttribute("data-detent", detent)
        host.hidden = False
        host.classList.remove("open")
        later(lambda: host.classList.add("open"), 16)
        qs("#ios").classList.add("sheet-open")
        later(lambda: nn(qs("#sheet .nav-btn")) and qs("#sheet .nav-btn").focus(), 80)
        self.haptic()

    def restore_evidence_block(self) -> None:
        blk, slot = qs("#evidence-block"), qs("#evidence-slot")
        if blk is not None and slot is not None and blk.parentElement != slot:
            slot.appendChild(blk)

    def close_sheet(self) -> None:
        host = qs("#sheet-host")
        if host is None or not self.sheet_kind:
            return
        kind = self.sheet_kind
        self.sheet_kind = None
        host.classList.remove("open")
        qs("#ios").classList.remove("sheet-open")

        def fin():
            if self.sheet_kind is None:
                host.hidden = True
                self.restore_evidence_block()
                qs("#sheet-body").innerHTML = ""
                qs("#sheet").style.transform = ""
        later(fin, 320)

    def render_hints_sheet(self) -> None:
        lv = self.case["levels"][self.level_i]
        n_h, total = self.store.hints(lv["id"]), len(lv["hints"])
        items = []
        for k in range(n_h):
            label = "Answer walkthrough" if k == total - 1 else f"Hint {k + 1}"
            body = f"<code>{esc(lv['hints'][k])}</code>" if k == total - 1 else esc(lv["hints"][k])
            items.append(f'<li class="hint"><b>{label}</b><div>{body}</div></li>')
        more = ""
        if n_h < total:
            label = "Show the answer walkthrough" if n_h == total - 1 else f"Reveal hint {n_h + 1} of {total}"
            more = f'<button class="btn-ios filled block" data-action="hint">{IC["bulb"]} {label}</button>'
        intro = ("<p class=\"muted\">Hints unlock one at a time. Using them is fine - they are noted on your report.</p>" if not n_h else "")
        qs("#sheet-body").innerHTML = (f'<div class="sheet-pad">{intro}<ul class="group list hints-list">{"".join(items)}</ul>{more}</div>'
                                       if items else f'<div class="sheet-pad">{intro}{more}</div>')

    def render_history_sheet(self) -> None:
        import time
        items = []
        for i, h in enumerate(self.store.data["history"]):
            c = self.by_id.get(h["case"], {"title": h["case"]})
            when = time.strftime("%d %b %H:%M", time.localtime(h["at"]))
            items.append(f'<li><button class="row hist" data-action="history-item" data-i="{i}"><span class="row-main">'
                         f'<span class="row-sub">{esc(c["title"])} &middot; {esc(h["outcome"])} &middot; {when}</span>'
                         f'<code class="hist-sql">{esc(h["sql"])}</code></span></button></li>')
        qs("#sheet-body").innerHTML = (f'<div class="sheet-pad"><ul class="group list">{"".join(items)}</ul></div>' if items else
                                       f'<div class="empty-state">{IC["clock"]}<h3>No queries yet</h3><p>Every query you run is kept here on this device.</p></div>')

    def show_history(self) -> None:
        self.open_sheet("history")

    def reveal_hint(self) -> None:
        super().reveal_hint()
        self.haptic()

    # sheet drag (grabber / header): drag down to dismiss, up to expand
    def sheet_drag_start(self, e) -> None:
        if closest(e.target, "button"):
            return
        self._drag = {"y0": e.clientY, "t0": Date.now(), "dy": 0}
        qs("#sheet").classList.add("dragging")

    # ================= edge swipe back =================
    def swipe_start(self, e) -> None:
        if self.screen is None or SCREENS[self.screen][1] == 0 or e.clientX > 22 or self.sheet_kind:
            return
        parent_name = {"investigate": "case", "case": "home", "report": "progress"}.get(self.screen)
        if parent_name is None:
            return
        cur, par = qs(f"#scr-{self.screen}"), qs(f"#scr-{parent_name}")
        self._swipe = {"x0": e.clientX, "t0": Date.now(), "dx": 0, "cur": cur, "par": par, "w": max(1, window.innerWidth)}
        par.classList.add("peek")
        cur.classList.add("swiping")
        par.classList.add("swiping")

    def on_pointer_move(self, e) -> None:
        if self._swipe is not None:
            s = self._swipe
            s["dx"] = max(0, e.clientX - s["x0"])
            s["cur"].style.transform = f"translateX({s['dx']}px)"
            s["par"].style.transform = f"translateX({-0.28 * s['w'] + 0.28 * s['dx']}px)"
        elif self._drag is not None:
            d = self._drag
            d["dy"] = e.clientY - d["y0"]
            qs("#sheet").style.transform = f"translateY({max(-40, d['dy'])}px)"

    def on_pointer_up(self, e) -> None:
        if self._swipe is not None:
            s, self._swipe = self._swipe, None
            v = s["dx"] / max(1, Date.now() - s["t0"])
            cur, par = s["cur"], s["par"]
            cur.classList.remove("swiping")
            par.classList.remove("swiping")
            if s["dx"] > s["w"] * 0.33 or (v > 0.45 and s["dx"] > 40):
                cur.classList.add("settle")
                par.classList.add("settle")
                cur.style.transform = "translateX(100%)"
                par.style.transform = "translateX(0)"

                def finish():
                    cur.classList.remove("settle")
                    par.classList.remove("settle")
                    self.nav_back(animate=False)
                later(finish, 230)
            else:
                cur.classList.add("settle")
                par.classList.add("settle")
                cur.style.transform = ""
                par.style.transform = ""

                def reset():
                    cur.classList.remove("settle")
                    par.classList.remove("settle", "peek")
                later(reset, 260)
        elif self._drag is not None:
            d, self._drag = self._drag, None
            sheet = qs("#sheet")
            sheet.classList.remove("dragging")
            v = d["dy"] / max(1, Date.now() - d["t0"])
            sheet.style.transform = ""
            if d["dy"] > 110 or v > 0.6:
                if sheet.getAttribute("data-detent") == "large" and d["dy"] < 260 and v <= 0.6 and self.sheet_kind == "evidence":
                    sheet.setAttribute("data-detent", "medium")
                else:
                    self.close_sheet()
            elif d["dy"] < -40:
                sheet.setAttribute("data-detent", "large")

    # ================= progress / report =================
    def render_progress(self) -> None:
        d, t = self.total_progress()
        closed = sum(1 for c in self.cases if self.case_progress(c)[0] == self.case_progress(c)[1])
        solved = [lv["id"] for c in self.cases for lv in c["levels"] if self.store.solved(lv["id"])]
        hints = sum(self.store.hints(x) for x in solved)
        queries = len(self.store.data["history"])
        rows = "".join(self.case_row(c, "open-case") for c in self.cases)
        pref = theme_toggle.pref()
        seg = "".join(f'<button role="radio" aria-checked="{"true" if pref == k else "false"}" data-action="theme-pref" data-pref="{k}">{v}</button>'
                      for k, v in (("system", "System"), ("light", "Light"), ("dark", "Dark")))

        def switch(key, label, sub, default=True):
            val = self.store.get(key, default)
            return (f'<li><div class="row switch-row"><span class="row-main"><span class="row-title" id="lbl-{key}">{label}</span>'
                    f'<span class="row-sub">{sub}</span></span><button class="switch" role="switch" aria-checked="{"true" if val else "false"}" '
                    f'aria-labelledby="lbl-{key}" data-action="switch" data-key="{key}"><i></i></button></div></li>')
        meta = qs('meta[name="app-version"]')
        version = meta.getAttribute("content") if meta is not None else ""
        body = f"""
<div class="card-ios stats-card">
  {ring(d, t, 112, 11)}
  <div class="stats-grid">
    <div><b>{d}<small>/{t}</small></b><span>Findings proven</span></div>
    <div><b>{closed}<small>/{len(self.cases)}</small></b><span>Cases closed</span></div>
    <div><b>{hints}</b><span>Hints used</span></div>
    <div><b>{queries}</b><span>Queries logged</span></div>
  </div>
</div>
<h3 class="group-head">Report</h3>
<ul class="group list"><li><button class="row" data-action="report"><span class="tile sm" style="--tile:#B3261E">{IC['doc']}</span>
  <span class="row-main"><span class="row-title">Forensic audit report</span><span class="row-sub">Official record of your proven findings (PDF / PNG)</span></span>
  <span class="row-end">{IC['chev']}</span></button></li></ul>
<h3 class="group-head">Case files</h3>
<ul class="group list cases-list">{rows}</ul>
<h3 class="group-head">Appearance</h3>
<div class="group pad"><div class="segmented" role="radiogroup" aria-label="Appearance">{seg}</div></div>
<h3 class="group-head">Preferences</h3>
<ul class="group list">
  {switch("haptics", "Haptic feedback", "Gentle taps on run, verdicts and tabs")}
  {switch("lines", "Line numbers", "Show line numbers in the SQL editor")}
  <li><button class="row" data-action="help"><span class="row-main"><span class="row-title">Show tutorial</span></span><span class="row-end">{IC['chev']}</span></button></li>
</ul>
<ul class="group list"><li><button class="row destructive" data-action="reset-progress"><span class="row-main"><span class="row-title">Erase all progress</span></span></button></li></ul>
<p class="group-foot">Queryopsy {esc(version)} &middot; Python {esc(self.data.get('python', ''))} + SQLite on this device &middot; no account, no network.</p>"""
        self.set_screen_html("progress", self.screen_html("progress", "Progress", body))

    def show_certificate(self) -> None:
        self.go("#/progress/report")

    def render_report(self) -> None:
        from reports import audit_certificate
        name = self.store.get("name", "")
        body = f"""
<ul class="group list"><li><label class="row field-row"><span class="row-title">Investigator</span>
  <input id="cert-name" maxlength="40" value="{esc(name)}" placeholder="Your name" autocomplete="name" enterkeyhint="done"></label></li></ul>
<p class="group-foot">Typed up on your device from your saved progress. Nothing is uploaded.</p>
<div class="cert-wrap"><canvas id="cert-canvas" class="cert-preview" width="1600" height="1130" role="img" aria-label="Forensic audit report preview"></canvas></div>
<div class="btn-row"><button class="btn-ios filled" data-action="cert-pdf">Save PDF</button><button class="btn-ios tinted" data-action="cert-png">Save PNG</button></div>"""
        self.set_screen_html("report", self.screen_html("report", "Audit Report", body, back="Progress", large=False))
        inp, cv = qs("#cert-name"), qs("#cert-canvas")
        on(inp, "input", lambda e: (self.store.set("name", inp.value.strip()), audit_certificate.draw(self, qs("#cert-canvas"))))
        audit_certificate.draw(self, cv)
        audit_certificate.when_fonts_ready(lambda: nn(qs("#cert-canvas")) and audit_certificate.draw(self, qs("#cert-canvas")))

    def on_theme_changed(self, theme: str) -> None:
        if self.screen == "progress":
            self.render_progress()

    # ================= events =================
    def haptic(self, kind: str = "tap") -> None:
        if not self.store.get("haptics", True):
            return
        try:
            if hasattr(window, "AndroidApp") and hasattr(window.AndroidApp, "haptic"):
                window.AndroidApp.haptic(kind)
            elif hasattr(window.navigator, "vibrate"):
                window.navigator.vibrate({"tap": 8, "success": 18, "error": 30}.get(kind, 8))
        except Exception:  # noqa: BLE001 - haptics are optional
            pass

    def on_click(self, e) -> None:
        el = closest(e.target, "[data-action]")
        a = el.dataset.action if el is not None else ""
        if a == "tab":
            self.haptic()
            tab = el.dataset.tab
            if tab == "cases":
                if self.screen == "home":           # tapping the active tab scrolls to the top, like iOS
                    qs("#scr-home .scroller").scrollTo(_opts(top=0, behavior="smooth"))
                else:
                    self.go("#/")
            elif tab == "investigate":
                if self.case is not None:
                    self.go(f"#/case/{self.case['id']}/{self.level_i + 1}")
                else:
                    nxt = self.next_unsolved()
                    c, lv = nxt if nxt else (self.cases[0], self.cases[0]["levels"][0])
                    self.go(f"#/case/{c['id']}/{c['levels'].index(lv) + 1}")
            elif tab == "evidence":
                self.go("#/evidence")
            elif tab == "progress":
                self.go("#/progress")
            return
        if a == "nav-back":
            self.nav_back()
            return
        if a in ("resume",):
            self.go(f"#/case/{el.dataset.case}/{el.dataset.n}")
            return
        if a == "open-level":
            self.go(f"#/case/{self.case['id']}/{int(el.dataset.n) + 1}")
            return
        if a == "investigate":
            self.go(f"#/case/{self.case['id']}/{self.level_i + 1}")
            return
        if a == "hints-sheet":
            self.open_sheet("hints")
            return
        if a == "sheet-close":
            self.close_sheet()
            return
        if a == "report":
            self.close_overlay()
            self.go("#/progress/report")
            return
        if a == "theme-pref":
            theme_toggle.set_pref(el.dataset.pref)
            self.haptic()
            for b in document.querySelectorAll('[data-action="theme-pref"]'):
                b.setAttribute("aria-checked", "true" if b.dataset.pref == el.dataset.pref else "false")
            return
        if a == "switch":
            key = el.dataset.key
            val = el.getAttribute("aria-checked") != "true"
            el.setAttribute("aria-checked", "true" if val else "false")
            self.store.set(key, val)
            self.apply_prefs()
            self.haptic()
            return
        if a == "kb-insert":
            if self.editor is not None:
                self.editor.insert(el.dataset.t + (" " if el.dataset.t[:1].isalpha() or el.dataset.t == "COUNT(*)" else ""))
                self.haptic()
            return
        if a == "theme":
            theme_toggle.toggle()
            return
        if a == "history-item":
            self.close_sheet()
        super().on_click(e)

    def apply_prefs(self) -> None:
        root = document.documentElement
        root.classList.toggle("no-lines", not self.store.get("lines", True))
        if self.editor is not None:
            later(self.editor.refresh, 30)

    def run(self) -> None:
        super().run()
        if qs("#results .verdict.ok") is not None:
            self.haptic("success")
        elif qs("#results .verdict.err") is not None or qs("#results .verdict.no") is not None:
            self.haptic("error")

    def after_run(self) -> None:
        res = qs("#results")
        if res is None:
            return
        if document.activeElement == qs("#sql"):
            qs("#sql").blur()                     # drop the keyboard so the verdict is visible
        later(lambda: res.scrollIntoView(_opts(behavior="smooth", block="start")), 60)

    def on_key(self, e) -> None:
        if e.key == "Escape" and self.sheet_kind and not qs("#overlay").innerHTML:
            self.close_sheet()
            return
        super().on_key(e)

    def on_focus_in(self, e) -> None:
        t = nn(e.target)
        root = qs("#ios")
        if t is not None and getattr(t, "id", "") == "sql":
            root.classList.add("kb")
        if t is not None and getattr(t, "tagName", "") in ("INPUT", "TEXTAREA"):
            root.classList.add("typing")

    def on_focus_out(self, e) -> None:
        def check():
            a = nn(document.activeElement)
            root = qs("#ios")
            if a is None or getattr(a, "id", "") != "sql":
                root.classList.remove("kb")
            if a is None or getattr(a, "tagName", "") not in ("INPUT", "TEXTAREA"):
                root.classList.remove("typing")
        later(check, 120)

    def sync_keyboard_offset(self) -> None:
        vv = window.visualViewport
        off = max(0, window.innerHeight - vv.height - vv.offsetTop)
        document.documentElement.style.setProperty("--kb-offset", f"{off:.0f}px")

    def back(self, *_args) -> str:
        """Android back / browser back: close the top-most layer, then pop the screen, then go home, then exit."""
        if qs("#overlay").innerHTML:
            self.close_overlay()
            return "1"
        if self.sheet_kind:
            self.close_sheet()
            return "1"
        ac = qs("#ac-list")
        if ac is not None and not ac.hidden:
            ac.hidden = True
            return "1"
        if document.activeElement == qs("#sql"):
            qs("#sql").blur()
            return "1"
        if self.parent_hash() is not None:
            self.nav_back()
            return "1"
        if self.screen != "home":
            self.go("#/")
            return "1"
        return "0"

    def show_onboarding(self) -> None:
        """First-run welcome, worded for touch (the website version talks about keyboard shortcuts)."""
        self.overlay("""
<div class="eyebrow">Welcome, auditor</div>
<h2>Prove fraud with SQL.</h2>
<p class="muted">A real SQLite database runs on this device. No server, no sign-up, and everything works offline.</p>
<ol class="onboard-steps">
 <li><div><b>Open a case.</b> Each case file is a dataset with a story and a list of exhibits to prove.</div></li>
 <li><div><b>Check the evidence.</b> Tap Tables to see every column; tap a name to drop it into your query.</div></li>
 <li><div><b>Run it.</b> You get a verdict and a row and column count - never the answer itself.</div></li>
 <li><div><b>Stuck?</b> Hints unlock one at a time. Close a case to get your audit report.</div></li>
</ol>
<div class="actions"><button class="btn btn-primary" data-action="start-training">Start orientation</button>
<button class="btn" data-action="skip-onboard">Explore on my own</button></div>""", "Welcome")

    def close_overlay(self) -> None:
        box = qs("#overlay")
        if box.innerHTML:
            box.innerHTML = ""


from .editor import Editor  # noqa: E402  (imported late to keep the module header readable)
