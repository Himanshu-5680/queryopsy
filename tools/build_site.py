"""Pre-render the home page from data/cases.json and stamp the CSP into index.html.

The case grid, stats and progress counters are plain HTML, so the page is readable
instantly while Pyodide boots in the background.      Usage: python tools/build_site.py
"""
from __future__ import annotations

import base64
import hashlib
import json
import pathlib
import re
from html import escape

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_SLUG = "Himanshu-5680/queryopsy"


def card(c: dict) -> str:
    n = len(c["levels"])
    ph = '<span class="chip chip-warn">Placeholder data</span>' if c["source"].get("placeholder") else '<span class="chip chip-ok">Real data</span>'
    return (f'<button class="case-card card" data-action="open-case" data-case="{c["id"]}" data-accent="{c.get("accent", "orange")}" aria-disabled="true">'
            f'<span class="no">CASE {c["no"]:02d}</span><h3>{escape(c["title"])}</h3>'
            f'<span class="row"><span class="chip chip-accent2">{escape(c["industry"])}</span><span class="chip">{escape(c["difficulty"])}</span>{ph}</span>'
            f'<p>{escape(c["tagline"])}</p><span class="bar"><i></i></span>'
            f'<span class="foot"><span class="count">0/{n} findings</span><span class="go">Open case</span></span></button>')


def main() -> None:
    data = json.loads((ROOT / "data" / "cases.json").read_text(encoding="utf-8"))
    cases = data["cases"]
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    cards = "".join(card(c) for c in cases)
    real = sum(1 for c in cases[1:] if not c["source"].get("placeholder"))
    findings = sum(len(c["levels"]) for c in cases)
    stats = (f'<div class="stats"><div><b>{len(cases) - 1}</b><span>case files + orientation</span></div><div><b>{findings}</b><span>findings to prove</span></div>'
             f'<div><b>0</b><span>servers or sign-ups</span></div><div><b>100%</b><span>offline &amp; on-device</span></div></div>')
    html = re.sub(r"<!--CASES:START-->.*?<!--CASES:END-->", f"<!--CASES:START-->{cards}<!--CASES:END-->", html, flags=re.S)
    html = re.sub(r"<!--STATS:START-->.*?<!--STATS:END-->", f"<!--STATS:START-->{stats}<!--STATS:END-->", html, flags=re.S)
    html = html.replace("REPO_SLUG", REPO_SLUG)
    ver = json.loads((ROOT / "version.json").read_text(encoding="utf-8"))["versionName"]
    html = re.sub(r'(<meta name="app-version" content=")[^"]*(")', lambda mm: mm.group(1) + ver + mm.group(2), html)
    m = re.search(r"<!--THEME--><script>(.*?)</script><!--/THEME-->", html, flags=re.S)
    digest = base64.b64encode(hashlib.sha256(m.group(1).encode()).digest()).decode()
    csp = ("default-src 'self'; script-src 'self' 'wasm-unsafe-eval' 'unsafe-eval' 'sha256-" + digest + "'; "
           "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; "
           "worker-src 'self'; manifest-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'")
    html = re.sub(r'(<meta http-equiv="Content-Security-Policy" content=")[^"]*(")', lambda mm: mm.group(1) + csp + mm.group(2), html)
    (ROOT / "index.html").write_text(html, encoding="utf-8")
    print(f"index.html: {len(cases)} cases, {findings} findings, {real} real datasets")


if __name__ == "__main__":
    main()
