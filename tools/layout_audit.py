"""Layout audit: open a busy case workspace at many viewports/themes/zoom levels, report overlaps and clipping.

    python tools/layout_audit.py [--chrome PATH] [--out DIR] [--quick]
Browser zoom is emulated as viewport / zoom with device_scale_factor = zoom (what a zoomed desktop browser does).
Exit code 1 if any problem is found.
"""
import functools
import http.server
import json
import pathlib
import sys
import threading

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]

VIEWPORTS = [(1024, 450), (1024, 460), (1024, 600), (1280, 720), (1366, 768), (1440, 900), (1920, 1080),
             (360, 740), (412, 915), (768, 1024), (1180, 700), (1200, 640), (861, 600)]
ZOOMS = [(1366, 768, 1.25), (1366, 768, 1.5), (1280, 720, 1.1), (1920, 1080, 1.5), (1024, 600, 1.25)]

# Runs inside the page: returns a list of human-readable problems.
PROBE = r"""
() => {
  const out = [];
  const vis = el => { if (!el) return false; const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 1 && r.height > 1 && s.visibility !== 'hidden' && s.display !== 'none' && !el.closest('[hidden]'); };
  const R = el => el.getBoundingClientRect();
  const inter = (a, b) => Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)) * Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
  const panels = ['.dossier-panel', '.bench', '.schema-panel'].map(s => [s, document.querySelector(s)]).filter(([s, e]) => vis(e) && getComputedStyle(e).position !== 'fixed');
  for (let i = 0; i < panels.length; i++) for (let j = i + 1; j < panels.length; j++) {
    const a = inter(R(panels[i][1]), R(panels[j][1])); if (a > 4) out.push(`panels overlap: ${panels[i][0]} x ${panels[j][0]} (${Math.round(a)}px2)`); }
  // descendants of a panel must not paint outside it horizontally
  for (const [s, p] of panels) { const pr = R(p);
    for (const el of p.querySelectorAll('.card, .table-wrap, table.grid th, .editor-foot, .schema-tabs, .toolbar, .verdict')) {
      if (!vis(el)) continue; const r = R(el);
      if (el.matches('th')) { const w = R(el.closest('.table-wrap')); if (r.right > w.right + 1 && r.left < w.right - 1 && getComputedStyle(el.closest('.table-wrap')).overflowX === 'visible') out.push('th escapes table-wrap'); continue; }
      if (r.right > pr.right + 2 || r.left < pr.left - 2) out.push(`${el.className || el.tagName} escapes ${s} horizontally (${Math.round(r.left)}-${Math.round(r.right)} vs ${Math.round(pr.left)}-${Math.round(pr.right)})`); } }
  // table header must stay inside its scroll container, and be what is painted there
  document.querySelectorAll('.table-wrap').forEach(w => { if (!vis(w)) return; const wr = R(w);
    const th = w.querySelector('th'); if (!th) return; const tr = R(th);
    const x = Math.min(wr.right - 4, Math.max(wr.left + 4, tr.left + 8)), y = Math.max(tr.top, wr.top) + 3;
    if (y < innerHeight && y > 0) { const hit = document.elementFromPoint(x, y); if (hit && !w.contains(hit) && !hit.closest('.topbar,.mobile-tabs,#overlay,.ac,.toast,.schema-panel.open')) out.push('something covers the results header: ' + (hit.className || hit.tagName)); }
    const sr = document.querySelector('.schema-panel'); if (vis(sr) && getComputedStyle(sr).position !== 'fixed' && inter(wr, R(sr)) > 4) out.push('results table overlaps evidence room'); });
  // schema tabs must be clickable (not covered)
  document.querySelectorAll('.schema-tabs button').forEach(b => { if (!vis(b)) return; const r = R(b); const y = r.top + r.height / 2;
    if (y < 0 || y > innerHeight) return; const hit = document.elementFromPoint(r.left + r.width / 2, y);
    if (hit && hit !== b && !b.contains(hit) && !hit.closest('.topbar,#overlay,.toast')) out.push('schema tab covered by ' + (hit.className || hit.tagName)); });
  // text clipping: single-line UI strips must not overflow their boxes
  for (const el of document.querySelectorAll('.editor-foot span, .toolbar, .panel-head, .results-meta span, .schema-tabs button, .mobile-tabs button, .topbar, .btn')) {
    if (!vis(el)) continue; const s = getComputedStyle(el); if (s.textOverflow === 'ellipsis') continue;
    if (el.scrollWidth > el.clientWidth + 2 && s.overflowX !== 'auto' && s.overflowX !== 'scroll') out.push(`text clipped in ${el.className || el.tagName}: "${el.textContent.trim().slice(0, 40)}"`); }
  if (document.documentElement.scrollWidth > innerWidth + 1) out.push(`page scrolls horizontally (${document.documentElement.scrollWidth} > ${innerWidth})`);
  return [...new Set(out)];
}
"""


class H(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".wasm": "application/wasm", ".py": "text/plain"}

    def log_message(self, *a):
        pass


def run_steps(pg, mobile, problems, out_dir, theme, w, h, z):
    mobile = pg.locator(".mobile-tabs").is_visible()     # tab layout is decided by CSS, not by the device type
    for step in ("preview", "query"):
        if step == "preview":
            btn = pg.locator('[data-action="preview"][data-table="funding_rounds"]').first
            if mobile:
                pg.click('.mobile-tabs [data-tab="schema"]')
            elif not btn.is_visible():
                ev = pg.locator('[data-action="evidence"]')
                if ev.count() and ev.first.is_visible():
                    ev.first.click()
            btn.scroll_into_view_if_needed()
            btn.click()
        else:
            if mobile:
                pg.click('.mobile-tabs [data-tab="query"]')
            pg.evaluate("document.querySelector('#overlay') && (document.querySelector('#overlay').innerHTML='')")
            pg.fill("#sql", "SELECT * FROM funding_rounds r JOIN round_investors i ON i.round_id = r.round_id -- a deliberately long comment to stress wrapping in the editor\nLIMIT 40;")
            pg.click('[data-action="run"]')
        pg.wait_for_timeout(350)
        for y in (0, 400, 99999):
            pg.evaluate(f"window.scrollTo(0, {y})")
            pg.wait_for_timeout(60)
            problems += [f"{step}@scroll{y}: {x}" for x in pg.evaluate(PROBE)]
        if out_dir and step == "preview":
            pg.evaluate("window.scrollTo(0, 0)")
            pg.screenshot(path=str(out_dir / f"{theme}-{w}x{h}@{z}.png"))


def main():
    exe = sys.argv[sys.argv.index("--chrome") + 1] if "--chrome" in sys.argv else None
    out_dir = pathlib.Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=str(ROOT)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/"
    combos = [(w, h, 1.0) for w, h in VIEWPORTS] + ZOOMS
    if "--quick" in sys.argv:
        combos = [(1024, 460, 1.0), (1366, 768, 1.0), (412, 915, 1.0)]
    bad = 0
    with sync_playwright() as p:
        b = p.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--no-sandbox"])
        for theme in ("dark", "light"):
            for w, h, z in combos:
                cw, ch = round(w / z), round(h / z)
                mobile = cw < 600
                ctx = b.new_context(viewport={"width": cw, "height": ch}, device_scale_factor=z if not mobile else 2.5,
                                    is_mobile=mobile, has_touch=mobile)
                pg = ctx.new_page()
                pg.set_default_timeout(6000)
                pg.add_init_script(f"localStorage.setItem('queryopsy.theme','{theme}');"
                                   "localStorage.setItem('queryopsy.progress.v1', JSON.stringify({onboarded:true}))")
                pg.goto(base + "?app=0#/case/case01_funding/2")
                pg.wait_for_function("document.documentElement.dataset.engine === 'ready'", timeout=90000)
                pg.wait_for_selector("#sql", state="attached")
                problems = []
                try:
                    run_steps(pg, mobile, problems, out_dir, theme, w, h, z)
                except Exception as e:  # an interaction that cannot happen is a layout bug too
                    problems.append("interaction failed: " + str(e).splitlines()[0][:160])
                problems = sorted(set(problems))
                problems = sorted(set(problems))
                tag = f"{theme:5} {w}x{h} zoom {z} (css {cw}x{ch})"
                print(("OK   " if not problems else "FAIL ") + tag)
                for x in problems[:12]:
                    print("       -", x)
                bad += bool(problems)
                ctx.close()
        b.close()
    print(f"\n{bad} failing combination(s)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
