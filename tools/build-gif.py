#!/usr/bin/env python3
"""Joins the PNG frames from marketing/motion (?frames=8&size=1020) into docs/haltos.gif."""
import glob
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS = 8


def main():
    paths = sorted(glob.glob(os.path.join(ROOT, "marketing", "motion", "out", "frame-*.png")))
    if not paths:
        sys.exit("no frames in marketing/motion/out, open the motion page with ?frames=8&size=1020 first")
    frames = [Image.open(p).convert("RGB") for p in paths]
    # One palette for every frame lets the GIF store only what changed, about 5x smaller than per-frame palettes.
    sample = frames[:: max(1, len(frames) // 20)]
    tile = 340
    sheet = Image.new("RGB", (tile * len(sample), tile))
    for i, f in enumerate(sample):
        sheet.paste(f.resize((tile, tile)), (i * tile, 0))
    palette = sheet.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    out = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
    path = os.path.join(ROOT, "docs", "haltos.gif")
    out[0].save(path, save_all=True, append_images=out[1:], duration=1000 // FPS, loop=0, optimize=True)
    print(f"{path}: {len(frames)} frames, {os.path.getsize(path) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
