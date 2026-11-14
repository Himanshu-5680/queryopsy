"""Theme: follows the system by default; the player can pin Light or Dark.

Website: "Dossier" (light manila case file) / "Crime Lab" (dark evidence board).
App mode: iOS-style light / dark with the same case-file accents.
"""
from js import document, localStorage, window

KEY = "queryopsy.theme"          # "system" (default), "light" or "dark"
_watchers = []
_mq_proxy = None


def pref() -> str:
    try:
        p = localStorage.getItem(KEY)
    except Exception:
        p = None
    return p if p in ("light", "dark") else "system"


def system_theme() -> str:
    return "dark" if window.matchMedia("(prefers-color-scheme: dark)").matches else "light"


def current() -> str:
    return document.documentElement.getAttribute("data-theme") or "light"


def _app_mode() -> bool:
    return bool(document.documentElement.classList.contains("app-mode"))


def apply(theme: str) -> None:
    document.documentElement.setAttribute("data-theme", theme)
    meta = document.querySelector('meta[name="theme-color"]')
    if meta:
        if _app_mode():
            meta.setAttribute("content", "#0B0A09" if theme == "dark" else "#F2F1EE")
        else:
            meta.setAttribute("content", "#0F0C0A" if theme == "dark" else "#2A241D")
    btn = document.getElementById("theme-btn")
    if btn:
        btn.setAttribute("aria-label", "Switch to light theme" if theme == "dark" else "Switch to dark theme")
        btn.setAttribute("aria-pressed", "true" if theme == "dark" else "false")
    if hasattr(window, "AndroidApp"):
        try:
            window.AndroidApp.setDark(theme == "dark")
        except Exception:
            pass
    for fn in _watchers:
        try:
            fn(theme)
        except Exception:
            pass


def set_pref(p: str) -> str:
    try:
        if p in ("light", "dark"):
            localStorage.setItem(KEY, p)
        else:
            localStorage.removeItem(KEY)
    except Exception:
        pass
    theme = p if p in ("light", "dark") else system_theme()
    apply(theme)
    return theme


def toggle() -> str:
    return set_pref("light" if current() == "dark" else "dark")


def watch_system(callback=None) -> None:
    """Re-theme live when the OS switches between light and dark (only while the preference is "system")."""
    from pyodide.ffi import create_proxy
    if callback is not None:
        _watchers.append(callback)
    if globals().get("_mq_proxy") is not None:
        return
    mq = window.matchMedia("(prefers-color-scheme: dark)")
    proxy = create_proxy(lambda e: apply(system_theme()) if pref() == "system" else None)
    try:
        mq.addEventListener("change", proxy)
    except Exception:
        pass
    globals()["_mq_proxy"] = proxy
