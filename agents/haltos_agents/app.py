"""Qt side of HaltOS Agents: models, the controller QML talks to, tray and single instance."""
import os
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    QRunnable,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import hidden
from .attach import Attachment, attach_argv
from .claude import GROUPS, ClaudeError, Session, clean_env, list_sessions, remove, stop
from .transcript import CANCEL, find_transcript, pending_question, read_feed

QML = Path(__file__).resolve().parent.parent / "qml" / "Main.qml"
LABELS = {"need": "seni bekliyor", "work": "çalışıyor", "done": "bitti"}
POLL_MS = 2000
BRANCH_TTL = 30.0


class ListModel(QAbstractListModel):
    """A list of dicts exposed to QML, one role per key."""

    def __init__(self, roles: list[str], parent=None):
        super().__init__(parent)
        self.keys = roles
        self.rows: list[dict] = []

    def roleNames(self):
        return {Qt.UserRole + i: QByteArray(k.encode()) for i, k in enumerate(self.keys)}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index, role):
        if not index.isValid() or not 0 <= role - Qt.UserRole < len(self.keys):
            return None
        return self.rows[index.row()].get(self.keys[role - Qt.UserRole])

    def replace(self, rows: list[dict]) -> None:
        if rows == self.rows:
            return
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()


class Job(QRunnable):
    def __init__(self, fn, done):
        super().__init__()
        self.fn, self.done = fn, done

    def run(self):
        try:
            self.done.emit(self.fn(), "")
        except ClaudeError as e:
            self.done.emit(None, str(e))


class Controller(QObject):
    changed = Signal()
    polled = Signal(object, str)
    acted = Signal(object, str)
    sessionsChanged = Signal(list)
    showRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._agents = ListModel(["key", "name", "group", "groupLabel", "state", "cwd", "branch", "attachable"], self)
        self._feed = ListModel(["kind", "body"], self)
        self.sessions: list[Session] = []
        self.hidden: set[str] = hidden.load()
        self.attachments: dict[str, Attachment] = {}
        self._error = ""
        self._selected = ""
        self._question = None
        self._feed_stamp = None
        self._branches: dict[str, tuple[float, str]] = {}
        self._busy = False
        self.pool = QThreadPool(self)
        self.polled.connect(self._on_polled)
        self.acted.connect(self._on_acted)
        self.timer = QTimer(self, interval=POLL_MS, timeout=self.refresh)

    @Property(QObject, constant=True)
    def agents(self):
        return self._agents

    @Property(QObject, constant=True)
    def feed(self):
        return self._feed

    @Property(str, notify=changed)
    def error(self):
        return self._error

    @Property(str, notify=changed)
    def selectedKey(self):
        return self._selected

    @Property("QVariantMap", notify=changed)
    def selected(self):
        s = self.session(self._selected)
        if s is None:
            return {}
        return {
            "key": s.key,
            "name": s.name,
            "cwd": s.cwd.replace(str(Path.home()), "~", 1),
            "branch": self._branches.get(s.cwd, (0, ""))[1],
            "group": s.group,
            "attachable": s.attachable,
        }

    @Property("QVariantMap", notify=changed)
    def question(self):
        q = self._question
        return {} if q is None else {"text": q.text, "options": [label for label, _ in q.options]}

    def session(self, key: str) -> Session | None:
        return next((s for s in self.sessions if s.key == key), None)

    def start(self) -> None:
        self.refresh()
        self.timer.start()

    @Slot()
    def refresh(self):
        if self._busy:
            return
        self._busy = True
        self.pool.start(Job(self._poll, self.polled))

    def _poll(self):
        sessions = list_sessions()
        now = time.time()
        for cwd in {s.cwd for s in sessions}:
            if now - self._branches.get(cwd, (0, ""))[0] > BRANCH_TTL:
                self._branches[cwd] = (now, _branch(cwd))
        return sessions

    @Slot(object, str)
    def _on_polled(self, sessions, error):
        self._busy = False
        self._error = error
        if sessions is not None:
            self.sessions = [s for s in sessions if s.key not in self.hidden]
            order = {g: i for i, g in enumerate(GROUPS)}
            ordered = sorted(self.sessions, key=lambda s: (order[s.group], -s.started_at))
            self._agents.replace([self._row(s) for s in ordered])
            if not self.session(self._selected) and ordered:
                self._selected = ordered[0].key
            self.sessionsChanged.emit(self.sessions)
        self._load_feed()
        self.changed.emit()

    def _row(self, s: Session) -> dict:
        return {
            "key": s.key,
            "name": s.name,
            "group": s.group,
            "groupLabel": LABELS[s.group],
            "state": s.state or s.status,
            "cwd": s.cwd.replace(str(Path.home()), "~", 1),
            "branch": self._branches.get(s.cwd, (0, ""))[1],
            "attachable": s.attachable,
        }

    def _load_feed(self, force: bool = False) -> None:
        s = self.session(self._selected)
        path = find_transcript(s.session_id) if s else None
        try:
            stamp = (path, path.stat().st_mtime, s.status) if path else None
        except OSError:
            stamp = None
        if stamp == self._feed_stamp and not force:
            return
        self._feed_stamp = stamp
        if path is None:
            self._feed.replace([])
            self._question = None
            return
        self._feed.replace([{"kind": i.kind, "body": i.text} for i in read_feed(path)])
        self._question = pending_question(path, waiting=s.status == "waiting")

    @Slot(str)
    def select(self, key):
        if key == self._selected:
            return
        self._selected = key
        self._load_feed(force=True)
        self.changed.emit()

    def _attachment(self) -> Attachment | None:
        """One live `claude attach` per agent, opened the first time the owner acts on it."""
        s = self.session(self._selected)
        if s is None or not s.attachable:
            return None
        a = self.attachments.get(s.key)
        if a is None or not a.alive:
            a = self.attachments[s.key] = Attachment(attach_argv(s.key), clean_env(os.environ))
            a.start()
        return a

    @Slot(str)
    def send(self, text):
        a = self._attachment()
        if a and text.strip():
            a.paste(text)

    @Slot(int)
    def answer(self, index):
        a, q = self._attachment(), self._question
        if a and q and 0 <= index < len(q.options):
            a.key(q.options[index][1])

    @Slot()
    def interrupt(self):
        a = self._attachment()
        if a:
            a.key(CANCEL)

    @Slot()
    def kill(self):
        s = self.session(self._selected)
        if s and s.attachable:
            self.pool.start(Job(lambda: stop(s.key), self.acted))

    @Slot()
    def openTerminal(self):
        s = self.session(self._selected)
        if not s or not s.attachable:
            return
        try:
            subprocess.Popen(
                ["konsole", "--profile", "HaltOS", "-e", *attach_argv(s.key)],
                env=clean_env(os.environ),
                cwd=s.cwd or None,
                start_new_session=True,
            )
        except OSError as e:
            self._error = f"Konsole açılamadı: {e}"
            self.changed.emit()

    @Slot()
    def archive(self):
        s = self.session(self._selected)
        if not s or s.group != "done":
            return
        key = s.key

        def work():
            # claude rm refuses sessions it cannot drop safely; those are only hidden here.
            if not (s.attachable and remove(key)):
                hidden.add(hidden.PATH, key)
            return key

        self.pool.start(Job(work, self.acted))

    @Slot(object, str)
    def _on_acted(self, result, error):
        if isinstance(result, str):
            self.hidden.add(result)
            a = self.attachments.pop(result, None)
            if a:
                a.close()
        if error:
            self._error = error
            self.changed.emit()
        self.refresh()

    def shutdown(self) -> None:
        self.timer.stop()
        self.pool.waitForDone(5000)
        for a in self.attachments.values():
            a.close()


def _branch(cwd: str) -> str:
    try:
        p = subprocess.run(["git", "-C", cwd, "branch", "--show-current"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return p.stdout.strip() if p.returncode == 0 else ""


def _single_instance(app: QApplication, controller: Controller) -> QLocalServer | None:
    """A second launch asks the running app to show itself instead of starting another copy."""
    probe = QLocalSocket()
    probe.connectToServer("haltos-agents")
    if probe.waitForConnected(300):
        probe.write(b"show")
        probe.waitForBytesWritten(300)
        return None
    QLocalServer.removeServer("haltos-agents")
    server = QLocalServer(app)
    server.newConnection.connect(lambda: (server.nextPendingConnection(), controller.showRequested.emit()))
    server.listen("haltos-agents")
    return server


def run(args) -> int:
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "org.kde.desktop")
    app = QApplication(sys.argv)
    app.setApplicationName("HaltOS Agents")
    app.setDesktopFileName("haltos-agents")
    app.setWindowIcon(QIcon.fromTheme("haltos-agents", QIcon.fromTheme("utilities-terminal")))
    app.setQuitOnLastWindowClosed(False)

    controller = Controller()
    server = None if args.smoke else _single_instance(app, controller)
    if server is None and not args.smoke:
        return 0

    tray = None
    if not args.smoke and QSystemTrayIcon.isSystemTrayAvailable():
        tray = QSystemTrayIcon(app.windowIcon(), app)
        menu = QMenu()
        menu.addAction("Aç", controller.showRequested.emit)
        menu.addAction("Çık", app.quit)
        tray.setContextMenu(menu)
        tray.setToolTip("HaltOS Agents")
        tray.activated.connect(lambda reason: reason == QSystemTrayIcon.Trigger and controller.showRequested.emit())
        tray.show()

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("agentsController", controller)
    engine.setInitialProperties({"hideOnClose": tray is not None, "startHidden": args.tray})
    engine.load(QML)
    if not engine.rootObjects():
        return 1
    try:
        if args.smoke:
            return 0
        controller.start()
        app.aboutToQuit.connect(controller.shutdown)
        return app.exec()
    finally:
        # QML must go before the controller it binds to, or teardown prints null errors.
        del engine
