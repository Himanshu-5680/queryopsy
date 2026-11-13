"""Render a clickable ER diagram (SVG) for a case at build time."""
from __future__ import annotations

from html import escape

from .base import Table

W, ROW, HEAD, GAP_X, GAP_Y, PAD = 230, 22, 34, 70, 40, 16


def render(tables: list[Table], cols: int | None = None) -> str:
    cols = cols or (2 if len(tables) <= 4 else 3)
    boxes, x_heights = {}, [PAD] * cols
    order = sorted(tables, key=lambda t: -sum(1 for c in t.columns if "REFERENCES" in c.extra))
    for i, t in enumerate(order):
        c = i % cols
        h = HEAD + ROW * len(t.columns) + 8
        boxes[t.name] = (PAD + c * (W + GAP_X), x_heights[c], h)
        x_heights[c] += h + GAP_Y
    width = PAD * 2 + cols * W + (cols - 1) * GAP_X + (60 if cols == 1 else 0)
    height = max(x_heights) - GAP_Y + PAD
    lines, parts = [], []
    for t in tables:
        x, y, _ = boxes[t.name]
        for i, c in enumerate(t.columns):
            if "REFERENCES" not in c.extra:
                continue
            target = c.extra.split("REFERENCES", 1)[1].strip().split("(")
            tt, tc = target[0].strip(), target[1].rstrip(")").strip()
            if tt not in boxes:
                continue
            tx, ty, _ = boxes[tt]
            tidx = next((j for j, cc in enumerate(next(z for z in tables if z.name == tt).columns) if cc.name == tc), 0)
            y1 = y + HEAD + ROW * i + ROW / 2
            y2 = ty + HEAD + ROW * tidx + ROW / 2
            if tx > x:
                x1, x2 = x + W, tx
            elif tx < x:
                x1, x2 = x, tx + W
            else:
                x1, x2 = x + W, tx + W
            mid = (x1 + x2) / 2 if tx != x else x1 + 40
            lines.append(f'<path class="erd-link" d="M{x1:.0f},{y1:.0f} C{mid:.0f},{y1:.0f} {mid:.0f},{y2:.0f} {x2:.0f},{y2:.0f}"/>'
                         f'<circle class="erd-dot" cx="{x2:.0f}" cy="{y2:.0f}" r="4"/>')
    for t in tables:
        x, y, h = boxes[t.name]
        parts.append(f'<g class="erd-table" data-table="{escape(t.name)}">'
                     f'<rect class="erd-shadow" x="{x + 5}" y="{y + 5}" width="{W}" height="{h}"/>'
                     f'<rect class="erd-box" x="{x}" y="{y}" width="{W}" height="{h}"/>'
                     f'<rect class="erd-head" x="{x}" y="{y}" width="{W}" height="{HEAD}"/>'
                     f'<text class="erd-title" x="{x + 12}" y="{y + 22}" data-insert="{escape(t.name)}" role="button" tabindex="0">'
                     f'{escape(t.name)}</text>')
        for i, c in enumerate(t.columns):
            cy = y + HEAD + ROW * i + 16
            badge = "PK" if "PRIMARY KEY" in c.extra else ("FK" if "REFERENCES" in c.extra else "")
            parts.append(f'<text class="erd-col" x="{x + 12}" y="{cy}" data-insert="{escape(c.name)}" role="button" tabindex="0">'
                         f'{escape(c.name)}</text><text class="erd-type" x="{x + W - 12}" y="{cy}" text-anchor="end">'
                         f'{"<tspan class=erd-key>" + badge + "</tspan> " if badge else ""}{escape(c.type)}</text>')
        parts.append("</g>")
    return (f'<svg class="erd" viewBox="0 0 {width} {height:.0f}" width="{width}" height="{height:.0f}" role="img" '
            f'aria-label="Entity relationship diagram">{"".join(lines)}{"".join(parts)}</svg>')
