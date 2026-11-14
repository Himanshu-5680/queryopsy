"""Theme guard rails: WCAG contrast for every text token pair, bundled fonts, no external assets in CSS."""
import importlib.util
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_contrast_meets_wcag_in_both_themes():
    assert _load("contrast_check").main() == 0


def test_case_file_fonts_are_bundled_and_css_is_offline():
    css = (ROOT / "src" / "ui" / "casefile.css").read_text()
    for url in re.findall(r"url\(([^)]+)\)", css):
        url = url.strip("'\"")
        assert not url.startswith(("http:", "https:", "//")), url
        if not url.startswith("data:"):
            assert (ROOT / "src" / "ui" / url).resolve().exists(), f"missing asset {url}"
    for f in ("courier-prime-400.woff2", "courier-prime-700.woff2", "special-elite-400.woff2"):
        assert (ROOT / "vendor" / "fonts" / f).stat().st_size > 5000


def test_reduced_motion_is_respected():
    css = (ROOT / "src" / "ui" / "casefile.css").read_text()
    assert "prefers-reduced-motion: reduce" in css
