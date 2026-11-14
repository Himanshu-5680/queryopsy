"""Assemble the deployable static site into build/site/ and zip it into dist/.

    python tools/build_web.py            -> build/site/ + dist/queryopsy-web-v<version>.zip
Only runtime files are shipped: no tests, pipeline, raw data or solutions.
"""
from __future__ import annotations

import json
import re
import pathlib
import shutil
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SITE = ROOT / "build" / "site"
DIST = ROOT / "dist"
INCLUDE = ["index.html", "manifest.webmanifest", "sw.js", "assets", "src", "reports", "vendor",
           "data/cases.json", "data/db", "data/schemas", "LICENSE"]
SKIP_SUFFIX = {".pyc", ".md~"}


def version() -> str:
    return json.loads((ROOT / "version.json").read_text())["versionName"]


def build() -> pathlib.Path:
    shutil.rmtree(SITE, ignore_errors=True)
    for item in INCLUDE:
        src = ROOT / item
        dst = SITE / item
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".*"))
        elif src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    files = sorted(p.relative_to(SITE).as_posix() for p in SITE.rglob("*") if p.is_file() and p.suffix not in SKIP_SUFFIX)
    precache = ["./"] + [f for f in files if not f.endswith((".sql", "LICENSE"))]
    (SITE / "precache.json").write_text(json.dumps(precache), encoding="utf-8")
    sw = re.sub(r"queryopsy-v[0-9][0-9.]*", f"queryopsy-v{version()}", (SITE / "sw.js").read_text(), count=1)
    (SITE / "sw.js").write_text(sw)
    (SITE / ".nojekyll").write_text("")
    return SITE


def zip_site() -> pathlib.Path:
    DIST.mkdir(exist_ok=True)
    out = DIST / f"queryopsy-web-v{version()}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(SITE.rglob("*")):
            if p.is_file():
                z.write(p, "queryopsy-web/" + p.relative_to(SITE).as_posix())
        z.writestr("queryopsy-web/HOW-TO-RUN.txt",
                   "Queryopsy - offline website\n\nBrowsers block WebAssembly on file:// pages, so serve this folder:\n"
                   "  python -m http.server 8000      (then open http://localhost:8000)\n")
    return out


if __name__ == "__main__":
    site = build()
    out = zip_site()
    size = sum(p.stat().st_size for p in site.rglob("*") if p.is_file())
    print(f"site: {site} ({size / 1e6:.1f} MB)  zip: {out} ({out.stat().st_size / 1e6:.1f} MB)")
