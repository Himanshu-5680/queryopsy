"""Layout regression tests (v1.0.1): main panels never overlap, the results header stays inside its pane,
the evidence room collapses into a drawer on narrow / short screens, and the drawer works with keyboard and Back."""
import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("layout_audit", ROOT / "tools" / "layout_audit.py")
layout_audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(layout_audit)

PANELS = r"""
() => {
  const vis = el => { if (!el) return false; const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 1 && r.height > 1 && s.display !== 'none' && s.visibility !== 'hidden'; };
  const boxes = ['.dossier-panel', '.bench', '.schema-panel'].map(s => document.querySelector(s))
    .filter(e => vis(e) && getComputedStyle(e).position !== 'fixed').map(e => { const r = e.getBoundingClientRect();
      return {name: e.className, l: r.left, r: r.right, t: r.top + scrollY, b: r.bottom + scrollY}; });
  const wrap = document.querySelector('.table-wrap'), th = wrap && wrap.querySelector('th');
  const w = wrap && wrap.getBoundingClientRect(), h = th && th.getBoundingClientRect();
  const bench = document.querySelector('.bench').getBoundingClientRect();
  return {boxes, wrap: w && {l: w.left, r: w.right, t: w.top, b: w.bottom}, th: h && {l: h.left, r: h.right, t: h.top, b: h.bottom},
          bench: {l: bench.left, r: bench.right}, sw: document.documentElement.scrollWidth, iw: innerWidth};
}
"""

VIEWPORTS = [(1024, 460), (1024, 600), (1180, 700), (1366, 768), (1920, 1080), (768, 1024), (412, 915), (360, 740)]


def _open(page, base_url, w, h, theme):
    mobile = w < 600
    page.set_viewport_size({"width": w, "height": h})
    page.add_init_script(f"localStorage.setItem('queryopsy.theme','{theme}');"
                         "localStorage.setItem('queryopsy.progress.v1', JSON.stringify({onboarded:true}))")
    problems = []
    page.on("console", lambda m: problems.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: problems.append(str(e)))
    # ?app=0: the website (dossier) layout; phones get the app-mode UI by default (tests/e2e/test_appmode.py)
    page.goto(base_url + "?app=0#/case/case01_funding/2")
    page.wait_for_function("document.documentElement.dataset.engine === 'ready'", timeout=90000)
    page.wait_for_selector("#sql", state="attached")
    return mobile, problems


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("w,h", VIEWPORTS, ids=[f"{w}x{h}" for w, h in VIEWPORTS])
def test_no_panel_overlap_and_header_inside_pane(page, base_url, w, h, theme):
    mobile, errors = _open(page, base_url, w, h, theme)
    problems = []
    layout_audit.run_steps(page, mobile, problems, None, theme, w, h, 1.0)
    assert not problems, problems
    page.evaluate("window.scrollTo(0, 0)")
    m = page.evaluate(PANELS)
    boxes = m["boxes"]
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            ox = min(a["r"], b["r"]) - max(a["l"], b["l"])
            oy = min(a["b"], b["b"]) - max(a["t"], b["t"])
            assert not (ox > 2 and oy > 2), f"{a['name']} overlaps {b['name']}"
    assert m["wrap"] and m["th"], "results table missing"
    assert m["th"]["t"] >= m["wrap"]["t"] - 1 and m["th"]["b"] <= m["wrap"]["b"] + 1, "header outside its pane vertically"
    assert m["th"]["l"] >= m["wrap"]["l"] - 1, "header starts outside its pane"
    assert m["wrap"]["r"] <= m["bench"]["r"] + 1, "results pane escapes the bench"
    assert m["sw"] <= m["iw"] + 1, "page scrolls horizontally"
    assert not errors, errors


def test_evidence_drawer_keyboard_and_back(page, base_url):
    _open(page, base_url, 1100, 700, "dark")
    ws = page.locator("#workspace")
    room = page.locator("#evidence-room")
    assert not room.is_visible() or room.bounding_box()["x"] >= 1100 - 1, "drawer should start closed"
    page.keyboard.press("Alt+e")
    page.wait_for_function("document.querySelector('#workspace').dataset.evidence === 'open'")
    page.wait_for_timeout(350)
    box = room.bounding_box()
    assert box["x"] + box["width"] <= 1101 and box["x"] < 1100, "drawer not on screen"
    assert page.evaluate("document.querySelector('#evidence-room').contains(document.activeElement)"), "focus not moved into drawer"
    page.keyboard.press("Escape")
    page.wait_for_function("document.querySelector('#workspace').dataset.evidence !== 'open'")
    page.click('[data-action="evidence"]')
    page.wait_for_function("document.querySelector('#workspace').dataset.evidence === 'open'")
    assert page.evaluate("window.queryopsyBack()") == "1", "Back should close the drawer first"
    assert ws.get_attribute("data-evidence") != "open"


def test_back_on_mobile_returns_to_dossier_then_cases(page, base_url):
    page.set_viewport_size({"width": 412, "height": 915})
    _open(page, base_url, 412, 915, "light")
    page.click('.mobile-tabs [data-tab="schema"]')
    assert page.evaluate("window.queryopsyBack()") == "1"
    assert page.get_attribute('.mobile-tabs [data-tab="brief"]', "aria-pressed") == "true"
    assert page.evaluate("window.queryopsyBack()") == "1"
    page.wait_for_function("location.hash === '#/' || location.hash === ''")
