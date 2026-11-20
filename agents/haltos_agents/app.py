"""Qt side of HaltOS Agents: models, the controller QML talks to, tray and single instance."""
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    QProcess,
    QRunnable,
    Qt,
    QThreadPool,
    QSettings,
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
from .claude import (
    GROUPS,
    ClaudeError,
    Session,
    UntrustedDir,
    clean_env,
    launch,
    list_sessions,
    remove,
    resume_argv,
    start_argv,
    stop,
)
from . import screen
from .keys import encode
from .layout import grouped, neighbour
from .layout import sections as group_sections
from .names import age, recent_dirs, slug
from .notify import MONITOR_ARGV, Notice, NotifyPolicy, notify_argv, parse_action, parse_notify_id
from .search import Index
from .transcript import CANCEL, PROJECTS, FeedItem, find_transcript, last_model, pending_question, read_feed, short_model

QML = Path(__file__).resolve().parent.parent / "qml" / "Main.qml"
SCHEME = Path(__file__).resolve().parent / "HaltMono.colors"
LABELS = {"need": "waiting", "work": "working", "done": "done"}
POLL_MS = 2000
INDEX_MS = 60_000
BRANCH_TTL = 30.0
TILE_LINES = 16
# Tiles are re-read every poll while agents work, so start small and read further only when a few
# huge rows (tool output, attachments) leave the short tail empty.
TILE_BYTES = (128_000, 512_000, 2_000_000)
SETTINGS = Path.home() / ".config" / "haltos-agents.ini"
GRID_LAYOUTS = ("1x2", "2x2", "3x2", "2x3", "3x3", "4x2")
INDEX_DB = Path.home() / ".cache" / "haltos-agents" / "index.sqlite"


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
        if all("key" in r for r in rows + self.rows) and self.rows:
            self._sync(rows)
            return
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def _sync(self, rows: list[dict]) -> None:
        """Move, insert and remove rows so views keep their delegates, focus and scroll position."""
        want = {r["key"] for r in rows}
        for i in reversed(range(len(self.rows))):
            if self.rows[i]["key"] not in want:
                self.beginRemoveRows(QModelIndex(), i, i)
                del self.rows[i]
                self.endRemoveRows()
        for i, row in enumerate(rows):
            have = [r["key"] for r in self.rows]
            if row["key"] in have[i:]:
                j = have.index(row["key"], i)
                if j != i:
                    self.beginMoveRows(QModelIndex(), j, j, QModelIndex(), i)
                    self.rows.insert(i, self.rows.pop(j))
                    self.endMoveRows()
                if self.rows[i] != row:
                    self.rows[i] = row
                    self.dataChanged.emit(self.index(i), self.index(i))
            else:
                self.beginInsertRows(QModelIndex(), i, i)
                self.rows.insert(i, row)
                self.endInsertRows()


def _item(i: FeedItem) -> dict:
    return {"kind": i.kind, "body": i.text, "name": i.name, "added": i.added, "removed": i.removed, "error": i.error}


class Job(QRunnable):
    def __init__(self, fn, done):
        super().__init__()
        self.fn, self.done = fn, done

    def run(self):
        try:
            self.done.emit(self.fn(), "")
        except Exception as e:  # noqa: BLE001
            # Anything uncaught here would leave the poller marked busy forever.
            self.done.emit(None, str(e) or type(e).__name__)


class Terminal(QObject):
    """One agent's Claude Code, drawn from its attachment's output and fed the keys typed in its tab."""

    changed = Signal()

    def __init__(self, attachment, parent=None, cols: int = 120, rows: int = 40):
        super().__init__(parent)
        self.screen = screen.Screen(cols, rows)
        self._rows = ListModel(["key", "html"], self)
        self._cursor = (0, 0, True)
        self.attachment = None
        self.attach(attachment)
        # Output arrives on the reader thread; the UI picks it up at most every 30 ms.
        self.timer = QTimer(self, interval=30, timeout=self._refresh)
        self.timer.start()

    def attach(self, attachment) -> None:
        if self.attachment is not None:
            self.attachment.listener = None
        self.attachment = attachment
        attachment.listener = self.screen.feed
        # A size change makes Claude Code redraw everything, so a fresh tab never starts blank.
        cols, rows = self.screen.cols, self.screen.screen.lines
        attachment.resize(cols, rows - 1)
        attachment.resize(cols, rows)

    def _refresh(self) -> None:
        if not self.screen.take_changed():
            return
        self._rows.replace([{"key": str(i), "html": row} for i, row in enumerate(self.screen.rows())])
        self._cursor = self.screen.cursor()
        self.changed.emit()

    @Property(QObject, constant=True)
    def rows(self):
        return self._rows

    @Property(int, notify=changed)
    def cursorX(self):
        return self._cursor[0]

    @Property(int, notify=changed)
    def cursorY(self):
        return self._cursor[1]

    @Property(bool, notify=changed)
    def cursorVisible(self):
        return self._cursor[2]

    @Slot(int, str, int)
    def key(self, key, text, mods):
        data = encode(key, text, mods)
        if data:
            self.attachment.key(data)

    @Slot(str)
    def paste(self, text):
        self.attachment.type_paste(text)

    @Slot(int, int)
    def resize(self, cols, rows):
        if cols < 10 or rows < 3 or (cols, rows) == (self.screen.cols, self.screen.screen.lines):
            return
        self.screen.resize(cols, rows)
        self.attachment.resize(cols, rows)

    @Slot(int)
    def scroll(self, pages):
        self.screen.scroll(pages)

    def close(self) -> None:
        self.timer.stop()
        if self.attachment is not None:
            self.attachment.listener = None


class Controller(QObject):
    changed = Signal()
    polled = Signal(object, str)
    acted = Signal(object, str)
    launched = Signal(object, str)
    found = Signal(object, str)
    sessionsChanged = Signal(list)
    showRequested = Signal()
    launchReady = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._agents = ListModel(["key", "name", "group", "groupLabel", "state", "cwd", "branch", "attachable", "age", "project", "tail", "question"], self)
        self._feed = ListModel(["kind", "body", "name", "added", "removed", "error"], self)
        self._results = ListModel(["sessionId", "title", "cwd", "where", "date", "snippet"], self)
        self._tabs = ListModel(["key", "name", "group"], self)
        self.settings = QSettings(os.environ.get("HALTOS_AGENTS_SETTINGS", str(SETTINGS)), QSettings.IniFormat)
        self.terminals: dict[str, Terminal] = {}
        self._current_tab = 0
        self._query = ""
        self._untrusted = ""
        self._want = ""
        self._recent: list[str] = []
        self.window_active = False
        self.policy = NotifyPolicy()
        self.notifiers: set[QProcess] = set()
        self.notice_keys: dict[int, str] = {}
        self.monitor: QProcess | None = None
        self.index: Index | None = None
        self.index_lock = threading.Lock()
        self.sessions: list[Session] = []
        self.hidden: set[str] = hidden.load()
        self.attachments: dict[str, Attachment] = {}
        self._poll_error = ""
        self._action_error = ""
        self._last_launch: tuple[list[str], str] | None = None
        self._selected = ""
        self._question = None
        self._feed_stamp = None
        self._model = ""
        self._tiles: dict[str, tuple] = {}
        self._windows: dict[str, int] = {}
        self._drafts: dict[str, str] = {}
        self.terminals: dict[str, subprocess.Popen] = {}
        self._branches: dict[str, tuple[float, str]] = {}
        self._busy = False
        self.pool = QThreadPool(self)
        self.polled.connect(self._on_polled)
        self.acted.connect(self._on_acted)
        self.launched.connect(self._on_launched)
        self.found.connect(self._on_found)
        self.timer = QTimer(self, interval=POLL_MS, timeout=self.refresh)
        self.index_timer = QTimer(self, interval=INDEX_MS, timeout=self.reindex)

    @Property(QObject, constant=True)
    def agents(self):
        return self._agents

    @Property(QObject, constant=True)
    def feed(self):
        return self._feed

    @Property(QObject, constant=True)
    def results(self):
        return self._results

    @Property(str, notify=changed)
    def error(self):
        """Action errors stay until dismissed; poll errors clear on the next good poll."""
        return self._action_error or self._poll_error

    @Property(str, notify=changed)
    def untrustedDir(self):
        return self._untrusted

    @Property(str, notify=changed)
    def query(self):
        return self._query

    @Property(list, notify=changed)
    def recentDirs(self):
        return self._recent

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
            "project": Path(s.cwd).name,
            "model": self._model,
            "group": s.group,
            "attachable": s.attachable,
        }

    @Property(int, notify=changed)
    def selectedIndex(self):
        keys = [row["key"] for row in self._agents.rows]
        return keys.index(self._selected) if self._selected in keys else -1

    @Property("QVariantMap", notify=changed)
    def counts(self):
        groups = [row["group"] for row in self._agents.rows]
        return {g: groups.count(g) for g in ("need", "work", "done")}

    @Property(QObject, constant=True)
    def tabs(self):
        return self._tabs

    @Property(int, notify=changed)
    def currentTab(self):
        """0 is the grid, n is the n-th agent tab."""
        return self._current_tab

    def _tab_keys(self) -> list[str]:
        return [row["key"] for row in self._tabs.rows]

    def _tab_rows(self, keys: list[str]) -> list[dict]:
        rows = []
        for key in keys:
            s = self.session(key)
            rows.append({"key": key, "name": s.name if s else key, "group": s.group if s else "done"})
        return rows

    @Slot(str, result=bool)
    def openTab(self, key):
        """Opens the agent's Claude Code in a tab, or switches to the tab it already has."""
        if not self._ensure_tab(key):
            return False
        keys = self._tab_keys()
        self._current_tab = keys.index(key) + 1
        self.select(key)
        self.changed.emit()
        return True

    def _ensure_tab(self, key: str) -> bool:
        """Gives the agent a tab without switching to it."""
        keys = self._tab_keys()
        if key in keys:
            return True
        s = self.session(key)
        if s is None or not s.attachable:
            return False
        if screen.pyte is None:
            # Without python3-pyte there is no terminal to draw; a popup window is not a tab.
            self._action_error = "Tabs need python3-pyte. Run: sudo apt install python3-pyte, then restart HaltOS Agents."
            self.changed.emit()
            return False
        try:
            self.terminals[key] = Terminal(self._attachment_for(key), self)
        except ClaudeError as e:
            self._action_error = str(e)
            self.changed.emit()
            return False
        self._tabs.replace(self._tab_rows(keys + [key]))
        return True

    @Slot(int)
    def fillGrid(self, count):
        """Fills empty grid panes with the agents that most need a look: waiting first, then working, then done."""
        if screen.pyte is None:
            return
        opened = False
        for row in self._agents.rows:
            if len(self._tab_keys()) >= count:
                break
            if row["key"] not in self._tab_keys() and row["attachable"]:
                opened = self._ensure_tab(row["key"]) or opened
        if opened:
            self.changed.emit()

    @Slot(int)
    def showTab(self, index):
        keys = self._tab_keys()
        if 0 <= index <= len(keys):
            self._current_tab = index
            if index:
                self.select(keys[index - 1])
            self.changed.emit()

    @Slot(str)
    def closeTab(self, key):
        """Detaches the tab only; the agent keeps running."""
        keys = self._tab_keys()
        if key not in keys:
            return
        at = keys.index(key) + 1
        keys.remove(key)
        terminal = self.terminals.pop(key)
        terminal.close()
        self._tabs.replace(self._tab_rows(keys))
        if self._current_tab == at:
            self._current_tab = min(at, len(keys))
        elif self._current_tab > at:
            self._current_tab -= 1
        if self._current_tab:
            self.select(keys[self._current_tab - 1])
        self.changed.emit()

    @Slot(str, result=QObject)
    def terminal(self, key):
        return self.terminals.get(key)

    @Slot(str, result=str)
    def draft(self, key):
        return self._drafts.get(key, "")

    @Slot(str, str)
    def setDraft(self, key, text):
        if text:
            self._drafts[key] = text
        else:
            self._drafts.pop(key, None)

    @Property("QVariantMap", notify=changed)
    def question(self):
        q = self._question
        return {} if q is None else {"text": q.text, "options": [label for label, _ in q.options]}

    def session(self, key: str) -> Session | None:
        return next((s for s in self.sessions if s.key == key), None)

    def start(self) -> None:
        self.refresh()
        self.timer.start()
        self.reindex()
        self.index_timer.start()
        self._watch_notifications()

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
        self._read_tiles(sessions)
        return sessions

    def _read_tiles(self, sessions: list[Session]) -> None:
        """Runs on the poll worker; a transcript is only parsed again when it or the status changed."""
        tiles = {}
        for s in sessions:
            path = find_transcript(s.session_id)
            try:
                st = path.stat() if path else None
            except OSError:
                st = None
            stamp = (path, st.st_mtime, s.status) if st else None
            cached = self._tiles.get(s.key)
            if cached and cached[0] == stamp:
                tiles[s.key] = cached
            elif stamp is None:
                tiles[s.key] = (None, [], {})
            else:
                # Start from the window that was enough last time, so a busy agent does not climb every poll.
                start = self._windows.get(s.key, TILE_BYTES[0])
                for size in [b for b in TILE_BYTES if b >= start]:
                    items = read_feed(path, TILE_LINES, size)
                    if len(items) >= TILE_LINES or size >= st.st_size:
                        break
                self._windows[s.key] = size
                q = pending_question(path, waiting=s.status == "waiting", tail_bytes=size)
                question = {} if q is None else {"text": q.text, "options": [label for label, _ in q.options]}
                tiles[s.key] = (stamp, [_item(i) for i in items], question)
        self._tiles = tiles

    @Slot(object, str)
    def _on_polled(self, sessions, error):
        launched = ""
        self._busy = False
        self._poll_error = error
        if sessions is not None:
            self.sessions = [s for s in sessions if s.key not in self.hidden]
            self._prune_attachments()
            order = {g: i for i, g in enumerate(GROUPS)}
            ordered = sorted(self.sessions, key=lambda s: (order[s.group], -s.started_at))
            self._agents.replace([self._row(s) for s in ordered])
            # A tab whose agent is gone has nothing to attach to any more.
            for key in [k for k in self._tab_keys() if not self.session(k)]:
                self.closeTab(key)
            self._tabs.replace(self._tab_rows(self._tab_keys()))
            if self._want and self.session(self._want):
                self._selected, self._want = self._want, ""
                launched = self._selected
            elif not self.session(self._selected) and ordered:
                self._selected = ordered[0].key
            self.sessionsChanged.emit(self.sessions)
            focused = self._selected if self.window_active else None
            for notice in self.policy.observe(self.sessions, time.time(), focused):
                self._notify(notice)
        self._load_feed()
        self.changed.emit()
        if launched:
            self.launchReady.emit(launched)

    def _row(self, s: Session) -> dict:
        tile = self._tiles.get(s.key, (None, [], {}))
        return {
            "key": s.key,
            "name": s.name,
            "group": s.group,
            "groupLabel": LABELS[s.group],
            "state": s.state or s.status,
            "cwd": s.cwd.replace(str(Path.home()), "~", 1),
            "branch": self._branches.get(s.cwd, (0, ""))[1],
            "attachable": s.attachable,
            "age": age(time.time() - s.started_at) if s.group == "work" else s.group,
            "project": Path(s.cwd).name,
            "tail": tile[1],
            "question": tile[2],
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
            self._model = ""
            return
        self._feed.replace([_item(i) for i in read_feed(path)])
        self._model = short_model(last_model(path))
        self._question = pending_question(path, waiting=s.status == "waiting")

    @Slot(str)
    def select(self, key):
        if key == self._selected:
            return
        self._selected = key
        self._load_feed(force=True)
        self.changed.emit()

    def _prune_attachments(self) -> None:
        """Each attachment is a node process, so ones for gone or unreachable sessions are closed."""
        live = {s.key: s for s in self.sessions}
        for key, a in list(self.attachments.items()):
            if key in live and not a.failed:
                continue
            a.close()
            del self.attachments[key]
            if a.failed and key in live:
                self._action_error = f"Could not attach to {live[key].name}. Try the terminal."

    def _attachment(self) -> Attachment | None:
        s = self.session(self._selected)
        if s is None or not s.attachable:
            return None
        return self._attachment_for(s.key)

    def _attachment_for(self, key: str) -> Attachment:
        """One live `claude attach` per agent, shared by its tab and the grid's actions."""
        a = self.attachments.get(key)
        if a is None or not a.alive:
            if a is not None:
                a.close()
            a = self.attachments[key] = Attachment(attach_argv(key), clean_env(os.environ))
            try:
                a.start()
            except ClaudeError:
                del self.attachments[key]
                raise
            if key in self.terminals:
                self.terminals[key].attach(a)
        return a

    def _act(self, fn) -> bool:
        try:
            a = self._attachment()
        except ClaudeError as e:
            a, self._action_error = None, str(e)
        ok = bool(a) and fn(a)
        if not ok:
            self._action_error = self._action_error or "Could not write to the agent. Try the terminal."
            self.changed.emit()
        return ok

    @Slot(str, result=bool)
    def send(self, text):
        return bool(text.strip()) and self._act(lambda a: a.paste(text))

    @Slot(int)
    def answer(self, index):
        q = self._question
        if q and 0 <= index < len(q.options):
            self._act(lambda a: a.key(q.options[index][1]))

    @Slot()
    def interrupt(self):
        s = self.session(self._selected)
        # Esc on a permission prompt denies it, so only a working agent gets one.
        if s and s.group == "work":
            self._act(lambda a: a.key(CANCEL))

    @Slot(int)
    def step(self, delta):
        keys = [row["key"] for row in self._agents.rows]
        if not keys:
            return
        here = keys.index(self._selected) if self._selected in keys else 0
        self.select(keys[max(0, min(len(keys) - 1, here + delta))])

    @Slot(str, int)
    def go(self, direction, columns):
        if direction in ("left", "right"):
            self.step(-1 if direction == "left" else 1)
            return
        keys = [row["key"] for row in self._agents.rows]
        if self._selected in keys:
            here = keys.index(self._selected)
            self.select(keys[neighbour(grouped(self._groups(), columns), here, direction)])

    def _groups(self) -> list[str]:
        return [row["group"] for row in self._agents.rows]

    @Slot(int, result=list)
    def tiles(self, columns):
        return [[col, row] for col, row, _, _ in grouped(self._groups(), columns)]

    @Slot(int, result=list)
    def sections(self, columns):
        return [list(s) for s in group_sections(self._groups(), columns)]

    @Slot()
    def kill(self):
        s = self.session(self._selected)
        if s and s.attachable:
            self.pool.start(Job(lambda: stop(s.key), self.acted))

    @Slot()
    def openTerminal(self):
        """Opens the real Claude Code for the agent in a HaltOS themed Konsole, one window per agent."""
        s = self.session(self._selected)
        if not s or not s.attachable:
            return
        running = self.terminals.get(s.key)
        if running is not None and running.poll() is None:
            return
        try:
            self.terminals[s.key] = subprocess.Popen(
                ["konsole", "--profile", "HaltOS", "--separate", "--hide-menubar", "--hide-tabbar",
                 "-p", f"tabtitle={s.name}", "--workdir", s.cwd or str(Path.home()), "-e", *attach_argv(s.key)],
                env=clean_env(os.environ),
                cwd=s.cwd or None,
                start_new_session=True,
            )
        except OSError as e:
            self._action_error = f"Could not open Konsole: {e}"
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

    @Property(str, notify=changed)
    def statusLine(self):
        """Window title and tray tooltip, so who waits shows without opening the app."""
        counts = self.counts
        parts = [f"{counts[g]} {word}" for g, word in (("need", "waiting"), ("work", "working")) if counts[g]]
        return " · ".join(["HaltOS Agents", *parts])

    def _open_with(self, argv_head: list[str], key: str) -> None:
        s = self.session(key)
        if not s or not s.cwd:
            return
        try:
            subprocess.Popen([*argv_head, s.cwd], env=clean_env(os.environ), start_new_session=True)
        except OSError as e:
            self._action_error = f"Could not run {argv_head[0]}: {e}"
            self.changed.emit()

    @Slot(str)
    def openFolder(self, key):
        self._open_with(["xdg-open"], key)

    @Slot(str)
    def openInCode(self, key):
        self._open_with(["code"], key)

    @Slot()
    def clearDone(self):
        for row in list(self._agents.rows):
            if row["group"] == "done":
                self.deleteAgent(row["key"])

    @Slot(str)
    def deleteAgent(self, key):
        """Stops the agent if it runs and removes it; what claude refuses to remove is hidden instead."""
        s = self.session(key)
        if s is None:
            return
        self.closeTab(key)
        a = self.attachments.pop(key, None)
        if a:
            a.close()

        def work():
            if s.attachable:
                if s.group != "done":
                    try:
                        stop(key)
                    except ClaudeError:
                        pass
                if remove(key):
                    return key
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
            self._action_error = error
            self.changed.emit()
        self.refresh()

    def _notify(self, notice: Notice) -> None:
        proc = QProcess(self)
        self.notifiers.add(proc)

        def done(*_):
            nid = parse_notify_id(bytes(proc.readAllStandardOutput()).decode())
            if nid is not None:
                self.notice_keys[nid] = notice.key
            self.notifiers.discard(proc)
            proc.deleteLater()

        proc.finished.connect(done)
        argv = notify_argv(notice)
        proc.start(argv[0], argv[1:])

    def _on_action(self, line: str) -> None:
        hit = parse_action(line)
        key = hit and hit[1] == "open" and self.notice_keys.pop(hit[0], None)
        if key:
            self.openTab(key)
            self.showRequested.emit()

    def _watch_notifications(self) -> None:
        """Clicks on our notifications arrive as ActionInvoked signals on the session bus."""
        self.monitor = QProcess(self)
        buffer = bytearray()

        def read():
            buffer.extend(bytes(self.monitor.readAllStandardOutput()))
            *lines, rest = buffer.split(b"\n")
            buffer[:] = rest
            for line in lines:
                self._on_action(line.decode("utf8", "replace"))

        self.monitor.readyReadStandardOutput.connect(read)
        self.monitor.start(MONITOR_ARGV[0], MONITOR_ARGV[1:])

    @Slot(bool)
    def setWindowActive(self, active):
        self.window_active = active

    @Slot()
    def dismissError(self):
        self._action_error = self._poll_error = ""
        self.changed.emit()

    @Slot()
    def dismissUntrusted(self):
        self._untrusted = ""
        self._last_launch = None
        self.changed.emit()

    @Slot()
    def loadRecentDirs(self):
        self._recent = recent_dirs()
        self.changed.emit()

    @Slot(str, result=bool)
    def isGitRepo(self, path):
        path = os.path.expanduser(path.strip())
        if not path or not os.path.isdir(path):
            return False
        p = subprocess.run(["git", "-C", path, "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True)
        return p.stdout.strip() == "true"

    def _launch(self, argv: list[str], cwd: str):
        self._last_launch = (argv, cwd)

        def work():
            try:
                return launch(argv, cwd)
            except UntrustedDir as e:
                return e

        self.pool.start(Job(work, self.launched))

    @Slot(str, str, str, bool, str)
    def newAgent(self, directory, name, model, worktree, prompt):
        directory = os.path.expanduser(directory.strip())
        if not directory or not prompt.strip():
            return
        self.settings.setValue("lastDir", directory)
        name = name.strip() or slug(prompt, {s.name for s in self.sessions})
        self._launch(start_argv(name, prompt, model or None, worktree), directory)

    @Slot()
    def newAgentQuick(self):
        """One click: an idle agent in the last folder used, whose tab then takes the first message."""
        last = self.settings.value("lastDir", "")
        selected = self.session(self._selected)
        directory = last if last and Path(last).is_dir() else selected.cwd if selected else str(Path.home())
        self.settings.setValue("lastDir", directory)
        # Folder names use dashes and underscores where slug expects spaces, so they keep their word breaks.
        base = Path(directory).name.replace("-", " ").replace("_", " ")
        self._launch(start_argv(slug(base, {s.name for s in self.sessions}), "", None, False), directory)

    @Property(str, notify=changed)
    def gridLayout(self):
        layout = self.settings.value("gridLayout", "2x2")
        return layout if layout in GRID_LAYOUTS else "2x2"

    @Slot(str)
    def setGridLayout(self, layout):
        if layout in GRID_LAYOUTS:
            self.settings.setValue("gridLayout", layout)
            self.changed.emit()

    @Slot(str, result="QVariantMap")
    def agentInfo(self, key):
        s = self.session(key)
        return {"name": s.name, "group": s.group} if s else {"name": key, "group": "done"}

    @Property(list, notify=changed)
    def tabKeys(self):
        return self._tab_keys()

    @Slot(str, str)
    def resume(self, session_id, cwd):
        self._query = ""
        self._results.replace([])
        live = next((s for s in self.sessions if s.session_id == session_id), None)
        if live:
            # Resuming a running session would start a second copy of the same conversation.
            self._selected = ""
            self.select(live.key)
            return
        self._launch(resume_argv(session_id), cwd or str(Path.home()))

    @Slot()
    def retryLaunch(self):
        """Runs the launch the trust prompt blocked, so the owner does not retype the task."""
        last, self._untrusted = self._last_launch, ""
        if last:
            self._launch(*last)
        self.changed.emit()

    @Slot(object, str)
    def _on_launched(self, result, error):
        if error:
            self._action_error = error
        if isinstance(result, UntrustedDir):
            self._untrusted = result.cwd
        elif isinstance(result, str):
            self._want, self._untrusted = result, ""
        self.changed.emit()
        self.refresh()

    @Slot()
    def trustInKonsole(self):
        """Opens claude once in that folder, where its own trust prompt can be answered."""
        cwd = self._untrusted
        if cwd:
            subprocess.Popen(
                ["konsole", "--profile", "HaltOS", "--workdir", cwd, "-e", "claude"],
                env=clean_env(os.environ),
                start_new_session=True,
            )
        self.changed.emit()

    def _with_index(self, fn):
        with self.index_lock:
            if self.index is None:
                self.index = Index(INDEX_DB)
            return fn(self.index)

    @Slot()
    def reindex(self):
        self.pool.start(Job(lambda: self._with_index(lambda i: i.update(PROJECTS)) and None, self.found))

    @Slot(str)
    def search(self, query):
        self._query = query
        self.changed.emit()
        if not query.strip():
            self._results.replace([])
            return
        self.pool.start(Job(lambda: (query, self._with_index(lambda i: i.search(query))), self.found))

    @Slot(object, str)
    def _on_found(self, result, error):
        if not result or result[0] != self._query:
            return
        home = str(Path.home())
        self._results.replace(
            [
                {
                    "sessionId": h.session_id,
                    "title": h.title or h.session_id[:8],
                    "cwd": h.cwd,
                    "where": h.cwd.replace(home, "~", 1),
                    "date": time.strftime("%d.%m.%Y %H:%M", time.localtime(h.mtime)),
                    "snippet": h.snippet,
                }
                for h in result[1]
            ]
        )

    def shutdown(self) -> None:
        self.timer.stop()
        self.index_timer.stop()
        if self.monitor is not None:
            self.monitor.kill()
            self.monitor.waitForFinished(1000)
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
    # The KDE style draws dialogs and menus from this scheme instead of the desktop's.
    app.setProperty("KDE_COLOR_SCHEME_PATH", str(SCHEME))
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
        menu.addAction("Open", controller.showRequested.emit)
        # No Quit: the app is meant to keep running, and its user service would start it again anyway.
        tray.setContextMenu(menu)
        tray.setToolTip(controller.statusLine)
        controller.changed.connect(lambda: tray.setToolTip(controller.statusLine))
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
            # Let async QML items finish so the check also covers them.
            QTimer.singleShot(300, app.quit)
            app.exec()
            return 0
        controller.start()
        app.aboutToQuit.connect(controller.shutdown)
        return app.exec()
    finally:
        # QML must go before the controller it binds to, or teardown prints null errors.
        del engine
