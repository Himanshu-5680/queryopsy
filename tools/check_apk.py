"""Smoke-test the APK's web payload exactly as the Android shell serves it.

Unpacks assets/www from the APK and serves it to Chromium on the same virtual origin
(https://appassets.androidplatform.net/www/) with the same MIME table as MainActivity,
blocking every other request. Then boots the app and solves one level.

    python tools/check_apk.py dist/Queryopsy-v1.0.0.apk [--chrome PATH]
"""
import json
import pathlib
import sys
import zipfile

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
MIME = {"html": "text/html", "js": "text/javascript", "css": "text/css", "json": "application/json", "wasm": "application/wasm",
        "zip": "application/zip", "whl": "application/zip", "py": "text/plain", "sqlite": "application/octet-stream",
        "woff2": "font/woff2", "svg": "image/svg+xml", "png": "image/png", "webmanifest": "application/manifest+json", "txt": "text/plain"}
ORIGIN = "https://appassets.androidplatform.net"


def main():
    apk = zipfile.ZipFile(sys.argv[1])
    exe = sys.argv[sys.argv.index("--chrome") + 1] if "--chrome" in sys.argv else None
    sol = json.loads((ROOT / "tests" / "fixtures" / "solutions.json").read_text())
    names = set(apk.namelist())
    blocked, errors = [], []

    def handle(route):
        url = route.request.url
        if not url.startswith(ORIGIN + "/www/"):
            blocked.append(url)
            return route.abort()
        path = "assets" + url[len(ORIGIN):].split("?")[0].split("#")[0]
        ext = path.rsplit(".", 1)[-1].lower()
        if path not in names or ext not in MIME:
            return route.fulfill(status=404, body="")
        route.fulfill(status=200, body=apk.read(path), headers={"Content-Type": MIME[ext], "X-Content-Type-Options": "nosniff"})

    with sync_playwright() as p:
        b = p.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--no-sandbox"])
        ctx = b.new_context(viewport={"width": 412, "height": 892}, device_scale_factor=2, is_mobile=True, has_touch=True,
                            service_workers="block")
        ctx.route("**/*", handle)
        pg = ctx.new_page()
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(ORIGIN + "/www/index.html")
        pg.wait_for_function("document.documentElement.dataset.engine === 'ready'", timeout=90000)
        pg.click('.modal [data-action="start-training"]')
        pg.wait_for_selector("#sql", state="attached")
        pg.click('.mobile-tabs [data-tab="query"]')
        pg.fill("#sql", sol["case00_training-1"])
        pg.click('[data-action="run"]')
        pg.wait_for_selector("#results .verdict.ok")
        b.close()
    print("APK payload OK: engine booted on the virtual origin, level solved.")
    print("blocked external requests:", blocked or "none", "| console errors:", errors or "none")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
