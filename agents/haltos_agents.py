"""HaltOS Agents: claudegrid as a system app. A tray icon that reopens past grids and keeps grids under its button."""
import ctypes
import glob
import json
import os
import subprocess
import sys
import threading
import time

APP = "haltos-agents"
# claudegrid names its Konsole windows "▦ <name>", which tells a grid from any other Konsole window.
GRID_MARK = "▦"
HOME = os.path.expanduser("~")
STATE = os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.join(HOME, ".local", "state"), APP)
GRIDS = os.path.join(STATE, "grids.json")
CLAUDE = os.path.join(HOME, ".claude")
KEEP = 12


def is_grid(wm_class: str, title: str, cmdline: list[str] | None = None) -> bool:
    """claudegrid starts each Konsole with a profile from its runtime dir, which holds when another tab renames the window."""
    if wm_class != "konsole":
        return False
    started_by_claudegrid = any("/claudegrid" in arg and arg.endswith(".profile") for arg in cmdline or [])
    return started_by_claudegrid or title.startswith(GRID_MARK)


def cmdline(pid: int) -> list[str]:
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            return [a.decode(errors="replace") for a in f.read().split(b"\0") if a]
    except OSError:
        return []


def parents(proc: str = "/proc") -> dict[int, int]:
    out = {}
    for name in os.listdir(proc):
        if not name.isdigit():
            continue
        try:
            with open(os.path.join(proc, name, "stat")) as f:
                stat = f.read()
        except OSError:
            continue
        # The command name may hold spaces and parentheses, so the fields are read after the last ")".
        out[int(name)] = int(stat.rsplit(")", 1)[1].split()[1])
    return out


def descendants(root: int, parent_of: dict[int, int]) -> set[int]:
    children: dict[int, list[int]] = {}
    for pid, ppid in parent_of.items():
        children.setdefault(ppid, []).append(pid)
    seen: set[int] = set()
    todo = [root]
    while todo:
        for child in children.get(todo.pop(), []):
            if child not in seen:
                seen.add(child)
                todo.append(child)
    return seen


def running_sessions(pids, sessions_dir: str) -> list[dict]:
    """Claude Code writes ~/.claude/sessions/<pid>.json for every running session."""
    found = []
    for pid in pids:
        try:
            with open(os.path.join(sessions_dir, f"{pid}.json")) as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        if data.get("sessionId"):
            found.append({"id": data["sessionId"], "cwd": data.get("cwd") or HOME,
                          "name": data.get("name") or "", "started": data.get("startedAt") or 0})
    found.sort(key=lambda s: s["started"])
    return [{k: s[k] for k in ("id", "cwd", "name")} for s in found]


def remember(grids: list[dict], sessions: list[dict], now: float, transcript=None) -> list[dict]:
    """Saves an open grid as it is now, over the saved grid it shares a session with. A grid nobody wrote in is skipped."""
    transcript = transcript or has_transcript
    if not any(transcript(s["id"]) for s in sessions):
        return grids
    ids = {s["id"] for s in sessions}
    match = next((g for g in grids if ids & {s["id"] for s in g["sessions"]}), None)
    return ([{"saved": now, "sessions": sessions}] + [g for g in grids if g is not match])[:KEEP]


def settle(previous: dict[int, list[dict]], current: dict[int, list[dict]]) -> list[list[dict]]:
    """The sessions of each grid window that look the same as one look earlier. A closing window loses its panes
    one by one, and saving it halfway would drop the rest from the saved grid."""
    return [sessions for window, sessions in current.items() if sessions and previous.get(window) == sessions]


def load_grids(path: str = GRIDS) -> list[dict]:
    try:
        with open(path) as f:
            data = json.load(f)
        return [g for g in data if isinstance(g, dict) and g.get("sessions")]
    except (OSError, ValueError, TypeError):
        return []


def save_grids(grids: list[dict], path: str = GRIDS) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(grids, f, indent=1)
    os.replace(tmp, path)


def has_transcript(session_id: str, claude: str = CLAUDE) -> bool:
    return bool(glob.glob(os.path.join(glob.escape(claude), "projects", "*", glob.escape(session_id) + ".jsonl")))


def live_sessions(sessions_dir: str = os.path.join(CLAUDE, "sessions")) -> set[str]:
    """Session ids whose Claude Code process still runs. A file can outlive a process that was killed."""
    live = set()
    for path in glob.glob(os.path.join(glob.escape(sessions_dir), "*.json")):
        try:
            with open(path) as f:
                data = json.load(f)
            if data.get("sessionId") and os.path.exists(f"/proc/{int(data['pid'])}"):
                live.add(data["sessionId"])
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return live


def resume_config(grid: dict, transcript=has_transcript, running: set[str] = frozenset()) -> dict:
    """A claudegrid config with one pane per session. A session that never got a message opens fresh in its folder,
    and one that runs somewhere already stays out, since two processes on one session overwrite each other."""
    panes = []
    for s in grid["sessions"]:
        if s["id"] in running:
            continue
        pane = {"dir": s["cwd"]}
        if s.get("name"):
            pane["name"] = s["name"]
        if transcript(s["id"]):
            pane["args"] = ["--resume", s["id"]]
        panes.append(pane)
    return {"panes": panes}


def ago(seconds: float) -> str:
    if seconds < 60:
        return "just now"
    for size, unit in ((86400, "d"), (3600, "h"), (60, "m")):
        if seconds >= size:
            return f"{int(seconds // size)}{unit} ago"
    return "just now"


def label(grid: dict, now: float) -> str:
    folders = []
    for s in grid["sessions"]:
        name = os.path.basename(s["cwd"].rstrip("/")) or s["cwd"]
        if name not in folders:
            folders.append(name)
    shown = ", ".join(folders[:3]) + (f" +{len(folders) - 3}" if len(folders) > 3 else "")
    count = len(grid["sessions"])
    return f"{count} agent{'s' if count != 1 else ''} · {shown} · {ago(now - grid['saved'])}"


def clean_env(environ) -> dict[str, str]:
    """Inherited session markers make claude think it is a child and stop saving its transcript."""
    return {k: v for k, v in environ.items() if not k.startswith("CLAUDE") or k == "CLAUDE_CONFIG_DIR"}


def launch_grid(grid: dict | None = None) -> bool:
    args = ["claudegrid"]
    if grid:
        config = resume_config(grid, running=live_sessions())
        if not config["panes"]:
            return True
        path = os.path.join(STATE, "resume.json")
        os.makedirs(STATE, exist_ok=True)
        with open(path, "w") as f:
            json.dump(config, f)
        args += ["-c", path, "-l", str(len(config["panes"]))]
    try:
        # Its own session, so a restart of the tray never takes the grid's Konsole down with it.
        child = subprocess.Popen(args, cwd=HOME, start_new_session=True, env=clean_env(os.environ),
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return False
    # claudegrid exits once Konsole is up, and the tray lives for days, so nothing may stay unreaped.
    threading.Thread(target=child.wait, daemon=True).start()
    return True


class X11:
    """The few Xlib calls needed to find, retag and raise grid windows. HaltOS desktops run on X11 through xrdp."""

    def __init__(self):
        self.x = ctypes.CDLL("libX11.so.6")
        self.x.XOpenDisplay.restype = ctypes.c_void_p
        self.x.XInternAtom.restype = ctypes.c_ulong
        self.x.XDefaultRootWindow.restype = ctypes.c_ulong
        # Xlib's default handler exits the process, and a grid can close between listing windows and reading one.
        self._ignore = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)(lambda display, event: 0)
        self.x.XSetErrorHandler(self._ignore)
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
            return b"", 0
        width = {8: 1, 16: ctypes.sizeof(ctypes.c_short), 32: ctypes.sizeof(ctypes.c_long)}.get(fmt.value, 1)
        raw = ctypes.string_at(data, count.value * width)
        self.x.XFree(data)
        return raw, count.value

    def windows(self) -> list[int]:
        raw, count = self._prop(self.root.value, "_NET_CLIENT_LIST", 33)
        return list((ctypes.c_ulong * count).from_buffer_copy(raw)) if count else []

    def text(self, window: int, name: str) -> str:
        return self._prop(window, name, self.atom("UTF8_STRING").value)[0].decode(errors="replace")

    def wm_class(self, window: int) -> str:
        parts = self._prop(window, "WM_CLASS", 31)[0].split(b"\0")
        return parts[1].decode(errors="replace") if len(parts) > 1 else ""

    def pid(self, window: int) -> int:
        raw, count = self._prop(window, "_NET_WM_PID", 6)
        return (ctypes.c_ulong * 1).from_buffer_copy(raw)[0] if count else 0

    def grids(self) -> list[int]:
        return [w for w in self.windows()
                if is_grid(self.wm_class(w), self.text(w, "_NET_WM_NAME"), cmdline(self.pid(w)))]

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
        self.x.XSendEvent(self.d, self.root, 0, (1 << 19) | (1 << 20), ctypes.byref(event))
        self.x.XFlush(self.d)


def open_default(x11: "X11 | None") -> bool:
    """The open grid comes to the front. With none open, the last grid comes back, and a new one starts only without either."""
    found = x11.grids() if x11 else []
    if found:
        x11.activate(found[-1])
        return True
    grids = load_grids()
    return launch_grid(grids[0] if grids else None)


def tray() -> int:
    from PySide6.QtCore import QPoint, QSize, Qt, QTimer
    from PySide6.QtGui import QColor, QCursor, QGuiApplication, QIcon, QPainter, QPen, QPixmap
    from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QSystemTrayIcon,
                                   QToolButton, QVBoxLayout, QWidget)

    app = QApplication(sys.argv)
    app.setApplicationName("HaltOS Agents")
    app.setDesktopFileName(APP)
    app.setQuitOnLastWindowClosed(False)
    try:
        x11 = X11()
    except OSError:
        x11 = None
    tagged: set[int] = set()

    def close_icon() -> QIcon:
        pix = QPixmap(16, 16)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor("#a1a1aa"), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(4, 4, 12, 12)
        p.drawLine(12, 4, 4, 12)
        p.end()
        return QIcon(pix)

    def start(grid: dict | None = None) -> None:
        if grid:
            ids = {x["id"] for x in grid["sessions"]}
            # A grid that is still open comes to the front instead of opening again.
            window = next((w for w, sessions in seen.items() if ids & {x["id"] for x in sessions}), None)
            if window is not None and ids <= live_sessions():
                x11.activate(window)
                return
        if not launch_grid(grid):
            icon.showMessage("HaltOS Agents", "claudegrid could not start. Is it installed?")

    def forget(index: int) -> None:
        grids = load_grids()
        if 0 <= index < len(grids):
            del grids[index]
            save_grids(grids)

    def show_open() -> None:
        found = x11.grids() if x11 else []
        if found:
            x11.activate(found[-1])

    class GridMenu(QFrame):
        """Past grids with a remove button each, which the tray's own menu cannot hold."""

        def __init__(self):
            super().__init__(None, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
            self.setObjectName("gridMenu")
            self.setStyleSheet("#gridMenu { background: #09090b; border: 1px solid #27272a; }")
            self.box = QVBoxLayout(self)
            self.box.setContentsMargins(6, 6, 6, 6)
            self.box.setSpacing(2)

        def rebuild(self) -> None:
            while self.box.count():
                item = self.box.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            actions = [("New grid", start)]
            if x11 and x11.grids():
                actions.insert(0, ("Show open grid", show_open))
            for text, act in actions:
                button = QPushButton(text)
                button.setFlat(True)
                button.setStyleSheet("text-align: left; padding: 6px 10px;")
                button.clicked.connect(lambda _=False, act=act: (self.hide(), act()))
                self.box.addWidget(button)
            grids = load_grids()
            caption = QLabel("Recent grids" if grids else "No saved grids yet")
            caption.setStyleSheet("color: #71717a; padding: 6px 10px 2px 10px;")
            self.box.addWidget(caption)
            now = time.time()
            for i, grid in enumerate(grids):
                row = QWidget()
                line = QHBoxLayout(row)
                line.setContentsMargins(0, 0, 0, 0)
                line.setSpacing(2)
                open_btn = QPushButton(label(grid, now))
                open_btn.setFlat(True)
                open_btn.setStyleSheet("text-align: left; padding: 6px 10px;")
                open_btn.setToolTip("\n".join(f"{s.get('name') or s['id'][:8]}  {s['cwd']}" for s in grid["sessions"]))
                open_btn.clicked.connect(lambda _=False, g=grid: (self.hide(), start(g)))
                remove = QToolButton()
                remove.setIcon(close_icon())
                remove.setIconSize(QSize(16, 16))
                remove.setAutoRaise(True)
                remove.setToolTip("Remove this grid")
                remove.clicked.connect(lambda _=False, i=i: self.remove(i))
                line.addWidget(open_btn, 1)
                line.addWidget(remove)
                self.box.addWidget(row)
            self.adjustSize()

        def remove(self, index: int) -> None:
            forget(index)
            self.rebuild()

        def popup_at(self, pos: QPoint) -> None:
            self.rebuild()
            screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
            area = screen.availableGeometry()
            x = min(max(pos.x() - self.width() // 2, area.left()), area.right() - self.width())
            y = pos.y() + 12 if pos.y() < area.center().y() else pos.y() - self.height() - 12
            self.move(x, max(area.top(), min(y, area.bottom() - self.height())))
            self.show()
            self.activateWindow()

    menu = GridMenu()

    def watch() -> None:
        if x11 is None:
            return
        found = x11.grids()
        for w in found:
            if w not in tagged and x11.text(w, "_KDE_NET_WM_DESKTOP_FILE") != APP:
                x11.retag(w)
                QTimer.singleShot(250, lambda w=w: x11.show(w))
        tagged.intersection_update(found)
        tagged.update(found)

    seen: dict[int, list[dict]] = {}

    def record() -> None:
        nonlocal seen
        if x11 is None:
            return
        found = x11.grids()
        current: dict[int, list[dict]] = {}
        if found:
            parent_of = parents()
            for w in found:
                pid = x11.pid(w)
                if pid:
                    current[w] = running_sessions(descendants(pid, parent_of), os.path.join(CLAUDE, "sessions"))
        steady, seen = settle(seen, current), current
        if not steady:
            return
        grids = load_grids()
        before = json.dumps(grids)
        for sessions in steady:
            grids = remember(grids, sessions, time.time())
        # Only a change in sessions is written, so an idle grid does not rewrite the file every few seconds.
        if json.dumps([g["sessions"] for g in grids]) != json.dumps([g["sessions"] for g in json.loads(before)]):
            save_grids(grids)

    # Plasma draws the right click menu itself, so it holds plain entries: a submenu per grid stands in for the X.
    context = QMenu()

    def fill_context() -> None:
        context.clear()
        if x11 and x11.grids():
            context.addAction("Show open grid").triggered.connect(show_open)
        context.addAction("New grid").triggered.connect(lambda: start())
        grids = load_grids()
        if grids:
            context.addSection("Recent grids")
        now = time.time()
        for i, grid in enumerate(grids):
            sub_menu = context.addMenu(label(grid, now))
            sub_menu.addAction("Open").triggered.connect(lambda _=False, g=grid: start(g))
            sub_menu.addAction("Remove").triggered.connect(lambda _=False, i=i: forget(i))

    context.aboutToShow.connect(fill_context)
    fill_context()

    icon = QSystemTrayIcon(QIcon.fromTheme(APP))
    icon.setToolTip("HaltOS Agents: claudegrid")
    icon.setContextMenu(context)
    # A left click opens the list with an X beside each grid. Qt does not pass Plasma's right click on without a menu.
    icon.activated.connect(lambda reason: menu.popup_at(QCursor.pos())
                           if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
    icon.show()

    watcher = QTimer()
    watcher.timeout.connect(watch)
    watcher.start(700)
    recorder = QTimer()
    recorder.timeout.connect(record)
    recorder.start(5000)
    watch()
    return app.exec()


def main(argv: list[str]) -> int:
    if "--open" in argv:
        try:
            x11 = X11()
        except OSError:
            x11 = None
        started = open_default(x11)
    elif "--new" in argv:
        started = launch_grid()
    else:
        return tray()
    if not started:
        print("haltos-agents: claudegrid could not start, is it installed?", file=sys.stderr)
    return 0 if started else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
