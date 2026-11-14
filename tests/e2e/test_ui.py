"""End-to-end tests of the real website (Pyodide engine) in Chromium."""
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / "data" / "cases.json").read_text())["cases"]
SOLUTIONS = json.loads((ROOT / "tests" / "fixtures" / "solutions.json").read_text())


def run_sql(page, sql):
    page.fill("#sql", sql)
    page.press("#sql", "Control+Enter")
    page.wait_for_selector("#results .verdict")


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_every_official_solution_is_proven_in_the_browser(app, case):
    app.goto(app.url.split("#")[0] + f"#/case/{case['id']}/1")
    app.wait_for_selector("#sql")
    for i, lv in enumerate(case["levels"]):
        app.click(f'#stepper button[data-n="{i}"]')
        run_sql(app, SOLUTIONS[lv["id"]])
        assert "PROVEN" in app.inner_text("#results .verdict").upper(), lv["id"]
        assert app.locator(f'#stepper button[data-n="{i}"]').get_attribute("class") == "done"
    app.wait_for_selector(".modal >> text=/case closed/i")


def test_wrong_query_shows_diff_not_answer(app):
    app.click('.case-card[data-case="case01_funding"]')
    app.wait_for_selector("#sql")
    run_sql(app, "SELECT round_id, startup, deal_date FROM funding_rounds")
    v = app.inner_text("#results .verdict")
    v = v.upper()
    assert "NOT PROVEN YET" in v and "COLUMNS 3 / 3" in v and "MATCHING ROWS 2 / 2" in v


def test_friendly_error_and_suggestion(app):
    app.click('.case-card[data-case="case01_funding"]')
    app.wait_for_selector("#sql")
    run_sql(app, "SELECT * FROM funding_round")
    v = app.inner_text("#results .verdict")
    assert "no table called" in v.lower() and "funding_rounds" in v


def test_autocomplete_and_schema_insert(app):
    app.click('.case-card[data-case="case02_quickcommerce"]')
    app.wait_for_selector("#sql")
    app.fill("#sql", "")
    app.type("#sql", "SELECT * FROM pla")
    app.wait_for_selector("#ac-list li")
    assert "platforms" in app.inner_text("#ac-list")
    app.press("#sql", "Tab")
    assert app.input_value("#sql") == "SELECT * FROM platforms"
    app.click('#schema button[data-insert="orders"]')
    assert app.input_value("#sql").endswith("orders")
    app.click('.schema-tabs button[data-tab="diagram"]')
    app.wait_for_selector("svg.erd")
    app.click('svg.erd text[data-insert="rider_payouts"]')
    assert app.input_value("#sql").endswith("rider_payouts")


def test_preview_hints_history(app):
    app.click('.case-card[data-case="case03_catalog"]')
    app.wait_for_selector("#sql")
    app.click('#schema button[data-action="preview"][data-table="products"]')
    assert "PREVIEW: PRODUCTS" in app.inner_text("#results").upper()
    app.keyboard.press("Alt+KeyH")
    app.wait_for_selector(".hint")
    run_sql(app, "SELECT COUNT(*) FROM products")
    app.click('[data-action="history"]')
    assert "SELECT COUNT(*) FROM products" in app.inner_text(".drawer")
    app.keyboard.press("Escape")


def test_theme_and_progress_persist(app):
    app.click("#theme-btn")
    theme = app.get_attribute("html", "data-theme")
    app.goto(app.url.split("#")[0] + "#/case/case00_training/3")
    app.wait_for_selector("#sql")
    run_sql(app, SOLUTIONS["case00_training-3"])
    app.reload()
    app.wait_for_function("document.documentElement.dataset.engine === 'ready'", timeout=90000)
    assert app.get_attribute("html", "data-theme") == theme
    assert app.inner_text("#progress-count").startswith("1/")


def test_certificate_downloads(app):
    app.goto(app.url.split("#")[0] + "#/case/case00_training/1")
    app.wait_for_selector("#sql")
    for i, lv in enumerate(CASES[0]["levels"]):
        app.click(f'#stepper button[data-n="{i}"]')
        run_sql(app, SOLUTIONS[lv["id"]])
    app.click('[data-action="certificate"] >> nth=0')
    app.fill("#cert-name", "Test Auditor")
    with app.expect_download() as d:
        app.click('[data-action="cert-png"]')
    assert pathlib.Path(d.value.path()).read_bytes()[:4] == b"\x89PNG"
    with app.expect_download() as d:
        app.click('[data-action="cert-pdf"]')
    assert pathlib.Path(d.value.path()).read_bytes()[:5] == b"%PDF-"


def test_onboarding_first_visit(page, base_url):
    page.goto(base_url)
    page.wait_for_selector("text=Start orientation >> nth=1", timeout=90000)
    page.click('.modal [data-action="start-training"]')
    page.wait_for_selector("#sql")
    assert "ORIENTATION" in page.inner_text(".dossier h1").upper()


def test_mobile_website_layout(page, base_url):
    """A narrow browser forced into website mode (?app=0) still gets the tabbed dossier layout."""
    page.set_viewport_size({"width": 390, "height": 844})
    page.add_init_script("if (!localStorage.getItem('queryopsy.progress.v1')) localStorage.setItem('queryopsy.progress.v1', JSON.stringify({onboarded: true}))")
    page.goto(base_url + "?app=0#/case/case01_funding/1")
    page.wait_for_selector(".mobile-tabs", timeout=90000)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    assert page.is_visible(".dossier-panel") and not page.is_visible("#sql")
    page.click('.mobile-tabs [data-tab="schema"]')
    assert page.is_visible(".schema-panel")
    page.click('#schema button[data-insert="funding_rounds"]')       # inserting jumps to the query tab
    assert page.is_visible("#sql")
    page.fill("#sql", SOLUTIONS["case01_funding-1"])
    page.click('[data-action="run"]')
    page.wait_for_selector("#results .verdict.ok")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")


def test_works_with_network_blocked(page, base_url):
    """Everything the app needs is served by the site itself - block anything else and it still works."""
    page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base_url) else r.abort())
    page.add_init_script("if (!localStorage.getItem('queryopsy.progress.v1')) localStorage.setItem('queryopsy.progress.v1', JSON.stringify({onboarded: true}))")
    page.goto(base_url + "#/case/case04_upi/3")
    page.wait_for_selector("#sql", timeout=90000)
    page.fill("#sql", SOLUTIONS["case04_upi-3"])
    page.press("#sql", "Control+Enter")
    page.wait_for_selector("#results .verdict.ok")
