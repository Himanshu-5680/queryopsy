"""App-mode UI (APK, installed PWA, phones <= 760px): no sideways scrolling and native-style navigation."""
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SOLUTIONS = json.loads((ROOT / "tests" / "fixtures" / "solutions.json").read_text())
# a real Android System WebView user agent - what the APK's WebView reports
WEBVIEW_UA = ("Mozilla/5.0 (Linux; Android 14; Pixel 7 Build/UQ1A.240205.004; wv) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Version/4.0 Chrome/131.0.6778.135 Mobile Safari/537.36")
WIDTHS = [360, 393, 412]

# every visible element that sticks out to the right of the viewport without a scrolling/clipping ancestor
OVERFLOW_PROBE = """(vw) => {
  const W = vw, bad = [];
  for (const e of document.querySelectorAll('body *')) {
    const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
    if (!r.width || r.right <= W + 1 || cs.visibility === 'hidden' || cs.display === 'none') continue;
    let p = e.parentElement, clipped = false;
    while (p) {
      if (getComputedStyle(p).overflowX !== 'visible' && p.getBoundingClientRect().right <= W + 1) { clipped = true; break; }
      p = p.parentElement;
    }
    if (!clipped) bad.push(`${e.tagName}.${e.className} right=${Math.round(r.right)}`);
  }
  // a mobile browser widens the layout viewport to fit over-wide content, so innerWidth growing is overflow too
  return {sw: document.documentElement.scrollWidth, bw: document.body.scrollWidth, iw: innerWidth, W, bad: bad.slice(0, 10)};
}"""


def _phone(browser, base_url, w, h=852, theme="light", query="", progress=None):
    ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, is_mobile=True, has_touch=True,
                              user_agent=WEBVIEW_UA)
    pg = ctx.new_page()
    errors = []
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    state = progress or {"onboarded": True}
    pg.add_init_script(f"localStorage.setItem('queryopsy.theme','{theme}');"
                       f"if (!sessionStorage.getItem('seeded')) {{ localStorage.setItem('queryopsy.progress.v1', '{json.dumps(state)}'); sessionStorage.setItem('seeded','1'); }}")
    pg.goto(base_url + query)
    pg.wait_for_function("document.documentElement.dataset.engine === 'ready'", timeout=90000)
    pg.errors = errors
    return ctx, pg


def _no_overflow(pg, where):
    r = pg.evaluate(OVERFLOW_PROBE, pg.viewport_size["width"])
    assert r["iw"] == r["W"] and r["sw"] <= r["W"] and r["bw"] <= r["W"] and not r["bad"], f"{where}: horizontal overflow {r}"


def _active(pg):
    return pg.evaluate("[...document.querySelectorAll('#stack > .screen.is-active')].map(e => e.dataset.screen)")


@pytest.mark.parametrize("w", WIDTHS)
def test_app_mode_has_no_horizontal_overflow(browser, base_url, w):
    ctx, pg = _phone(browser, base_url, w, progress={"onboarded": True, "solved": {"case00_training-1": {"at": 0}}})
    assert pg.evaluate("document.documentElement.classList.contains('app-mode')")
    assert "user-scalable=no" in pg.get_attribute('meta[name="viewport"]', "content")
    pg.wait_for_selector("#scr-home.is-active .hero-card")
    _no_overflow(pg, "home")
    pg.click('#scr-home [data-action="open-case"][data-case="case01_funding"]')
    pg.wait_for_selector("#scr-case.is-active .exhibit-list, #scr-case.is-active .group")
    _no_overflow(pg, "case")
    pg.click('#scr-case [data-action="investigate"]')
    pg.wait_for_selector("#scr-investigate.is-active #sql")
    pg.fill("#sql", "SELECT * FROM funding_rounds r JOIN round_investors i ON i.round_id = r.round_id -- a deliberately long comment\nLIMIT 40;")
    pg.click("#run-btn")
    pg.wait_for_selector("#results table")
    _no_overflow(pg, "investigate + wide result")
    for tab in ("evidence", "progress"):
        pg.click(f'#tabbar [data-tab="{tab}"]')
        pg.wait_for_selector(f"#scr-{tab}.is-active")
        _no_overflow(pg, tab)
    assert not pg.errors, pg.errors
    ctx.close()


@pytest.mark.parametrize("w", WIDTHS)
def test_website_mode_on_phone_has_no_horizontal_overflow(browser, base_url, w):
    """The dossier website (?app=0) on a phone: the long 'Continue: ...' button and the header used to pan the page."""
    ctx, pg = _phone(browser, base_url, w, query="?app=0", progress={"onboarded": True, "solved": {"case00_training-1": {"at": 0}}})
    assert not pg.evaluate("document.documentElement.classList.contains('app-mode')")
    _no_overflow(pg, "website home")
    pg.goto(base_url + "?app=0#/case/case01_funding/2")
    pg.wait_for_selector("#sql", state="attached")
    _no_overflow(pg, "website case")
    assert not pg.errors, pg.errors
    ctx.close()


def test_app_mode_navigation(browser, base_url):
    ctx, pg = _phone(browser, base_url, 393)
    pg.wait_for_selector("#scr-home.is-active")
    assert _active(pg) == ["home"]
    assert pg.is_visible("#tabbar") and not pg.is_visible(".topbar")
    # push: home -> case -> investigate
    pg.click('#scr-home [data-action="open-case"][data-case="case01_funding"]')
    pg.wait_for_selector("#scr-case.is-active")
    assert pg.evaluate("location.hash") == "#/case/case01_funding"
    pg.click('#scr-case [data-action="investigate"]')
    pg.wait_for_selector("#scr-investigate.is-active #sql")
    assert pg.evaluate("location.hash").startswith("#/case/case01_funding/")
    # schema bottom sheet with a grabber, closed by Back
    pg.click('#scr-investigate [data-action="evidence"]')
    pg.wait_for_selector("#sheet-host:not([hidden]) #sheet #schema")
    assert pg.is_visible("#sheet .grabber")
    assert pg.evaluate("window.queryopsyBack()") == "1"
    pg.wait_for_selector("#sheet-host", state="hidden")
    assert pg.locator("#evidence-slot #evidence-block").count() == 1     # the evidence block went back home
    # run a query -> verdict; the tab bar hides while typing and comes back after the run
    pg.goto(base_url + "#/case/case01_funding/1")
    pg.wait_for_selector("#scr-investigate.is-active #sql")
    pg.click("#sql")
    pg.wait_for_function("document.querySelector('#ios').classList.contains('kb')")
    assert pg.is_visible("#kbbar")
    pg.fill("#sql", SOLUTIONS["case01_funding-1"])
    pg.click('#kbbar [data-action="run"]')
    pg.wait_for_selector("#results .verdict.ok")
    # Android Back pops the stack: investigate -> case -> home -> (exit)
    assert pg.evaluate("window.queryopsyBack()") in ("1", "0")
    pg.wait_for_function("document.activeElement !== document.querySelector('#sql')")
    if _active(pg) == ["investigate"]:
        assert pg.evaluate("window.queryopsyBack()") == "1"
    pg.wait_for_selector("#scr-case.is-active")
    assert pg.evaluate("window.queryopsyBack()") == "1"
    pg.wait_for_selector("#scr-home.is-active")
    assert pg.evaluate("window.queryopsyBack()") == "0"
    # tabs
    pg.click('#tabbar [data-tab="evidence"]')
    pg.wait_for_selector("#scr-evidence.is-active #schema")
    pg.click('#tabbar [data-tab="investigate"]')
    pg.wait_for_selector("#scr-investigate.is-active")
    pg.click('#tabbar [data-tab="progress"]')
    pg.wait_for_selector("#scr-progress.is-active")
    assert pg.get_attribute('#tabbar [data-tab="progress"]', "aria-current") == "page"
    # appearance: manual dark, then back to the system theme
    pg.click('[data-action="theme-pref"][data-pref="dark"]')
    assert pg.evaluate("document.documentElement.dataset.theme") == "dark"
    assert pg.evaluate("localStorage.getItem('queryopsy.theme')") == "dark"
    pg.click('[data-action="theme-pref"][data-pref="system"]')
    assert pg.evaluate("localStorage.getItem('queryopsy.theme')") is None
    # report screen (push) and back
    pg.click('#scr-progress [data-action="report"]')
    pg.wait_for_selector("#scr-report.is-active #cert-canvas")
    assert pg.evaluate("location.hash") == "#/progress/report"
    pg.click('#scr-report [data-action="nav-back"]')
    pg.wait_for_selector("#scr-progress.is-active")
    assert not pg.errors, pg.errors
    ctx.close()


def test_app_mode_edge_swipe_back(browser, base_url):
    ctx, pg = _phone(browser, base_url, 393)
    pg.goto(base_url + "#/case/case02_quickcommerce/2")
    pg.wait_for_selector("#scr-investigate.is-active #sql")
    pg.wait_for_timeout(450)
    pg.mouse.move(4, 420)
    pg.mouse.down()
    for x in range(20, 300, 20):
        pg.mouse.move(x, 425)
    pg.mouse.up()
    pg.wait_for_selector("#scr-case.is-active")
    assert pg.evaluate("location.hash") == "#/case/case02_quickcommerce"
    assert not pg.errors, pg.errors
    ctx.close()


def test_app_mode_first_run_and_chrome_is_not_selectable(browser, base_url):
    ctx = browser.new_context(viewport={"width": 393, "height": 852}, is_mobile=True, has_touch=True, user_agent=WEBVIEW_UA)
    pg = ctx.new_page()
    pg.goto(base_url)
    pg.wait_for_function("document.documentElement.dataset.engine === 'ready'", timeout=90000)
    pg.wait_for_selector("#splash", state="detached")
    css = pg.evaluate("""(() => { const t = getComputedStyle(document.querySelector('#tabbar'));
        const b = getComputedStyle(document.body);
        return [t.userSelect || t.webkitUserSelect, b.overscrollBehaviorY, b.webkitTapHighlightColor]; })()""")
    assert css[0] == "none" and css[1] == "none"
    pg.click('.modal [data-action="start-training"]')
    pg.wait_for_selector("#scr-investigate.is-active #sql")
    assert pg.evaluate("location.hash") == "#/case/case00_training/1"
    ctx.close()
