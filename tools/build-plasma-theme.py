#!/usr/bin/env python3
"""Generates the HaltOS Plasma desktop theme. Only the panel is drawn here, everything else falls back to Breeze."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "plasma", "desktoptheme", "haltos")

R = 12
B = 1
MARGIN = 6


def corner(x, y, s, b, sx, sy):
    """Border ring and fill paths for one rounded corner, mirrored from the top-left one."""

    def p(px, py):
        return (x + (px if sx > 0 else s - px), y + (py if sy > 0 else s - py))

    sweep_o = 1 if sx * sy > 0 else 0
    sweep_i = 1 - sweep_o
    a, c, d, e, ctr = p(0, s), p(s, 0), p(s, b), p(b, s), p(s, s)
    ring = (f"M{a[0]:g},{a[1]:g} A{s},{s} 0 0 {sweep_o} {c[0]:g},{c[1]:g} L{d[0]:g},{d[1]:g} "
            f"A{s - b},{s - b} 0 0 {sweep_i} {e[0]:g},{e[1]:g} Z")
    fill = f"M{ctr[0]:g},{ctr[1]:g} L{e[0]:g},{e[1]:g} A{s - b},{s - b} 0 0 {sweep_o} {d[0]:g},{d[1]:g} Z"
    return ring, fill


def frame(prefix, fill, border, y0, fo=1.0, bo=1.0):
    """The nine pieces Plasma's FrameSvg stretches into a panel of any size."""
    s, out = R, []
    pre = f"{prefix}-" if prefix else ""
    f, bd = f'fill="{fill}" fill-opacity="{fo:g}"', f'fill="{border}" fill-opacity="{bo:g}"'
    for name, (cx, sx, sy) in {"topleft": (0, 1, 1), "topright": (2 * s, -1, 1),
                               "bottomleft": (0, 1, -1), "bottomright": (2 * s, -1, -1)}.items():
        cy = y0 if sy > 0 else y0 + 2 * s
        ring, fl = corner(cx, cy, s, B, sx, sy)
        out.append(f'<g id="{pre}{name}"><path d="{fl}" {f}/><path d="{ring}" {bd}/></g>')
    edges = {
        "top": ((s, y0 + B, s, s - B), (s, y0, s, B)),
        "bottom": ((s, y0 + 2 * s, s, s - B), (s, y0 + 3 * s - B, s, B)),
        "left": ((B, y0 + s, s - B, s), (0, y0 + s, B, s)),
        "right": ((2 * s, y0 + s, s - B, s), (3 * s - B, y0 + s, B, s)),
    }
    for name, (fr, br) in edges.items():
        out.append(f'<g id="{pre}{name}"><rect x="{fr[0]}" y="{fr[1]}" width="{fr[2]}" height="{fr[3]}" {f}/>'
                   f'<rect x="{br[0]}" y="{br[1]}" width="{br[2]}" height="{br[3]}" {bd}/></g>')
    out.append(f'<rect id="{pre}center" x="{s}" y="{y0 + s}" width="{s}" height="{s}" {f}/>')
    return out


def panel_svg(fill, border, with_mask, fo=1.0, bo=1.0):
    parts = frame("", fill, border, 0, fo, bo)
    if with_mask:
        # The blur region follows the mask, so it gets the same rounded shape in solid paint.
        parts += frame("mask", "#000000", "#000000", 3 * R + 8)
    h = 6 * R + 16 + 40
    for side, (x, w, hh) in {"top": (0, 1, MARGIN), "bottom": (2, 1, MARGIN), "left": (4, MARGIN, 1), "right": (12, MARGIN, 1)}.items():
        parts.append(f'<rect id="hint-{side}-margin" x="{x}" y="{h - 20}" width="{w}" height="{hh}" fill="none"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{3 * R}" height="{h}" viewBox="0 0 {3 * R} {h}">'
            + "".join(parts) + "</svg>\n")


def main():
    os.makedirs(os.path.join(OUT, "widgets"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "translucent", "widgets"), exist_ok=True)
    meta = {
        "KPackageStructure": "Plasma/Theme",
        "KPlugin": {"Id": "haltos", "Name": "HaltOS", "Description": "HaltOS zinc panel on top of Breeze",
                    "Authors": [{"Name": "HaltOS"}], "License": "GPL-2.0+", "Version": "1.0"},
        "X-Plasma-API-Minimum-Version": "6.0",
    }
    with open(os.path.join(OUT, "metadata.json"), "w") as f:
        json.dump(meta, f, indent=2)
        f.write("\n")
    with open(os.path.join(OUT, "widgets", "panel-background.svg"), "w") as f:
        f.write(panel_svg("#09090b", "#27272a", with_mask=False))
    with open(os.path.join(OUT, "translucent", "widgets", "panel-background.svg"), "w") as f:
        f.write(panel_svg("#09090b", "#52525b", with_mask=True, fo=0.62, bo=0.55))
    print(OUT)


if __name__ == "__main__":
    main()
