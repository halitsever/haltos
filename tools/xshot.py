#!/usr/bin/env python3
"""Captures one X window (by id) or the root window to PNG. Usage: xshot.py OUT.png [WINDOW_ID]"""
import struct
import subprocess
import sys

from PIL import Image

target = ["-id", sys.argv[2]] if len(sys.argv) > 2 else ["-root"]
raw = subprocess.run(["xwd", *target, "-silent"], check=True, capture_output=True).stdout
h = struct.unpack(">25I", raw[:100])
w, ht, bpp, bpl, order = h[4], h[5], h[11], h[12], h[7]
mode = {32: ("BGRX", "XRGB"), 24: ("BGR", "RGB")}[bpp][0 if order == 0 else 1]
Image.frombuffer("RGB", (w, ht), raw[h[0] + h[19] * 12 :], "raw", mode, bpl, 1).save(sys.argv[1])
