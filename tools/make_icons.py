"""Render launcher / PWA icons from assets/logo.svg with headless Chromium (run once, output committed).

    python tools/make_icons.py [--chrome PATH]
"""
import pathlib
import sys

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
RES = ROOT / "android" / "res"
DENS = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
LOGO = (ROOT / "assets" / "logo.svg").read_text()


def page_html(size: int, kind: str) -> str:
    if kind == "legacy":      # full icon on paper background
        body = f'<div style="width:{size}px;height:{size}px;background:#F4F0EA;display:grid;place-items:center">' \
               f'<div style="width:{size * .78}px;height:{size * .78}px">{LOGO}</div></div>'
    elif kind == "fg":        # adaptive foreground: logo in the 66% safe zone, transparent
        body = f'<div style="width:{size}px;height:{size}px;display:grid;place-items:center">' \
               f'<div style="width:{size * .58}px;height:{size * .58}px">{LOGO}</div></div>'
    else:                     # adaptive background
        body = f'<div style="width:{size}px;height:{size}px;background:#F4F0EA"></div>'
    return f"<html><body style='margin:0;background:transparent'>{body}<style>svg{{width:100%;height:100%}}</style></body></html>"


def main():
    exe = sys.argv[sys.argv.index("--chrome") + 1] if "--chrome" in sys.argv else None
    with sync_playwright() as p:
        b = p.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--no-sandbox"])
        pg = b.new_page()

        def shot(size, kind, out):
            pg.set_viewport_size({"width": size, "height": size})
            pg.set_content(page_html(size, kind))
            out.parent.mkdir(parents=True, exist_ok=True)
            pg.screenshot(path=str(out), omit_background=True)

        for d, s in DENS.items():
            shot(s, "legacy", RES / f"mipmap-{d}" / "ic_launcher.png")
            shot(int(s * 2.25), "fg", RES / f"mipmap-{d}" / "ic_launcher_foreground.png")
            shot(int(s * 2.25), "bg", RES / f"mipmap-{d}" / "ic_launcher_background.png")
        shot(192, "legacy", ROOT / "assets" / "icon-192.png")
        shot(512, "legacy", ROOT / "assets" / "icon-512.png")
        b.close()
    print("icons written")


if __name__ == "__main__":
    main()
