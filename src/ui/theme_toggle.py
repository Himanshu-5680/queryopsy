"""Dark / light theme switch ("Terminal Hacker" / "Paper Audit")."""
from js import document, localStorage, window

KEY = "queryopsy.theme"


def current() -> str:
    return document.documentElement.getAttribute("data-theme") or "light"


def apply(theme: str) -> None:
    document.documentElement.setAttribute("data-theme", theme)
    meta = document.querySelector('meta[name="theme-color"]')
    if meta:
        meta.setAttribute("content", "#121212" if theme == "dark" else "#F4F0EA")
    btn = document.getElementById("theme-btn")
    if btn:
        btn.setAttribute("aria-label", "Switch to light theme" if theme == "dark" else "Switch to dark theme")
        btn.setAttribute("aria-pressed", "true" if theme == "dark" else "false")
    try:
        localStorage.setItem(KEY, theme)
    except Exception:
        pass
    if hasattr(window, "AndroidApp"):
        try:
            window.AndroidApp.setDark(theme == "dark")
        except Exception:
            pass


def toggle() -> str:
    theme = "light" if current() == "dark" else "dark"
    apply(theme)
    return theme
