"""Minimal SVG helper for IEEE-style line figures (units = pt)."""
import math

FONT = "Liberation Sans, Arial, Helvetica, sans-serif"
PROPOSED_FILL = "#EDEDED"


class SVG:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.el = []

    # ---------- primitives ----------
    def raw(self, s):
        self.el.append(s)

    def rect(self, x, y, w, h, dashed=False, fill="#FFFFFF", sw=0.8, rx=0):
        da = ' stroke-dasharray="3,2"' if dashed else ""
        self.el.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" rx="{rx}" '
            f'fill="{fill}" stroke="#000" stroke-width="{sw}"{da}/>')

    def line(self, pts, sw=0.8, dashed=False, arrow_end=False, arrow_start=False, color="#000"):
        d = "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
        da = ' stroke-dasharray="3,2"' if dashed else ""
        me = ' marker-end="url(#ah)"' if arrow_end else ""
        ms = ' marker-start="url(#ahs)"' if arrow_start else ""
        self.el.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}"{da}{me}{ms}/>')

    def text(self, x, y, s, size=7.0, anchor="middle", weight="normal", style="normal", color="#000"):
        s = (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        self.el.append(
            f'<text x="{x:.2f}" y="{y:.2f}" font-family="{FONT}" font-size="{size}" '
            f'text-anchor="{anchor}" font-weight="{weight}" font-style="{style}" fill="{color}">{s}</text>')

    def mtext(self, cx, cy, lines, size=7.0, lh=None, weight_first=False, anchor="middle"):
        lh = lh or size * 1.2
        n = len(lines)
        y0 = cy - (n - 1) * lh / 2 + size * 0.35
        for i, s in enumerate(lines):
            w = "bold" if (weight_first and i == 0) else "normal"
            self.text(cx, y0 + i * lh, s, size=size, anchor=anchor, weight=w)

    def box(self, x, y, w, h, lines, size=7.0, dashed=False, proposed=False, bold_first=True, sw=0.8):
        fill = PROPOSED_FILL if proposed else "#FFFFFF"
        self.rect(x, y, w, h, dashed=dashed or proposed, fill=fill, sw=sw)
        self.mtext(x + w / 2, y + h / 2, lines, size=size, weight_first=bold_first)
        return (x, y, w, h)

    def diamond(self, cx, cy, w, h, lines, size=6.6):
        pts = [(cx, cy - h / 2), (cx + w / 2, cy), (cx, cy + h / 2), (cx - w / 2, cy)]
        d = " ".join(f"{a:.2f},{b:.2f}" for a, b in pts)
        self.el.append(f'<polygon points="{d}" fill="#FFFFFF" stroke="#000" stroke-width="0.8"/>')
        self.mtext(cx, cy, lines, size=size)

    def terminal(self, cx, cy, w, h, s, size=7.0):
        self.el.append(
            f'<rect x="{cx-w/2:.2f}" y="{cy-h/2:.2f}" width="{w:.2f}" height="{h:.2f}" rx="{h/2:.2f}" '
            f'fill="#FFFFFF" stroke="#000" stroke-width="0.8"/>')
        self.text(cx, cy + size * 0.35, s, size=size, weight="bold")

    def circle(self, cx, cy, r, fill="#FFFFFF", sw=0.8):
        self.el.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{fill}" stroke="#000" stroke-width="{sw}"/>')

    def dot(self, cx, cy, r=1.4):
        self.el.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r}" fill="#000"/>')

    # ---------- schematic symbols ----------
    def ground(self, x, y):
        self.line([(x, y), (x, y + 4)])
        for i, hw in enumerate((5, 3.2, 1.4)):
            yy = y + 4 + i * 1.8
            self.line([(x - hw, yy), (x + hw, yy)], sw=0.8)

    def resistor_v(self, x, y1, y2, label=None):
        """vertical zig-zag resistor between y1 and y2."""
        L = y2 - y1
        lead = L * 0.2
        zz = [(x, y1), (x, y1 + lead)]
        n = 6
        seg = (L - 2 * lead) / n
        for i in range(n):
            zz.append((x + (3 if i % 2 == 0 else -3), y1 + lead + seg * (i + 0.5)))
        zz += [(x, y2 - lead), (x, y2)]
        self.line(zz, sw=0.8)
        if label:
            self.text(x + 5, (y1 + y2) / 2 + 2.3, label, size=6.2, anchor="start")

    def resistor_h(self, x1, x2, y, label=None):
        L = x2 - x1
        lead = L * 0.2
        zz = [(x1, y), (x1 + lead, y)]
        n = 6
        seg = (L - 2 * lead) / n
        for i in range(n):
            zz.append((x1 + lead + seg * (i + 0.5), y + (3 if i % 2 == 0 else -3)))
        zz += [(x2 - lead, y), (x2, y)]
        self.line(zz, sw=0.8)
        if label:
            self.text((x1 + x2) / 2, y - 5, label, size=6.2)

    def capacitor_v(self, x, y1, y2, label=None, polar=True):
        m = (y1 + y2) / 2
        self.line([(x, y1), (x, m - 1.5)])
        self.line([(x - 5, m - 1.5), (x + 5, m - 1.5)], sw=1.1)
        if polar:
            self.el.append(f'<path d="M {x-5:.2f},{m+3:.2f} Q {x:.2f},{m+0.6:.2f} {x+5:.2f},{m+3:.2f}" fill="none" stroke="#000" stroke-width="1.1"/>')
            self.text(x - 7.5, m - 2.5, "+", size=6)
        else:
            self.line([(x - 5, m + 1.5), (x + 5, m + 1.5)], sw=1.1)
        self.line([(x, m + (2 if polar else 1.5)), (x, y2)])
        if label:
            self.text(x + 7, m + 2.3, label, size=6.2, anchor="start")

    def pushbutton_v(self, x, y1, y2, label=None):
        m = (y1 + y2) / 2
        self.line([(x, y1), (x, m - 4)])
        self.line([(x, m + 4), (x, y2)])
        self.dot(x, m - 4, 1.0)
        self.dot(x, m + 4, 1.0)
        self.line([(x - 4, m - 5.5), (x - 4, m + 5.5)])  # actuator bar
        self.line([(x - 4, m), (x - 8, m)])
        if label:
            self.text(x + 5, m + 2.3, label, size=6.2, anchor="start")

    def fuse_h(self, x1, x2, y, label=None):
        self.line([(x1, y), (x2, y)])
        self.rect(x1 + (x2 - x1) * 0.25, y - 2.5, (x2 - x1) * 0.5, 5, sw=0.8)
        if label:
            self.text((x1 + x2) / 2, y - 5, label, size=6.2)

    def antenna(self, x, y, label=None):
        self.line([(x, y), (x, y - 9)])
        self.line([(x - 4.5, y - 15), (x, y - 9), (x + 4.5, y - 15)])
        self.line([(x, y - 9), (x, y - 15)])
        if label:
            self.text(x + 6, y - 9, label, size=6.2, anchor="start")

    # ---------- output ----------
    def save(self, path):
        head = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}pt" height="{self.h}pt" '
                f'viewBox="0 0 {self.w} {self.h}">\n'
                '<defs>\n'
                '<marker id="ah" viewBox="0 0 8 8" refX="7.2" refY="4" markerWidth="5.2" markerHeight="5.2" orient="auto">'
                '<path d="M0,0.6 L7.6,4 L0,7.4 z" fill="#000"/></marker>\n'
                '<marker id="ahs" viewBox="0 0 8 8" refX="0.8" refY="4" markerWidth="5.2" markerHeight="5.2" orient="auto">'
                '<path d="M7.6,0.6 L0,4 L7.6,7.4 z" fill="#000"/></marker>\n'
                '</defs>\n'
                f'<rect x="0" y="0" width="{self.w}" height="{self.h}" fill="#FFFFFF"/>\n')
        with open(path, "w") as f:
            f.write(head + "\n".join(self.el) + "\n</svg>\n")
