"""Audit certificate: drawn on a <canvas> from Python, exported as PNG or as a PDF built in pure Python.

The PDF writer embeds the canvas as a JPEG (DCTDecode) on an A4-landscape page - no
PDF library needed, so it works offline in the browser and inside the Android app.
"""
from __future__ import annotations

import base64
import hashlib
import time

INK, PAPER, RED, NAVY, GREEN, MUTED = "#1E1A15", "#FBF6E9", "#B3261E", "#1F3A5F", "#2E6B34", "#6B6156"
TYPE, DISPLAY, CODE = "'Courier Prime', 'Courier New', monospace", "'Special Elite', 'Courier Prime', monospace", "'JetBrains Mono', monospace"
FONTS = ("700 28px 'Courier Prime'", "400 28px 'Courier Prime'", "400 40px 'Special Elite'")


def summary(app) -> dict:
    cases = []
    for c in app.cases:
        d, t = app.case_progress(c)
        cases.append({"title": c["title"], "no": c["no"], "done": d, "total": t})
    proven, total = app.total_progress()
    hints = sum(app.store.hints(lv["id"]) for c in app.cases for lv in c["levels"] if app.store.solved(lv["id"]))
    name = (app.store.get("name") or "").strip() or "Lead Data Auditor"
    stamp = ",".join(sorted(app.store.data["solved"]))
    cert_id = hashlib.sha256(f"{name}|{stamp}".encode()).hexdigest()[:12].upper()
    return {"name": name, "cases": cases, "proven": proven, "total": total, "hints": hints,
            "closed": sum(1 for c in cases if c["done"] == c["total"]), "id": cert_id, "date": time.strftime("%d %b %Y")}


def _stamp(ctx, x, y, text, color, size=46, angle=-0.14, pad=26):
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(angle)
    ctx.font = f"400 {size}px {DISPLAY}"
    w = ctx.measureText(text).width + pad * 2
    h = size + pad
    ctx.globalAlpha = 0.85
    ctx.strokeStyle = color
    ctx.lineWidth = 6
    ctx.strokeRect(-w / 2, -h / 2, w, h)
    ctx.lineWidth = 2
    ctx.strokeRect(-w / 2 + 9, -h / 2 + 9, w - 18, h - 18)
    ctx.fillStyle = color
    ctx.textAlign = "center"
    ctx.textBaseline = "middle"
    ctx.fillText(text, 0, 3)
    ctx.restore()


def _clip(ctx, x, y):
    ctx.save()
    ctx.strokeStyle = "#8E9296"
    ctx.lineWidth = 6
    for (w, h, dx, dy) in ((34, 110, 0, 0), (20, 76, 7, 14)):
        r = w / 2
        ctx.beginPath()
        ctx.moveTo(x + dx, y + dy + r)
        ctx.arc(x + dx + r, y + dy + r, r, 3.14159, 0)
        ctx.lineTo(x + dx + w, y + dy + h - r)
        ctx.arc(x + dx + r, y + dy + h - r, r, 0, 3.14159)
        ctx.closePath()
        ctx.stroke()
    ctx.restore()


def draw(app, canvas) -> dict:
    """Official forensic audit report (1600 x 1130 canvas)."""
    s = summary(app)
    ctx = canvas.getContext("2d")
    W, H = canvas.width, canvas.height
    ctx.textBaseline = "alphabetic"
    ctx.textAlign = "left"
    ctx.fillStyle = "#D9CBAE"                                   # desk
    ctx.fillRect(0, 0, W, H)
    ctx.fillStyle = "rgba(0,0,0,0.18)"                          # paper shadow
    ctx.fillRect(58, 62, W - 104, H - 104)
    ctx.fillStyle = PAPER
    ctx.fillRect(46, 46, W - 104, H - 104)
    ctx.strokeStyle = "rgba(31,58,95,0.08)"                     # faint ruled paper
    ctx.lineWidth = 1
    for yy in range(300, H - 80, 38):
        ctx.beginPath()
        ctx.moveTo(90, yy)
        ctx.lineTo(W - 100, yy)
        ctx.stroke()
    ctx.strokeStyle = NAVY
    ctx.lineWidth = 4
    ctx.strokeRect(70, 70, W - 152, H - 152)
    ctx.lineWidth = 1.5
    ctx.strokeRect(80, 80, W - 172, H - 172)
    _clip(ctx, 150, 20)
    # letterhead
    ctx.fillStyle = INK
    ctx.font = f"400 50px {DISPLAY}"
    ctx.fillText("BUREAU OF DATA FORENSICS", 230, 160)
    ctx.font = f"700 22px {TYPE}"
    ctx.fillStyle = MUTED
    ctx.fillText("QUERYOPSY  //  OFFICIAL FORENSIC AUDIT REPORT", 232, 198)
    ctx.textAlign = "right"
    ctx.fillStyle = INK
    ctx.font = f"700 22px {TYPE}"
    ctx.fillText(f"REPORT NO. QX-{s['id']}", W - 130, 150)
    ctx.fillText(f"DATE  {s['date'].upper()}", W - 130, 182)
    ctx.textAlign = "left"
    ctx.fillStyle = RED
    ctx.fillRect(120, 224, W - 240, 4)
    ctx.fillRect(120, 232, W - 240, 1.5)
    _stamp(ctx, W - 300, 300, "CONFIDENTIAL", RED, 34, 0.1, 18)
    # certification
    ctx.fillStyle = INK
    ctx.font = f"400 30px {TYPE}"
    ctx.fillText("This report certifies that the investigator", 130, 300)
    name = s["name"] if len(s["name"]) <= 28 else s["name"][:27] + "."
    ctx.font = f"400 74px {DISPLAY}"
    ctx.fillText(name, 130, 392)
    ctx.fillStyle = RED
    ctx.fillRect(130, 408, min(ctx.measureText(name).width + 20, W - 560), 4)
    ctx.fillStyle = INK
    ctx.font = f"400 28px {TYPE}"
    ctx.fillText(f"proved {s['proven']} of {s['total']} forensic findings with SQL and closed {s['closed']} case file(s).", 130, 462)
    ctx.fillStyle = MUTED
    ctx.font = f"400 22px {TYPE}"
    ctx.fillText("Evidence examined on-device. Source records: ", 130, 500)
    ctx.fillStyle = INK
    ctx.fillRect(130 + ctx.measureText("Evidence examined on-device. Source records: ").width, 482, 220, 24)
    # case register table
    x0, y0, widths = 130, 560, (150, 560, 180, 190)
    heads = ("FILE NO.", "CASE", "EXHIBITS", "STATUS")
    ctx.fillStyle = NAVY
    ctx.fillRect(x0, y0 - 34, sum(widths), 46)
    ctx.fillStyle = "#FFFFFF"
    ctx.font = f"700 22px {TYPE}"
    xx = x0
    for h_, w_ in zip(heads, widths):
        ctx.fillText(h_, xx + 14, y0 - 4)
        xx += w_
    y = y0 + 12
    ctx.font = f"700 22px {TYPE}"
    for c in s["cases"]:
        done = c["done"] == c["total"]
        status, col = ("CLOSED", GREEN) if done else (("OPEN", "#9A5B0F") if c["done"] else ("NOT OPENED", MUTED))
        ctx.strokeStyle = "rgba(30,26,21,0.25)"
        ctx.lineWidth = 1.5
        ctx.beginPath()
        ctx.moveTo(x0, y + 44)
        ctx.lineTo(x0 + sum(widths), y + 44)
        ctx.stroke()
        ctx.fillStyle = INK
        ctx.fillText(f"QX/{c['no']:02d}", x0 + 14, y + 30)
        title = c["title"] if len(c["title"]) <= 34 else c["title"][:33] + "."
        ctx.font = f"400 22px {TYPE}"
        ctx.fillText(title, x0 + widths[0] + 14, y + 30)
        ctx.font = f"700 22px {TYPE}"
        ctx.fillText(f"{c['done']} / {c['total']}", x0 + widths[0] + widths[1] + 14, y + 30)
        ctx.fillStyle = col
        ctx.fillText(status, x0 + widths[0] + widths[1] + widths[2] + 14, y + 30)
        y += 44
    # audit record card (evidence tag style)
    bx, by, bw, bh = 1230, 520, 270, 300
    ctx.fillStyle = "#F1D98A"
    ctx.beginPath()
    ctx.moveTo(bx + 30, by)
    ctx.lineTo(bx + bw, by)
    ctx.lineTo(bx + bw, by + bh)
    ctx.lineTo(bx, by + bh)
    ctx.lineTo(bx, by + 30)
    ctx.closePath()
    ctx.fill()
    ctx.strokeStyle = INK
    ctx.lineWidth = 2.5
    ctx.stroke()
    ctx.beginPath()
    ctx.arc(bx + 34, by + 34, 9, 0, 6.2832)
    ctx.fillStyle = PAPER
    ctx.fill()
    ctx.stroke()
    ctx.fillStyle = INK
    ctx.font = f"700 20px {TYPE}"
    ctx.fillText("AUDIT RECORD", bx + 58, by + 42)
    ctx.font = f"700 18px {TYPE}"
    for i, line in enumerate((f"Findings {s['proven']}/{s['total']}", f"Closed   {s['closed']} case(s)", f"Hints    {s['hints']}",
                              "Engine   SQLite", f"ID {s['id']}")):
        ctx.fillText(line, bx + 22, by + 96 + i * 40)
    # signature + verdict stamp
    ctx.strokeStyle = INK
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.moveTo(130, H - 170)
    ctx.lineTo(560, H - 170)
    ctx.stroke()
    ctx.font = f"400 34px {DISPLAY}"
    ctx.fillStyle = NAVY
    ctx.fillText(name[:22], 140, H - 182)
    ctx.fillStyle = MUTED
    ctx.font = f"700 18px {TYPE}"
    ctx.fillText("LEAD INVESTIGATOR", 130, H - 144)
    ctx.fillText(f"Verified on-device by the Queryopsy validation engine. Recompute ID {s['id']} from the same progress to verify.", 130, H - 112)
    complete = s["proven"] == s["total"] and s["total"] > 0
    _stamp(ctx, 1240, H - 200, "CASE CLOSED" if complete else ("VERIFIED" if s["closed"] else "IN PROGRESS"),
           GREEN if s["closed"] else MUTED, 54, -0.16, 26)
    return s


def when_fonts_ready(callback) -> None:
    """Canvas only uses web fonts that are loaded: load them, then redraw."""
    try:
        from js import Promise, document
        from pyodide.ffi import create_once_callable, to_js
        Promise.all(to_js([document.fonts.load(f) for f in FONTS])).then(create_once_callable(lambda *_: callback()))
    except Exception:  # noqa: BLE001 - fonts are a nicety; the first draw already happened
        pass


def pdf_from_jpeg(jpeg: bytes, px_w: int, px_h: int) -> bytes:
    """Minimal one-page PDF (A4 landscape) showing a JPEG scaled to fit."""
    pw, ph = 842, 595
    scale = min(pw / px_w, ph / px_h)
    w, h = px_w * scale, px_h * scale
    x, y = (pw - w) / 2, (ph - h) / 2
    content = f"q {w:.2f} 0 0 {h:.2f} {x:.2f} {y:.2f} cm /Im0 Do Q".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {pw} {ph}] /Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>".encode(),
        f"<< /Type /XObject /Subtype /Image /Width {px_w} /Height {px_h} /ColorSpace /DeviceRGB /BitsPerComponent 8 "
        f"/Filter /DCTDecode /Length {len(jpeg)} >>\nstream\n".encode() + jpeg + b"\nendstream",
        f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream",
        b"<< /Title (Queryopsy Audit Certificate) /Producer (Queryopsy) >>",
    ]
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R /Info 6 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def save(filename: str, mime: str, data: bytes) -> None:
    """Download in a browser; hand the bytes to the Android bridge inside the APK."""
    from js import Blob, Object, URL, Uint8Array, document, window
    from pyodide.ffi import create_once_callable, to_js
    if hasattr(window, "AndroidApp") and hasattr(window.AndroidApp, "saveFile"):
        window.AndroidApp.saveFile(filename, mime, base64.b64encode(data).decode())
        return
    arr = Uint8Array.new(len(data))
    arr.assign(data)
    blob = Blob.new(to_js([arr]), to_js({"type": mime}, dict_converter=Object.fromEntries))
    url = URL.createObjectURL(blob)
    a = document.createElement("a")
    a.href, a.download = url, filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.setTimeout(create_once_callable(lambda: URL.revokeObjectURL(url)), 4000)


def download(app, kind: str) -> None:
    from js import document
    canvas = document.getElementById("cert-canvas") or document.createElement("canvas")
    if not canvas.width or canvas.width < 1000:
        canvas.width, canvas.height = 1600, 1130
    s = draw(app, canvas)
    safe = "".join(ch for ch in s["name"] if ch.isalnum() or ch in "-_ ").strip().replace(" ", "_") or "auditor"
    if kind == "png":
        data = base64.b64decode(str(canvas.toDataURL("image/png")).split(",", 1)[1])
        save(f"Queryopsy_Certificate_{safe}.png", "image/png", data)
    else:
        jpeg = base64.b64decode(str(canvas.toDataURL("image/jpeg", 0.92)).split(",", 1)[1])
        save(f"Queryopsy_Certificate_{safe}.pdf", "application/pdf", pdf_from_jpeg(jpeg, canvas.width, canvas.height))
    from ui.dom import toast
    toast("Certificate saved.")
