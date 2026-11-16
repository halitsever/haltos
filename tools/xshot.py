#!/usr/bin/env python3
"""Captures X11 to PNG. Usage: xshot.py OUT.png [WINDOW_ID | overlay]

`overlay` reads the compositor's output window, the only place KWin draws window decorations.
"""
import ctypes
import struct
import subprocess
import sys

from PIL import Image


def overlay_window():
    x11 = ctypes.CDLL("libX11.so.6")
    xc = ctypes.CDLL("libXcomposite.so.1")
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XDefaultRootWindow.restype = ctypes.c_ulong
    xc.XCompositeGetOverlayWindow.restype = ctypes.c_ulong
    dpy = ctypes.c_void_p(x11.XOpenDisplay(None))
    root = ctypes.c_ulong(x11.XDefaultRootWindow(dpy))
    win = xc.XCompositeGetOverlayWindow(dpy, root)
    return win, lambda: (xc.XCompositeReleaseOverlayWindow(dpy, root), x11.XCloseDisplay(dpy))


release = None
if len(sys.argv) > 2 and sys.argv[2] == "overlay":
    win, release = overlay_window()
    target = ["-id", hex(win)]
elif len(sys.argv) > 2:
    target = ["-id", sys.argv[2]]
else:
    target = ["-root"]
try:
    raw = subprocess.run(["xwd", *target, "-silent"], check=True, capture_output=True).stdout
finally:
    if release:
        release()
h = struct.unpack(">25I", raw[:100])
w, ht, bpp, bpl, order = h[4], h[5], h[11], h[12], h[7]
mode = {32: ("BGRX", "XRGB"), 24: ("BGR", "RGB")}[bpp][0 if order == 0 else 1]
Image.frombuffer("RGB", (w, ht), raw[h[0] + h[19] * 12 :], "raw", mode, bpl, 1).save(sys.argv[1])
