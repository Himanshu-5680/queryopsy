"""Audit certificate: drawn on a <canvas> from Python, exported as PNG or as a PDF built in pure Python.

The PDF writer embeds the canvas as a JPEG (DCTDecode) on an A4-landscape page - no
PDF library needed, so it works offline in the browser and inside the Android app.
"""
from __future__ import annotations

import base64
import hashlib
import time

INK, PAPER, ORANGE, PURPLE, GREEN = "#0B0B0B", "#F4F0EA", "#FF5722", "#A855F7", "#16A34A"


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


def _box(ctx, x, y, w, h, fill, shadow=10, line=6):
    ctx.fillStyle = INK
    ctx.fillRect(x + shadow, y + shadow, w, h)
    ctx.fillStyle = fill
    ctx.fillRect(x, y, w, h)
    ctx.lineWidth = line
    ctx.strokeStyle = INK
    ctx.strokeRect(x, y, w, h)


def draw(app, canvas) -> dict:
    s = summary(app)
    ctx = canvas.getContext("2d")
    W, H = canvas.width, canvas.height
    ctx.fillStyle = PAPER
    ctx.fillRect(0, 0, W, H)
    ctx.fillStyle = "#E4DDD1"                       # dotted paper texture
    for yy in range(30, H, 34):
        for xx in range(30, W, 34):
            ctx.fillRect(xx, yy, 3, 3)
    _box(ctx, 50, 50, W - 110, H - 110, "#FFFFFF", 14, 8)
    _box(ctx, 50, 50, W - 110, 150, ORANGE, 0, 8)
    ctx.fillStyle = INK
    ctx.font = "700 30px 'JetBrains Mono', monospace"
    ctx.fillText("QUERYOPSY // ZERO-SERVER SQL FORENSICS", 100, 115)
    ctx.font = "700 62px 'Space Grotesk', sans-serif"
    ctx.fillText("Certificate of SQL Audit", 100, 175)
    ctx.font = "500 30px 'Space Grotesk', sans-serif"
    ctx.fillText("This certifies that", 100, 285)
    ctx.font = "700 84px 'Space Grotesk', sans-serif"
    name = s["name"] if len(s["name"]) <= 26 else s["name"][:25] + "."
    ctx.fillText(name, 100, 380)
    ctx.fillStyle = PURPLE
    ctx.fillRect(100, 400, min(ctx.measureText(name).width, W - 300), 10)
    ctx.fillStyle = INK
    ctx.font = "500 30px 'Space Grotesk', sans-serif"
    ctx.fillText(f"proved {s['proven']} of {s['total']} forensic findings with SQL and closed {s['closed']} case file(s).", 100, 470)
    y = 540
    ctx.font = "700 24px 'JetBrains Mono', monospace"
    for c in s["cases"]:
        done = c["done"] == c["total"]
        ctx.fillStyle = GREEN if done else ("#B45309" if c["done"] else "#8A847C")
        ctx.fillText("[x]" if done else ("[~]" if c["done"] else "[ ]"), 100, y)
        ctx.fillStyle = INK
        ctx.fillText(f"Case {c['no']:02d}  {c['title']}", 170, y)
        ctx.fillText(f"{c['done']}/{c['total']}", 960, y)
        y += 46
    _box(ctx, 1110, 520, 380, 300, PAPER, 8, 5)
    ctx.fillStyle = INK
    ctx.font = "700 22px 'JetBrains Mono', monospace"
    ctx.fillText("AUDIT RECORD", 1140, 565)
    ctx.font = "500 22px 'JetBrains Mono', monospace"
    for i, line in enumerate((f"Findings  {s['proven']}/{s['total']}", f"Hints     {s['hints']}", f"Date      {s['date']}",
                              f"Engine    SQLite/WASM", f"ID        {s['id']}")):
        ctx.fillText(line, 1140, 610 + i * 40)
    ctx.save()
    ctx.translate(1300, 900)
    ctx.rotate(-0.14)
    ctx.strokeStyle = GREEN if s["closed"] else "#8A847C"
    ctx.lineWidth = 8
    ctx.strokeRect(-190, -50, 380, 100)
    ctx.fillStyle = GREEN if s["closed"] else "#8A847C"
    ctx.font = "700 46px 'JetBrains Mono', monospace"
    ctx.textAlign = "center"
    ctx.fillText("VERIFIED" if s["closed"] else "IN PROGRESS", 0, 16)
    ctx.restore()
    ctx.textAlign = "left"
    ctx.fillStyle = "#5B5650"
    ctx.font = "500 20px 'JetBrains Mono', monospace"
    ctx.fillText("Verified on-device by the Queryopsy validation engine.", 100, H - 110)
    ctx.fillText(f"Certificate ID {s['id']} - recompute from the same progress to verify.", 100, H - 80)
    return s


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
