"""HaltOS Agents: a tray icon for claudegrid that keeps its grids under the HaltOS Agents task bar button."""
import ctypes
import os
import subprocess
import sys

APP = "haltos-agents"
# claudegrid names its Konsole windows "▦ <name>", which tells a grid from any other Konsole window.
GRID_MARK = "▦"


def is_grid(wm_class: str, title: str) -> bool:
    return wm_class == "konsole" and title.startswith(GRID_MARK)


class X11:
    """The few Xlib calls needed to find, retag and raise grid windows. HaltOS desktops run on X11 through xrdp."""

    def __init__(self):
        self.x = ctypes.CDLL("libX11.so.6")
        self.x.XOpenDisplay.restype = ctypes.c_void_p
        self.x.XInternAtom.restype = ctypes.c_ulong
        self.x.XDefaultRootWindow.restype = ctypes.c_ulong
        display = self.x.XOpenDisplay(None)
        if not display:
            raise OSError("no X display")
        self.d = ctypes.c_void_p(display)
        self.root = ctypes.c_ulong(self.x.XDefaultRootWindow(self.d))

    def atom(self, name: str) -> ctypes.c_ulong:
        return ctypes.c_ulong(self.x.XInternAtom(self.d, name.encode(), 0))

    def _prop(self, window: int, name: str, kind: int):
        actual, fmt = ctypes.c_ulong(), ctypes.c_int()
        count, after = ctypes.c_ulong(), ctypes.c_ulong()
        data = ctypes.POINTER(ctypes.c_ubyte)()
        ok = self.x.XGetWindowProperty(self.d, ctypes.c_ulong(window), self.atom(name), 0, 65536, 0, ctypes.c_ulong(kind),
                                       ctypes.byref(actual), ctypes.byref(fmt), ctypes.byref(count), ctypes.byref(after),
                                       ctypes.byref(data))
        if ok != 0 or not data:
            return fmt.value, b"", 0
        width = {8: 1, 16: ctypes.sizeof(ctypes.c_short), 32: ctypes.sizeof(ctypes.c_long)}.get(fmt.value, 1)
        raw = ctypes.string_at(data, count.value * width)
        self.x.XFree(data)
        return fmt.value, raw, count.value

    def windows(self) -> list[int]:
        _, raw, count = self._prop(self.root.value, "_NET_CLIENT_LIST", 33)
        return list((ctypes.c_ulong * count).from_buffer_copy(raw)) if count else []

    def text(self, window: int, name: str) -> str:
        return self._prop(window, name, self.atom("UTF8_STRING").value)[1].decode(errors="replace")

    def wm_class(self, window: int) -> str:
        raw = self._prop(window, "WM_CLASS", 31)[1]
        parts = raw.split(b"\0")
        return parts[1].decode(errors="replace") if len(parts) > 1 else ""

    def retag(self, window: int) -> None:
        """Konsole names itself org.kde.konsole, so the task bar would file the grid under Konsole without this."""
        value = APP.encode()
        self.x.XChangeProperty(self.d, ctypes.c_ulong(window), self.atom("_KDE_NET_WM_DESKTOP_FILE"),
                               self.atom("UTF8_STRING"), 8, 0, value, len(value))
        # The task bar only reads that property when a window appears, so the window appears again.
        self.x.XUnmapWindow(self.d, ctypes.c_ulong(window))
        self.x.XFlush(self.d)

    def show(self, window: int) -> None:
        self.x.XMapWindow(self.d, ctypes.c_ulong(window))
        self.x.XFlush(self.d)

    def activate(self, window: int) -> None:
        class Event(ctypes.Structure):
            _fields_ = [("type", ctypes.c_int), ("serial", ctypes.c_ulong), ("send_event", ctypes.c_int),
                        ("display", ctypes.c_void_p), ("window", ctypes.c_ulong), ("message_type", ctypes.c_ulong),
                        ("format", ctypes.c_int), ("data", ctypes.c_long * 5), ("pad", ctypes.c_long * 12)]
        # Source 2 tells the window manager a pager asked, so focus stealing prevention lets it through.
        event = Event(type=33, send_event=1, window=window, message_type=self.atom("_NET_ACTIVE_WINDOW").value, format=32)
        event.data[0] = 2
        mask = (1 << 19) | (1 << 20)
        self.x.XSendEvent(self.d, self.root, 0, mask, ctypes.byref(event))
        self.x.XFlush(self.d)


def launch_grid() -> None:
    # Its own session, so a restart of this service never takes the grid's Konsole down with it.
    subprocess.Popen(["claudegrid"], cwd=os.path.expanduser("~"), start_new_session=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> int:
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

    app = QApplication(sys.argv)
    app.setApplicationName("HaltOS Agents")
    app.setDesktopFileName(APP)
    app.setQuitOnLastWindowClosed(False)
    try:
        x11 = X11()
    except OSError:
        x11 = None
    tagged: set[int] = set()

    def grids() -> list[int]:
        if x11 is None:
            return []
        return [w for w in x11.windows() if is_grid(x11.wm_class(w), x11.text(w, "_NET_WM_NAME"))]

    def watch() -> None:
        if x11 is None:
            return
        found = grids()
        for w in found:
            if w not in tagged and x11.text(w, "_KDE_NET_WM_DESKTOP_FILE") != APP:
                x11.retag(w)
                QTimer.singleShot(250, lambda w=w: x11.show(w))
        tagged.intersection_update(found)
        tagged.update(found)

    def open_grid() -> None:
        found = grids()
        if found:
            x11.activate(found[-1])
        else:
            launch_grid()

    tray = QSystemTrayIcon(QIcon.fromTheme(APP))
    tray.setToolTip("HaltOS Agents: claudegrid")
    menu = QMenu()
    menu.addAction("Open claudegrid").triggered.connect(open_grid)
    menu.addAction("New grid").triggered.connect(launch_grid)
    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: open_grid() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
    tray.show()

    timer = QTimer()
    timer.timeout.connect(watch)
    timer.start(700)
    watch()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
