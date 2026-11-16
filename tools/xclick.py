#!/usr/bin/env python3
"""Clicks at screen coordinates via XTest, for driving UI tests without xdotool. Usage: xclick.py X Y"""
import ctypes
import sys
import time

x11 = ctypes.CDLL("libX11.so.6")
xtst = ctypes.CDLL("libXtst.so.6")
x11.XOpenDisplay.restype = ctypes.c_void_p
dpy = x11.XOpenDisplay(None)
if not dpy:
    sys.exit("cannot open display")
x, y = int(sys.argv[1]), int(sys.argv[2])
xtst.XTestFakeMotionEvent(ctypes.c_void_p(dpy), -1, x, y, 0)
x11.XFlush(ctypes.c_void_p(dpy))
time.sleep(0.1)
for down in (1, 0):
    xtst.XTestFakeButtonEvent(ctypes.c_void_p(dpy), 1, down, 0)
    x11.XFlush(ctypes.c_void_p(dpy))
    time.sleep(0.05)
x11.XCloseDisplay(ctypes.c_void_p(dpy))
