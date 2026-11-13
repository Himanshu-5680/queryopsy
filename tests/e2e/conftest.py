import functools
import http.server
import os
import pathlib
import threading

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".wasm": "application/wasm",
                      ".py": "text/plain", ".sqlite": "application/octet-stream", ".js": "text/javascript"}

    def log_message(self, *a):
        pass


@pytest.fixture(scope="session")
def base_url():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(ROOT)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/"
    srv.shutdown()


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    exe = os.environ.get("CHROME_PATH")      # optional: use a system Chrome instead of Playwright's download
    return {**browser_type_launch_args, **({"executable_path": exe} if exe else {}), "args": ["--no-sandbox"]}


@pytest.fixture()
def app(page, base_url):
    """Page with the engine booted, onboarding dismissed, console errors and network collected."""
    problems, external = [], []
    page.on("console", lambda m: problems.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: problems.append(str(e)))
    page.on("request", lambda r: external.append(r.url) if not r.url.startswith(base_url) and not r.url.startswith(("data:", "blob:")) else None)
    page.add_init_script("if (!localStorage.getItem('queryopsy.progress.v1')) localStorage.setItem('queryopsy.progress.v1', JSON.stringify({onboarded: true}))")
    page.goto(base_url)
    page.wait_for_function("document.documentElement.dataset.engine === 'ready'", timeout=90000)
    page.problems, page.external = problems, external
    yield page
    assert not problems, f"console errors: {problems}"
    assert not external, f"network requests left the site: {external}"
