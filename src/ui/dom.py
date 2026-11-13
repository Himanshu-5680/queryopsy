"""Tiny DOM helpers for Python-in-the-browser."""
from __future__ import annotations

from html import escape

from js import document, window
from pyodide.ffi import create_proxy

_proxies = []          # keep callbacks alive for the lifetime of the page


def esc(v) -> str:
    return escape("" if v is None else str(v), quote=True)


def nn(x):
    """JS null/undefined -> None (Pyodide maps null to a falsy JsNull object)."""
    if x is None or type(x).__name__ in ("JsNull", "JsUndefined"):
        return None
    return x


def qs(sel: str, root=None):
    return nn((root or document).querySelector(sel))


def on(target, event: str, fn, options=None) -> None:
    p = create_proxy(fn)
    _proxies.append(p)
    if options is None:
        target.addEventListener(event, p)
    else:
        target.addEventListener(event, p, options)


def later(fn, ms: int = 0) -> None:
    p = create_proxy(lambda *a: fn())
    _proxies.append(p)
    window.setTimeout(p, ms)


def toast(text: str, kind: str = "") -> None:
    box = document.getElementById("toast")
    box.className = f"toast card {kind}"
    box.textContent = text
    box.hidden = False
    box.setAttribute("role", "status")
    n = int(box.getAttribute("data-n") or 0) + 1
    box.setAttribute("data-n", str(n))

    def hide():
        if box.getAttribute("data-n") == str(n):
            box.hidden = True
    later(hide, 2600)


def closest(el, sel: str):
    try:
        el = nn(el)
        return nn(el.closest(sel)) if el is not None and hasattr(el, "closest") else None
    except Exception:
        return None
