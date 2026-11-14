"""WCAG contrast check for the website (casefile.css) and app-mode (ios.css) theme tokens, both themes.
Exit 1 if a text pair is below its target.

    python tools/contrast_check.py
"""
import pathlib
import re
import sys

UI = pathlib.Path(__file__).resolve().parents[1] / "src" / "ui"
CSS = (UI / "casefile.css").read_text()
IOS = (UI / "ios.css").read_text()

# (foreground token, background token, minimum ratio) - 4.5 body text, 3.0 large/bold UI text and icons
PAIRS = [("text", "card", 4.5), ("text", "paper", 4.5), ("text", "bg", 4.5), ("muted", "card", 4.5), ("muted", "paper", 4.5),
         ("faint", "code-bg", 4.5), ("accent-ink", "accent", 4.5), ("accent2-ink", "accent2", 4.5), ("tag-ink", "tag", 4.5),
         ("bar-ink", "bar", 4.5), ("bar-muted", "bar", 4.5), ("ok", "ok-bg", 4.5), ("bad", "bad-bg", 4.5), ("text", "warn-bg", 4.5),
         ("accent", "card", 3.0), ("accent2", "card", 3.0), ("focus", "card", 3.0), ("ok", "card", 3.0), ("text", "code-bg", 4.5),
         ("t-kw", "code-bg", 4.5), ("t-fn", "code-bg", 4.5), ("t-str", "code-bg", 4.5), ("t-num", "code-bg", 4.5),
         ("t-tbl", "code-bg", 4.5), ("t-col", "code-bg", 4.5), ("t-com", "code-bg", 4.5)]

# app mode: iOS-style palette (ios.css); syntax colours come from casefile.css but sit on the app's code background
IOS_PAIRS = [("ios-label", "ios-bg", 4.5), ("ios-label", "ios-cell", 4.5), ("ios-label-2", "ios-cell", 4.5), ("ios-label-2", "ios-bg", 4.5),
             ("ios-label-2", "ios-cell-2", 4.5), ("ios-tint", "ios-cell", 4.5), ("ios-tint", "ios-bg", 4.5), ("ios-tint-ink", "ios-tint", 4.5),
             ("ios-ok", "ios-cell", 4.5), ("ios-bad", "ios-cell", 4.5), ("ios-warn", "ios-cell", 4.5), ("ios-tag-ink", "ios-tag", 4.5),
             ("ios-manila-ink", "ios-manila", 4.5), ("ios-tint", "ios-manila", 4.5), ("faint", "ios-code", 3.0), ("ios-label", "ios-code", 4.5),
             ("accent2-ink", "accent2", 4.5)]
SYNTAX = ["t-kw", "t-fn", "t-str", "t-num", "t-tbl", "t-col", "t-com"]


def block(selector, css=None):
    m = re.search(re.escape(selector) + r"\s*\{(.*?)\n\}", css or CSS, re.S)
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9A-Fa-f]{6})", m.group(1))) if m else {}


def lum(hex_):
    c = [int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def main():
    bad = 0
    for name, sel in (("light", ':root, :root[data-theme="light"]'), ("dark", ':root[data-theme="dark"]')):
        t = block(sel)
        if not t:
            print(f"cannot find tokens for {name}")
            return 1
        for fg, bg, need in PAIRS:
            if fg not in t or bg not in t:
                continue
            r = ratio(t[fg], t[bg])
            ok = r >= need
            bad += not ok
            print(f"{'ok ' if ok else 'LOW'} {name:5} {fg:>12} on {bg:<8} {r:5.2f} (need {need})")
    light_ios = block("html.app-mode", IOS)
    for name, sel, site_sel in (("light", None, ':root, :root[data-theme="light"]'), ("dark", 'html.app-mode[data-theme="dark"]', ':root[data-theme="dark"]')):
        t = {**block(site_sel), **light_ios, **(block(sel, IOS) if sel else {})}
        if "ios-bg" not in t:
            print(f"cannot find app-mode tokens for {name}")
            return 1
        for fg, bg, need in IOS_PAIRS + [(k, "ios-code", 4.5) for k in SYNTAX]:
            if fg not in t or bg not in t:
                continue
            r = ratio(t[fg], t[bg])
            ok = r >= need
            bad += not ok
            print(f"{'ok ' if ok else 'LOW'} app-{name:5} {fg:>14} on {bg:<10} {r:5.2f} (need {need})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
