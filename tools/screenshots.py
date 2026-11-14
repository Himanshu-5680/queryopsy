"""Capture README/store screenshots with Playwright (Python).

    python tools/screenshots.py [--chrome /usr/bin/google-chrome] [--app-only]

Website shots go to docs/screenshots/, phone app-mode shots (393x852, light + dark) to docs/screenshots/app/.
"""
import json
import pathlib
import sys
import threading
import functools
import http.server

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"
SOL = json.loads((ROOT / "tests" / "fixtures" / "solutions.json").read_text())


class H(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".wasm": "application/wasm", ".py": "text/plain"}

    def log_message(self, *a):
        pass


WEBVIEW_UA = ("Mozilla/5.0 (Linux; Android 14; Pixel 7 Build/UQ1A.240205.004; wv) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Version/4.0 Chrome/131.0.6778.135 Mobile Safari/537.36")


def app_shots(b, base):
    """Phone screenshots of the app-mode UI as the Android app shows it."""
    out = OUT / "app"
    out.mkdir(parents=True, exist_ok=True)
    state = {"onboarded": True, "name": "Himanshu Pathak",
             "solved": {**{f"case00_training-{i}": {"at": 0} for i in (1, 2, 3)}, **{f"case01_funding-{i}": {"at": 0} for i in (1,)}}}
    for theme in ("light", "dark"):
        ctx = b.new_context(viewport={"width": 393, "height": 852}, device_scale_factor=3, is_mobile=True, has_touch=True, user_agent=WEBVIEW_UA)
        pg = ctx.new_page()
        pg.add_init_script(f"localStorage.setItem('queryopsy.theme', '{theme}');"
                           f"if (!sessionStorage.getItem('seeded')) {{ localStorage.setItem('queryopsy.progress.v1', JSON.stringify({json.dumps(state)})); sessionStorage.setItem('seeded', '1'); }}")
        pg.goto(base)
        pg.wait_for_function("document.documentElement.dataset.engine === 'ready'", timeout=90000)
        pg.wait_for_selector("#splash", state="detached")
        pg.wait_for_timeout(300)

        def shot(name):
            pg.wait_for_timeout(650)      # let push/pop and sheet animations settle
            pg.screenshot(path=str(out / f"{name}-{theme}.png"))

        shot("01-cases")
        pg.click('#scr-home [data-action="open-case"][data-case="case01_funding"]')
        pg.wait_for_selector("#scr-case.is-active .group")
        shot("02-case")
        pg.click('#scr-case [data-action="investigate"]')
        pg.wait_for_selector("#scr-investigate.is-active #sql")
        pg.click("#sql")
        pg.keyboard.press("End")
        pg.keyboard.type(" COUNT(*) AS rounds\nFROM funding_rounds\nWHERE LOWER(city_raw) LIKE '%bangal")
        shot("03-editor")
        pg.evaluate("document.activeElement.blur()")
        pg.click('#scr-investigate .nav-r [data-action="evidence"]')
        pg.wait_for_selector("#sheet-host:not([hidden]) #schema")
        shot("04-schema-sheet")
        pg.click('#sheet [data-action="sheet-close"]')
        pg.wait_for_selector("#sheet-host", state="hidden")
        pg.fill("#sql", SOL["case01_funding-2"])
        pg.click("#run-btn")
        pg.wait_for_selector("#results .verdict.ok")
        shot("05-verdict")
        pg.click('#tabbar [data-tab="progress"]')
        pg.wait_for_selector("#scr-progress.is-active")
        shot("06-progress")
        pg.click('#scr-progress [data-action="report"]')
        pg.wait_for_selector("#scr-report.is-active #cert-canvas")
        shot("07-report")
        ctx.close()
    print("app screenshots ->", out)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=str(ROOT)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/"
    exe = sys.argv[sys.argv.index("--chrome") + 1] if "--chrome" in sys.argv else None
    with sync_playwright() as p:
        b = p.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--no-sandbox"])
        app_shots(b, base)
        if "--app-only" in sys.argv:
            b.close()
            srv.shutdown()
            return

        def page(theme, w, h, dpr=1.5, progress=None):
            ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=dpr)
            pg = ctx.new_page()
            state = progress or {"onboarded": True}
            pg.add_init_script(f"localStorage.setItem('queryopsy.theme', '{theme}');"
                               f"if (!sessionStorage.getItem('seeded')) {{ localStorage.setItem('queryopsy.progress.v1', JSON.stringify({json.dumps(state)})); sessionStorage.setItem('seeded', '1'); }}")
            return pg

        def ready(pg):
            pg.wait_for_function("document.documentElement.dataset.engine === 'ready'", timeout=90000)
            pg.wait_for_timeout(500)

        def solve(pg, case, n):
            pg.goto(base + f"#/case/{case}/{n}")
            pg.wait_for_selector("#sql")
            pg.fill("#sql", SOL[f"{case}-{n}"])
            pg.press("#sql", "Control+Enter")
            pg.wait_for_selector("#results .verdict")

        done = {"solved": {f"case00_training-{i}": {"at": 0} for i in (1, 2, 3)}, "onboarded": True}
        done["solved"].update({f"case01_funding-{i}": {"at": 0} for i in (1, 2)})
        # 1. light home
        pg = page("light", 1440, 1000, progress=done)
        pg.goto(base)
        ready(pg)
        pg.screenshot(path=str(OUT / "home-light.png"))
        # 2. light case with a near-miss verdict
        pg.goto(base + "#/case/case01_funding/3")
        pg.wait_for_selector("#sql")
        pg.keyboard.press("Alt+KeyH")
        pg.fill("#sql", "SELECT LOWER(TRIM(startup)) AS startup_key, deal_date, amount_usd, COUNT(*) AS copies\nFROM funding_rounds\nGROUP BY 1, 2, 3\nHAVING COUNT(*) >= 1\nORDER BY copies DESC;")
        pg.press("#sql", "Control+Enter")
        pg.wait_for_timeout(600)
        pg.screenshot(path=str(OUT / "case-light.png"))
        # 3. dark case solved + ER diagram
        pg = page("dark", 1440, 1000, progress=done)
        pg.goto(base)
        ready(pg)
        solve(pg, "case02_quickcommerce", 2)
        pg.click('.schema-tabs button[data-tab="diagram"]')
        pg.wait_for_timeout(700)
        pg.screenshot(path=str(OUT / "case-dark.png"))
        pg.goto(base)
        pg.wait_for_timeout(400)
        pg.screenshot(path=str(OUT / "home-dark.png"))
        # 4. mobile website (forced with ?app=0; phones get the app-mode UI shot above)
        pg = page("light", 390, 844, dpr=2, progress=done)
        pg.goto(base + "?app=0#/case/case05_payroll/2")
        ready(pg)
        pg.screenshot(path=str(OUT / "mobile-brief.png"))
        pg.click('.mobile-tabs [data-tab="query"]')
        pg.fill("#sql", SOL["case05_payroll-2"])
        pg.click('[data-action="run"]')
        pg.wait_for_timeout(700)
        pg.evaluate("window.scrollTo(0, 0)")
        pg.screenshot(path=str(OUT / "mobile-query.png"))
        pg.click('.mobile-tabs [data-tab="schema"]')
        pg.wait_for_timeout(300)
        pg.screenshot(path=str(OUT / "mobile-schema.png"))
        # 5. certificate
        pg = page("light", 1200, 1000, progress=done)
        pg.goto(base)
        ready(pg)
        pg.evaluate("1")
        pg.click('[data-action="shortcuts"]')
        pg.wait_for_timeout(400)
        pg.screenshot(path=str(OUT / "shortcuts.png"))
        pg.keyboard.press("Escape")
        pg.goto(base + "#/case/case00_training/3")
        pg.wait_for_selector("#sql")
        pg.evaluate("localStorage.getItem('x')")
        solve(pg, "case00_training", 3)
        pg.click('#results [data-action="certificate"], [data-action="certificate"]')
        pg.fill("#cert-name", "Himanshu Pathak")
        pg.wait_for_timeout(500)
        pg.locator("#cert-canvas").screenshot(path=str(OUT / "certificate.png"))
        b.close()
    srv.shutdown()
    print("screenshots ->", OUT)


if __name__ == "__main__":
    main()
