#!/usr/bin/env python3
"""Generates every HaltOS logo, icon, wallpaper and ASCII banner from one ANSI Shadow glyph set."""
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAND = os.path.join(ROOT, "branding")
FONT_DIR = "/usr/share/fonts/truetype/jetbrains-mono"

FG = (250, 250, 250)
DIM = (113, 113, 122)
BG = (9, 9, 11)

FONT = {
    "H": ["██╗  ██╗", "██║  ██║", "███████║", "██╔══██║", "██║  ██║", "╚═╝  ╚═╝"],
    "A": [" █████╗ ", "██╔══██╗", "███████║", "██╔══██║", "██║  ██║", "╚═╝  ╚═╝"],
    "L": ["██╗     ", "██║     ", "██║     ", "██║     ", "███████╗", "╚══════╝"],
    "T": ["████████╗", "╚══██╔══╝", "   ██║   ", "   ██║   ", "   ██║   ", "   ╚═╝   "],
    "O": [" ██████╗ ", "██╔═══██╗", "██║   ██║", "██║   ██║", "╚██████╔╝", " ╚═════╝ "],
    "S": ["███████╗", "██╔════╝", "███████╗", "╚════██║", "███████║", "╚══════╝"],
}

MARK = [
    "██╗  ██╗    ",
    "██║  ██║    ",
    "███████║    ",
    "██╔══██║    ",
    "██║  ██║ ▄▄▄",
    "╚═╝  ╚═╝    ",
]


def banner(text):
    """Joins glyphs with figlet-style kerning so letters touch without overlapping."""
    rows = [""] * 6
    for ch in text:
        glyph = FONT[ch]
        if not rows[0]:
            rows = list(glyph)
            continue
        shift = min(
            (len(r) - len(r.rstrip(" "))) + (len(g) - len(g.lstrip(" "))) for r, g in zip(rows, glyph)
        )
        out = []
        for r, g in zip(rows, glyph):
            base = list(r + " " * (len(g) - shift))
            for i, c in enumerate(g):
                if c != " ":
                    base[len(r) - shift + i] = c
            out.append("".join(base))
        rows = out
    return rows


def cell_rects(ch, x, y, w, h):
    """Returns the filled rectangles that draw one box-drawing character inside a w*h cell."""
    t = w * 0.13
    d = w * 0.2
    cx, cy = x + w / 2, y + h / 2

    def hl(x0, x1, yy):
        return (x0, yy - t / 2, x1, yy + t / 2)

    def vl(xx, y0, y1):
        return (xx - t / 2, y0, xx + t / 2, y1)

    e = t / 2
    return {
        "█": [(x, y, x + w, y + h)],
        "▄": [(x, y + h / 2, x + w, y + h)],
        "═": [hl(x, x + w, cy - d), hl(x, x + w, cy + d)],
        "║": [vl(cx - d, y, y + h), vl(cx + d, y, y + h)],
        "╗": [hl(x, cx + d + e, cy - d), vl(cx + d, cy - d - e, y + h), hl(x, cx - d + e, cy + d), vl(cx - d, cy + d - e, y + h)],
        "╔": [hl(cx - d - e, x + w, cy - d), vl(cx - d, cy - d - e, y + h), hl(cx + d - e, x + w, cy + d), vl(cx + d, cy + d - e, y + h)],
        "╚": [vl(cx - d, y, cy + d + e), hl(cx - d - e, x + w, cy + d), vl(cx + d, y, cy - d + e), hl(cx + d - e, x + w, cy - d)],
        "╝": [vl(cx + d, y, cy + d + e), hl(x, cx + d + e, cy + d), vl(cx - d, y, cy - d + e), hl(x, cx - d + e, cy - d)],
    }.get(ch, [])


def grid_rects(rows, cw, ch, ox=0.0, oy=0.0, blocks_only=False):
    rects = []
    for r, line in enumerate(rows):
        for c, char in enumerate(line):
            if blocks_only and char not in "█▄":
                continue
            rects += cell_rects(char, ox + c * cw, oy + r * ch, cw, ch)
    return rects


def grid_svg(rows, cw, ch, pad, bg=None):
    w = max(map(len, rows)) * cw + 2 * pad
    h = len(rows) * ch + 2 * pad
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:g} {h:g}" width="{w:g}" height="{h:g}">']
    if bg:
        parts.append(f'<rect width="{w:g}" height="{h:g}" rx="{w * 0.16:g}" fill="{bg}"/>')
    parts.append('<g fill="#fafafa">')
    for x0, y0, x1, y1 in grid_rects(rows, cw, ch, pad, pad):
        parts.append(f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{x1 - x0:.2f}" height="{y1 - y0:.2f}"/>')
    parts.append("</g></svg>\n")
    return "".join(parts)


def draw_grid(img, rows, cw, ch, ox, oy, color, blocks_only=False):
    d = ImageDraw.Draw(img)
    for x0, y0, x1, y1 in grid_rects(rows, cw, ch, ox, oy, blocks_only):
        d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=color)


def mark_png(size, tile):
    ss = 4
    s = size * ss
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    pad = s * (0.14 if tile else 0.06)
    if tile:
        ImageDraw.Draw(img).rounded_rectangle([0, 0, s - 1, s - 1], radius=s * 0.18, fill=BG + (255,))
    cw = (s - 2 * pad) / 12
    draw_grid(img, MARK, cw, cw * 2 * 0.5 * 2, pad, pad, FG + (255,), blocks_only=size <= 32)
    return img.resize((size, size), Image.LANCZOS)


START_DOT = 0.2


def start_png(size):
    ss = 8
    s = size * ss
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    r = s * START_DOT
    ImageDraw.Draw(img).ellipse([s / 2 - r, s / 2 - r, s / 2 + r, s / 2 + r], fill=FG + (255,))
    return img.resize((size, size), Image.LANCZOS)


def glow(layer, radius, strength=2):
    blurred = layer.filter(ImageFilter.GaussianBlur(radius))
    out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    for _ in range(strength):
        out = Image.alpha_composite(out, blurred)
    return Image.alpha_composite(out, layer)


def scanlines(img, k):
    lines = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(lines)
    step = max(2, round(3 * k))
    for y in range(0, img.size[1], step):
        ld.line([(0, y), (img.size[0], y)], fill=(0, 0, 0, 45))
    return Image.alpha_composite(img, lines)


def wallpaper(w, h, seed=0x48):
    rng = random.Random(seed)
    k = h / 1080
    base = Image.new("RGBA", (w, h), BG + (255,))

    # Radial falloff keeps the edges dark so desktop icons stay readable.
    vignette = Image.new("L", (w, h), 0)
    vd = ImageDraw.Draw(vignette)
    for i in range(60):
        t = i / 60
        rx, ry = w * (0.75 - 0.6 * t), h * (0.75 - 0.6 * t)
        vd.ellipse([w / 2 - rx, h * 0.45 - ry, w / 2 + rx, h * 0.45 + ry], fill=int(22 * t))
    base = Image.composite(Image.new("RGBA", (w, h), (39, 39, 42, 255)), base, vignette)

    hexl = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hexl)
    hf = ImageFont.truetype(os.path.join(FONT_DIR, "JetBrainsMono-Regular.ttf"), max(10, round(14 * k)))
    col_w, row_h = round(26 * k), round(20 * k)
    for x in range(0, w, col_w):
        edge = min(x, w - x) / (w / 2)
        if edge > 0.32:
            continue
        for y in range(0, h, row_h):
            if rng.random() < 0.55:
                a = int((1 - edge / 0.32) * rng.randint(8, 26))
                hd.text((x, y), f"{rng.randrange(256):02x}", font=hf, fill=FG + (a,))
    base = Image.alpha_composite(base, hexl)

    rows = banner("HALTOS")
    cols = max(map(len, rows))
    cw = round(w * 0.5 / cols)
    ch = cw * 2
    bw, bh = cols * cw, 6 * ch
    ox, oy = (w - bw) // 2, round(h * 0.42 - bh / 2)
    fg = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_grid(fg, rows, cw, ch, ox, oy, FG + (255,))

    fd = ImageDraw.Draw(fg)
    sub_font = ImageFont.truetype(os.path.join(FONT_DIR, "JetBrainsMono-Regular.ttf"), round(22 * k))
    sub = "root@haltos:~# shutdown -h never"
    sw = fd.textlength(sub + "_", font=sub_font)
    sy = oy + bh + round(56 * k)
    fd.text(((w - sw) / 2, sy), sub, font=sub_font, fill=DIM + (255,))
    cx = (w - sw) / 2 + fd.textlength(sub, font=sub_font) + round(4 * k)
    fd.rectangle([cx, sy + round(4 * k), cx + round(12 * k), sy + round(26 * k)], fill=FG + (255,))

    tag_font = ImageFont.truetype(os.path.join(FONT_DIR, "JetBrainsMono-Regular.ttf"), round(15 * k))
    tag = "v1.0 // SIGKILL"
    fd.text((ox + bw - fd.textlength(tag, font=tag_font), oy - round(30 * k)), tag, font=tag_font, fill=DIM + (255,))

    base = Image.alpha_composite(base, glow(fg, round(10 * k), strength=1))
    return scanlines(base, k).convert("RGB")


def splash_wordmark(path):
    rows = banner("HALTOS")
    cw = 14
    img = Image.new("RGBA", (max(map(len, rows)) * cw, 6 * cw * 2), (0, 0, 0, 0))
    draw_grid(img, rows, cw, cw * 2, 0, 0, FG + (255,))
    img.save(path)
    return img.size


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def main():
    write(os.path.join(BRAND, "haltos-logo.svg"), grid_svg(MARK, 10, 20, 6))
    write(os.path.join(BRAND, "haltos-logo-tile.svg"), grid_svg(MARK, 10, 20, 18, bg="#09090b"))
    write(os.path.join(BRAND, "haltos-wordmark.svg"), grid_svg(banner("HALTOS"), 10, 20, 4))

    ascii_dir = os.path.join(BRAND, "ascii")
    write(os.path.join(ascii_dir, "mark.txt"), "\n".join(MARK) + "\n")
    write(os.path.join(ascii_dir, "wordmark.txt"), "\n".join(banner("HALTOS")) + "\n")
    write(
        os.path.join(ROOT, "system", "fastfetch", "haltos.txt"),
        "".join(f"$1{line}\n" for line in banner("HALTOS")) + "$2  v1.0 // SIGKILL\n",
    )

    icons = os.path.join(BRAND, "icons", "hicolor")
    for size in (16, 22, 24, 32, 48, 64, 128, 256, 512):
        out = os.path.join(icons, f"{size}x{size}", "apps")
        os.makedirs(out, exist_ok=True)
        mark_png(size, tile=size <= 32).save(os.path.join(out, "haltos-logo.png"))
    write(os.path.join(icons, "scalable", "apps", "haltos-logo.svg"), grid_svg(MARK, 10, 20, 6))

    for size in (16, 22, 24, 32, 48, 64, 128, 256):
        start_png(size).save(os.path.join(icons, f"{size}x{size}", "apps", "haltos-start.png"))
    write(
        os.path.join(icons, "scalable", "apps", "haltos-start.svg"),
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">'
        f'<circle cx="32" cy="32" r="{64 * START_DOT:g}" fill="#fafafa"/></svg>\n',
    )

    splash_img = os.path.join(ROOT, "plasma", "look-and-feel", "org.haltos.mono", "contents", "splash", "images")
    os.makedirs(splash_img, exist_ok=True)
    for stale in ("haltos-logo.svg",):
        p = os.path.join(splash_img, stale)
        if os.path.exists(p):
            os.remove(p)
    print("splash wordmark", splash_wordmark(os.path.join(splash_img, "wordmark.png")), file=sys.stderr)

    wp = os.path.join(BRAND, "wallpapers", "HaltOS", "contents", "images")
    os.makedirs(wp, exist_ok=True)
    for w, h in [(1920, 1080), (2560, 1440), (3840, 2160), (1512, 949)]:
        wallpaper(w, h).save(os.path.join(wp, f"{w}x{h}.png"), optimize=True)
        print(f"wallpaper {w}x{h}", file=sys.stderr)
    write(
        os.path.join(BRAND, "wallpapers", "HaltOS", "metadata.json"),
        '{\n  "KPlugin": {\n    "Id": "HaltOS",\n    "Name": "HaltOS",\n'
        '    "Authors": [{ "Name": "HaltOS" }],\n    "License": "CC-BY-SA-4.0"\n  }\n}\n',
    )


if __name__ == "__main__":
    main()
