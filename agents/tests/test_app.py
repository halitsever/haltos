import dataclasses
import json
import os
import random
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtCore import Q_ARG, QEvent, QEventLoop, QMetaObject, QObject, Qt, QTimer
    from PySide6.QtGui import QColor, QFontDatabase, QFontInfo, QGuiApplication, QKeyEvent
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtWidgets import QApplication

    from haltos_agents import app as A
    from haltos_agents.claude import ClaudeError, Session, UntrustedDir
    from haltos_agents.layout import grouped, neighbour
    from haltos_agents.transcript import Question
except ImportError:  # CI runners have no PySide6; the Qt layer is checked on a desktop.
    A = None


# Controllers live for the whole app, and freeing one between Qt tests crashed the run at random.
KEEP = []


def keep(c):
    KEEP.append(c)
    return c


def wait(ms):
    loop = QEventLoop()
    timer = QTimer(loop, singleShot=True, interval=ms)
    timer.timeout.connect(loop.quit)
    timer.start()
    loop.exec()


def session(key, sid=None, attachable=True):
    return Session(key, sid or f"sid-{key}", key, "/tmp", "background", "done", "idle", 0.0, attachable)


class Stub:
    def __init__(self):
        self.closed = False
        self.alive = True
        self.failed = False

    def close(self):
        self.closed = True


@unittest.skipIf(A is None, "PySide6 not installed")
class ControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.c = keep(A.Controller())
        self.started = []
        self.c.pool.start = lambda job: self.started.append(job)

    def test_poll_does_not_wipe_action_error(self):
        self.c._on_launched(None, "boom")
        self.c._on_polled([], "")
        self.assertEqual(self.c.error, "boom")

    def test_poll_error_shows_and_clears_itself(self):
        self.c._on_polled(None, "claude is not installed")
        self.assertEqual(self.c.error, "claude is not installed")
        self.c._on_polled([], "")
        self.assertEqual(self.c.error, "")

    def test_dismiss_keeps_untrusted_warning(self):
        self.c._on_launched(UntrustedDir("/x"), "")
        self.c._on_launched(None, "boom")
        self.c.dismissError()
        self.assertEqual((self.c.error, self.c.untrustedDir), ("", "/x"))

    def test_job_reports_any_exception(self):
        got = []
        self.c.polled.disconnect()
        self.c.polled.connect(lambda r, e: got.append((r, e)))

        def explode():
            raise TypeError("odd startedAt")

        A.Job(explode, self.c.polled).run()
        self.assertEqual(got, [(None, "odd startedAt")])

    def test_failed_poll_releases_busy_flag(self):
        self.c._busy = True
        self.c._on_polled(None, "x")
        self.c.refresh()
        self.assertEqual(len(self.started), 1)

    def test_send_reports_failure_and_keeps_text(self):
        self.c.sessions = [session("a")]
        self.c._selected = "a"

        class Broken:
            def __init__(self, *a, **k):
                pass

            def start(self):
                raise ClaudeError("claude could not be started")

        orig, A.Attachment = A.Attachment, Broken
        try:
            self.assertIs(self.c.send("merhaba"), False)
        finally:
            A.Attachment = orig
        self.assertIn("could not be started", self.c.error)

    def test_gone_and_failed_attachments_are_closed(self):
        gone, failed, live = Stub(), Stub(), Stub()
        failed.failed = True
        self.c.attachments = {"gone": gone, "a": failed, "b": live}
        self.c._on_polled([session("a"), session("b")], "")
        self.assertEqual((gone.closed, failed.closed, live.closed), (True, True, False))
        self.assertEqual(set(self.c.attachments), {"b"})
        self.assertIn("terminal", self.c.error)

    def test_dead_attachment_is_closed_before_replacing(self):
        dead = Stub()
        dead.alive = False
        self.c.sessions = [session("a")]
        self.c._selected = "a"
        self.c.attachments = {"a": dead}

        class Fresh(Stub):
            def __init__(self, *a, **k):
                super().__init__()

            def start(self):
                pass

            def paste(self, text):
                return True

        orig, A.Attachment = A.Attachment, Fresh
        try:
            self.assertIs(self.c.send("x"), True)
        finally:
            A.Attachment = orig
        self.assertTrue(dead.closed)

    def test_resume_of_live_session_selects_it(self):
        self.c.sessions = [session("a", sid="s-live")]
        self.c.resume("s-live", "/tmp")
        self.assertEqual((self.c.selectedKey, self.started), ("a", []))

    def test_untrusted_launch_can_be_retried(self):
        cwd = tempfile.mkdtemp()
        self.c.newAgent(cwd, "x", "", False, "do it")
        self.c._on_launched(UntrustedDir(cwd), "")
        self.started.clear()
        self.c.retryLaunch()
        self.assertEqual(len(self.started), 1)
        self.assertEqual(self.c.untrustedDir, "")

    def test_step_moves_and_clamps(self):
        self.c._on_polled([session("a"), session("b")], "")
        self.c.select("a")
        self.c.step(1)
        self.assertEqual(self.c.selectedKey, "b")
        self.c.step(1)
        self.assertEqual(self.c.selectedKey, "b")
        self.c.step(-5)
        self.assertEqual(self.c.selectedKey, "a")

    def test_step_without_agents_does_nothing(self):
        self.c.step(1)
        self.assertEqual(self.c.selectedKey, "")

    def test_interrupt_only_while_working(self):
        sent = []
        self.c._act = lambda fn: sent.append(fn) or True
        self.c.sessions = [Session("a", "s", "a", "/tmp", "background", "", "waiting", 0.0, True)]
        self.c._selected = "a"
        self.c.interrupt()
        self.assertEqual(sent, [])
        self.c.sessions = [Session("a", "s", "a", "/tmp", "background", "", "busy", 0.0, True)]
        self.c.interrupt()
        self.assertEqual(len(sent), 1)

    def test_selected_has_project_and_model(self):
        path = os.path.join(tempfile.mkdtemp(), "s.jsonl")
        with open(path, "w") as f:
            f.write('{"type": "assistant", "message": {"model": "claude-opus-5-5", "content": []}}\n')
        orig, A.find_transcript = A.find_transcript, lambda sid: Path(path)
        try:
            s = Session("a", "s", "a", "/tmp/kahvefalin", "background", "", "busy", 0.0, True)
            self.c._on_polled([s], "")
            sel = self.c.selected
        finally:
            A.find_transcript = orig
        self.assertEqual((sel["project"], sel["model"]), ("kahvefalin", "opus-5.5"))

    def test_same_rows_update_in_place(self):
        resets = []
        self.c._agents.modelReset.connect(lambda: resets.append(1))
        self.c._agents.replace([{"key": "a", "age": "1m"}, {"key": "b", "age": "2m"}])
        self.c._agents.replace([{"key": "a", "age": "2m"}, {"key": "b", "age": "3m"}])
        self.assertEqual(len(resets), 1)
        self.assertEqual(self.c._agents.rows[0]["age"], "2m")
        self.c._agents.replace([{"key": "b", "age": "3m"}])
        self.assertEqual(len(resets), 1)
        self.assertEqual(self.c._agents.rows, [{"key": "b", "age": "3m"}])

    def test_reorder_moves_rows_without_reset(self):
        m = self.c._agents
        resets, moves, ins, rem = [], [], [], []
        m.modelReset.connect(lambda: resets.append(1))
        m.rowsMoved.connect(lambda *a: moves.append(1))
        m.rowsInserted.connect(lambda *a: ins.append(1))
        m.rowsRemoved.connect(lambda *a: rem.append(1))

        def rows(ks):
            return [{"key": k, "age": k} for k in ks]

        m.replace(rows("abc"))
        m.replace(rows("cab"))
        m.replace(rows("ac"))
        m.replace(rows("dac"))
        self.assertEqual([r["key"] for r in m.rows], list("dac"))
        self.assertTrue(moves and ins and rem)
        self.assertLessEqual(len(resets), 1)

    def test_keyed_diff_matches_target(self):
        m, rnd = self.c._agents, random.Random(7)
        role = Qt.UserRole + m.keys.index("key")
        for _ in range(200):
            ks = rnd.sample("abcdefgh", rnd.randint(0, 8))
            m.replace([{"key": k, "age": str(rnd.randint(0, 2))} for k in ks])
            self.assertEqual([m.data(m.index(i), role) for i in range(m.rowCount())], ks)

    def _transcript(self, *rows):
        path = os.path.join(tempfile.mkdtemp(), "s.jsonl")
        with open(path, "w") as f:
            f.write("".join(json.dumps(r) + "\n" for r in rows))
        return Path(path)

    def test_tiles_reread_only_on_change(self):
        path = self._transcript({"type": "user", "message": {"content": [{"type": "text", "text": "fix login"}]}})
        calls = []
        orig_find, orig_read = A.find_transcript, A.read_feed
        A.find_transcript = lambda sid: path
        A.read_feed = lambda *a, **k: calls.append(1) or orig_read(*a, **k)
        try:
            busy = Session("a", "s", "a", "/tmp/kahvefalin", "background", "", "busy", 0.0, True)
            self.c._read_tiles([busy])
            self.c._read_tiles([busy])
            self.assertEqual(len(calls), 1)
            self.c._read_tiles([dataclasses.replace(busy, status="waiting")])
            self.assertEqual(len(calls), 2)
            self.c._read_tiles([busy])
            self.c._on_polled([busy], "")
        finally:
            A.find_transcript, A.read_feed = orig_find, orig_read
        row = self.c._agents.rows[0]
        self.assertEqual(row["project"], "kahvefalin")
        self.assertEqual(row["tail"][-1]["kind"], "prompt")
        self.assertEqual(row["tail"][-1]["body"], "fix login")

    def test_tile_remembers_the_window_that_worked(self):
        path = self._transcript(
            {"type": "user", "message": {"content": [{"type": "text", "text": "fix login"}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t", "content": "x" * 300_000}]}},
        )
        calls = []
        orig_find, orig_read = A.find_transcript, A.read_feed
        A.find_transcript = lambda sid: path
        A.read_feed = lambda *a, **k: calls.append(a[2]) or orig_read(*a, **k)
        try:
            self.c._read_tiles([session("a")])
            calls.clear()
            os.utime(path, (1, 1))
            self.c._read_tiles([session("a")])
        finally:
            A.find_transcript, A.read_feed = orig_find, orig_read
        self.assertEqual(calls, [512_000])

    def test_tile_reads_past_a_huge_last_row(self):
        path = self._transcript(
            {"type": "user", "message": {"content": [{"type": "text", "text": "fix login"}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t", "content": "x" * 300_000}]}},
        )
        orig, A.find_transcript = A.find_transcript, lambda sid: path
        try:
            self.c._read_tiles([session("a")])
            self.c._on_polled([session("a")], "")
        finally:
            A.find_transcript = orig
        self.assertEqual(self.c._agents.rows[0]["tail"][0]["body"], "fix login")

    def test_waiting_tile_has_question(self):
        path = self._transcript({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "git push"}}]}})
        orig, A.find_transcript = A.find_transcript, lambda sid: path
        try:
            s = Session("a", "s", "a", "/tmp", "background", "", "waiting", 0.0, True)
            self.c._read_tiles([s])
            self.c._on_polled([s], "")
        finally:
            A.find_transcript = orig
        self.assertEqual(self.c._agents.rows[0]["question"]["options"], ["Allow", "Deny"])

    def test_tile_without_transcript_is_empty(self):
        orig = A.find_transcript
        try:
            for found in (None, Path("/nonexistent/s.jsonl")):
                A.find_transcript = lambda sid, found=found: found
                self.c._read_tiles([session("a")])
                self.c._on_polled([session("a")], "")
                row = self.c._agents.rows[0]
                self.assertEqual((row["tail"], row["question"]), ([], {}))
        finally:
            A.find_transcript = orig

    def test_selected_index(self):
        self.assertEqual(self.c.selectedIndex, -1)
        self.c._on_polled([session("a"), session("b")], "")
        self.c.select("b")
        self.assertEqual(self.c.selectedIndex, 1)

    def test_counts_and_go(self):
        need = dataclasses.replace(session("a"), status="waiting")
        work = dataclasses.replace(session("b"), status="busy", state="")
        self.c._on_polled([need, work, session("c"), session("d")], "")
        self.assertEqual(self.c.counts, {"need": 1, "work": 1, "done": 2})
        self.assertEqual(self.c.sections(3), [["need", 1, 0], ["work", 1, 1], ["done", 2, 2]])
        self.assertEqual(self.c.tiles(3), [[0, 0], [0, 1], [0, 2], [1, 2]])
        self.c.select("a")
        self.c.go("down", 3)
        self.assertEqual(self.c.selectedKey, "b")
        self.c.go("down", 3)
        self.assertEqual(self.c.selectedKey, "c")
        self.c.go("up", 3)
        self.assertEqual(self.c.selectedKey, "b")
        self.c.select("c")
        self.c.go("right", 3)
        self.assertEqual(self.c.selectedKey, "d")
        self.assertFalse(hasattr(self.c, "pack"))

    def test_notification_click_requests_the_agent(self):
        shown, opened = [], []
        self.c.showRequested.connect(lambda: shown.append(1))
        self.c.agentRequested.connect(opened.append)
        self.c._on_polled([session("a"), session("b")], "")
        self.c.notice_keys[7] = "b"
        self.c._on_action("signal ... org.freedesktop.Notifications.ActionInvoked (uint32 7, 'default')")
        self.assertEqual((opened, shown, self.c.selectedKey), (["b"], [], "b"))

    def test_launched_agent_opens_unless_typing(self):
        opened = []
        self.c.agentRequested.connect(opened.append)
        self.c._on_polled([session("a")], "")
        self.c._want = "b"
        self.c._on_polled([session("a"), session("b")], "")
        self.assertEqual((self.c.selectedKey, opened), ("b", ["b"]))
        self.c.setTyping(True)
        self.c._want = "c"
        self.c._on_polled([session("a"), session("b"), session("c")], "")
        self.assertEqual(self.c.selectedKey, "b")
        self.c.setTyping(False)
        self.assertEqual((self.c.selectedKey, opened), ("c", ["b"]))

    def test_released_hold_loads_the_new_agent(self):
        loaded = []
        self.c._load_feed = lambda force=False: loaded.append(self.c._selected)
        self.c._on_polled([session("a")], "")
        self.c.setTyping(True)
        self.c._want = "b"
        self.c._on_polled([session("a"), session("b")], "")
        loaded.clear()
        self.c.setTyping(False)
        self.assertEqual((self.c.selectedKey, loaded), ("b", ["b"]))

    def test_drafts_kept_per_agent(self):
        self.c._on_polled([session("a"), session("b")], "")
        self.c.setDraft("a", "half typed")
        self.assertEqual((self.c.draft("a"), self.c.draft("b")), ("half typed", ""))
        self.c._on_polled([], "")
        self.assertEqual(self.c.draft("a"), "half typed")

    def test_rows_carry_age_and_feed_roles(self):
        for role in ("age", "tail", "question", "project"):
            self.assertIn(role, self.c._agents.keys)
        self.assertEqual(self.c._feed.keys, ["kind", "body", "name", "added", "removed", "error"])
        need = Session("n", "s", "n", "/tmp", "background", "", "waiting", 0.0, True)
        self.assertEqual(self.c._row(need)["age"], "need")
        self.assertEqual(self.c._row(session("d"))["age"], "done")


@unittest.skipIf(A is None, "PySide6 not installed")
class BannerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_error_banner_comes_back_after_dismiss(self):
        c = keep(A.Controller())
        c.pool.start = lambda job: None
        engine = QQmlApplicationEngine()
        engine.rootContext().setContextProperty("agentsController", c)
        engine.setInitialProperties({"hideOnClose": False, "startHidden": True})
        engine.load(A.QML)
        root = engine.rootObjects()[0]
        banner = root.findChild(QObject, "errorMessage")
        self.assertIsNotNone(banner)
        self.assertFalse(banner.property("showCloseButton"))
        c._on_launched(None, "first")
        self.assertTrue(banner.property("visible") or banner.property("text") == "first")
        c.dismissError()
        c._on_launched(None, "second")
        self.assertEqual(banner.property("text"), "second")
        wait(300)
        del root, banner, engine

    def test_terminal_ui(self):
        c = keep(A.Controller())
        c.pool.start = lambda job: None
        engine = QQmlApplicationEngine()
        engine.rootContext().setContextProperty("agentsController", c)
        engine.setInitialProperties({"hideOnClose": False, "startHidden": True})
        engine.load(A.QML)
        root = engine.rootObjects()[0]
        bar = root.findChild(QQuickItem, "keyBar")
        self.assertIsNotNone(bar)
        # Repeater items hang off the item tree, not the QObject tree.
        keys = {b.objectName(): b.property("hint") for b in bar.childItems() if b.objectName().startswith("key:")}
        self.assertEqual(keys, {
            "key:wasd": "wasd move",
            "key:type": "enter type",
            "key:1-9": "1-9 answer",
            "key:zoom": "o zoom",
            "key:interrupt": "x interrupt",
            "key:new": "n new",
            "key:search": "/ search",
            "key:help": "? keys",
        })
        QMetaObject.invokeMethod(root, "trigger", Q_ARG(str, "new"))
        self.assertTrue(root.findChild(QObject, "newAgentDialog").property("visible"))
        self.assertTrue(QFontInfo(root.property("font")).fixedPitch())
        wait(300)
        del root, bar, engine


@unittest.skipIf(A is None, "PySide6 not installed")
class QmlCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.c = keep(A.Controller())
        self.c.pool.start = lambda job: None
        self.engine = QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty("agentsController", self.c)
        self.engine.setInitialProperties({"hideOnClose": False, "startHidden": False})
        self.engine.load(A.QML)
        self.root = self.engine.rootObjects()[0]
        self.root.requestActivate()
        self.grid = self.root.findChild(QQuickItem, "agentGrid")
        self.keep = []

    def tearDown(self):
        self.wait(300)
        del self.keep, self.grid, self.root, self.engine

    def wait(self, ms=200):
        wait(ms)

    def poll(self, *sessions):
        self.c._on_polled(list(sessions), "")
        self.wait()

    def trigger(self, action):
        QMetaObject.invokeMethod(self.root, "trigger", Q_ARG(str, action))

    def item(self, name):
        return self.root.findChild(QQuickItem, name)

    def tile(self, key):
        items = self.grid.property("contentItem").childItems()
        return next(i for i in items if i.objectName() == "agentTile" and i.property("agentKey") == key)

    def tile_input(self, key):
        # PySide drops a child's wrapper with its parent's, so the tile wrapper has to outlive this call.
        tile = self.tile(key)
        self.keep.append(tile)
        return tile.findChild(QQuickItem, "tileInput")


@unittest.skipIf(A is None, "PySide6 not installed")
class ThemeTest(QmlCase):
    def test_window_is_haltmono(self):
        self.assertEqual(self.root.property("color"), QColor("#09090b"))
        if "JetBrains Mono" in QFontDatabase.families():
            self.assertEqual(self.root.property("font").family(), "JetBrains Mono")

    def test_counters(self):
        need = dataclasses.replace(session("a"), status="waiting")
        work = [dataclasses.replace(session(k), status="busy", state="") for k in "bc"]
        self.poll(need, *work)
        self.assertEqual(self.item("counter:need").property("text"), "1 waiting")
        self.assertEqual(self.item("counter:work").property("text"), "2 working")
        self.assertFalse(self.item("counter:done").property("visible"))
        self.assertFalse(self.item("emptyState").property("visible"))
        self.poll()
        self.assertTrue(self.item("emptyState").property("visible"))


@unittest.skipIf(A is None, "PySide6 not installed")
class GridTest(QmlCase):

    def test_grid_shows_every_agent(self):
        self.assertIsNotNone(self.grid)
        self.poll(session("a"), session("b"), session("c"))
        self.assertEqual(self.grid.property("count"), 3)
        self.assertIsNone(self.root.findChild(QQuickItem, "agentList"))

    def test_poll_does_not_move_focus(self):
        self.poll(session("a"))
        search = self.root.findChild(QQuickItem, "searchField")
        self.trigger("search")
        self.assertTrue(search.hasActiveFocus())
        self.poll(session("b"))
        self.assertEqual(self.c.selectedKey, "b")
        self.assertTrue(search.hasActiveFocus())
        bar = self.root.findChild(QQuickItem, "keyBar")
        policies = {b.property("focusPolicy") for b in bar.childItems() if b.objectName().startswith("key:")}
        self.assertEqual(policies, {0})

    def test_focus_and_draft_survive_new_agent(self):
        self.poll(session("a"))
        field = self.tile_input("a")
        field.forceActiveFocus()
        field.setProperty("text", "hello")
        newer = Session("b", "sid-b", "b", "/tmp", "background", "done", "idle", 1.0, True)
        self.poll(newer, session("a"))
        self.assertEqual([r["key"] for r in self.c._agents.rows], ["b", "a"])
        self.assertTrue(field.hasActiveFocus())
        self.assertEqual(field.property("text"), "hello")
        self.assertEqual(self.c.draft("a"), "hello")

    def test_unselected_tile_acts_on_its_agent(self):
        path = os.path.join(tempfile.mkdtemp(), "s.jsonl")
        open(path, "w").close()
        seen = []
        orig = A.find_transcript, A.pending_question
        A.find_transcript = lambda sid: Path(path)
        A.pending_question = lambda *a, **k: Question("q", [("Evet", b"1")])
        self.c._act = lambda fn: seen.append(self.c._selected) or True
        try:
            self.poll(session("a"), session("b"))
            self.c.select("a")
            QMetaObject.invokeMethod(self.tile("b"), "choose", Q_ARG(int, 0))
        finally:
            A.find_transcript, A.pending_question = orig
        self.assertEqual(seen, ["b"])

    def keys(self):
        bar = self.root.findChild(QQuickItem, "keyBar")
        return [b.property("hint") for b in bar.childItems() if b.objectName().startswith("key:")]

    def test_zoom_toggles_view_and_keys(self):
        self.poll(session("a"))
        detail = self.root.findChild(QQuickItem, "agentDetail")
        self.assertEqual(self.keys(), ["wasd move", "enter type", "1-9 answer", "o zoom", "x interrupt", "n new", "/ search", "? keys"])
        self.assertFalse(detail.property("visible"))
        self.trigger("zoom")
        self.wait()
        self.assertTrue(detail.property("visible"))
        self.assertFalse(self.grid.property("visible"))
        self.assertEqual(self.keys(), ["a d prev/next", "enter type", "1-9 answer", "esc grid", "x interrupt", "t terminal"])
        self.assertIsNotNone(self.root.findChild(QQuickItem, "backButton"))
        self.trigger("zoom")
        self.wait()
        self.assertFalse(detail.property("visible"))
        self.assertTrue(self.grid.property("visible"))

    def test_zoom_shares_draft(self):
        self.poll(session("a"))
        field = self.tile_input("a")
        field.setProperty("text", "abc")
        self.trigger("zoom")
        self.wait()
        full = self.root.findChild(QQuickItem, "agentInput")
        self.assertEqual(full.property("text"), "abc")
        full.setProperty("text", "abcd")
        self.trigger("zoom")
        self.wait()
        self.assertEqual(field.property("text"), "abcd")

    def test_zoom_arrows_step_by_one(self):
        self.poll(*(session(k) for k in "abcde"))
        self.c.select("a")
        self.trigger("zoom")
        self.trigger("down")
        self.assertEqual(self.c.selectedIndex, 1)
        self.trigger("up")
        self.assertEqual(self.c.selectedIndex, 0)

    def test_launched_agent_waits_while_typing(self):
        self.poll(session("a"), session("b"))
        self.c.select("a")
        field = self.tile_input("a")
        field.forceActiveFocus()
        field.setProperty("text", "typing")
        self.c._want = "c"
        self.poll(session("a"), session("b"), session("c"))
        self.assertEqual(self.c.selectedKey, "a")
        self.assertTrue(field.hasActiveFocus())
        QMetaObject.invokeMethod(self.root, "navigate")
        self.wait()
        self.assertEqual(self.c.selectedKey, "c")

    def test_zoom_keeps_cursor_at_end(self):
        self.poll(session("a"))
        field = self.tile_input("a")
        field.forceActiveFocus()
        field.setProperty("text", "fix the")
        self.trigger("zoom")
        self.wait()
        full = self.root.findChild(QQuickItem, "agentInput")
        self.assertEqual(full.property("cursorPosition"), 7)
        full.setProperty("text", "fix the tests")
        self.trigger("zoom")
        self.wait()
        self.assertEqual(field.property("cursorPosition"), 13)

    def test_stop_dialog_stops_the_agent_it_asked_about(self):
        stopped = []
        orig = A.stop
        A.stop = lambda key: stopped.append(key)
        self.c.pool.start = lambda job: job.run()
        try:
            self.poll(session("a"), session("b"))
            self.c.select("a")
            QMetaObject.invokeMethod(self.tile("a"), "stopRequested")
            self.wait()
            dialog = self.root.findChild(QObject, "stopDialog")
            self.c.select("b")
            QMetaObject.invokeMethod(dialog, "accept")
            self.wait()
        finally:
            A.stop = orig
        self.assertEqual(stopped, ["a"])

    def big(self, key):
        return self.tile(key).property("big")

    def test_spotlight_follows_selection(self):
        self.poll(session("a"), session("b"), session("c"))
        self.assertEqual([self.big(k) for k in "abc"], [True, False, False])
        self.c.select("c")
        self.wait()
        self.assertEqual([self.big(k) for k in "abc"], [False, False, True])

    def test_only_spotlight_has_input(self):
        self.poll(session("a"), session("b"))
        self.assertTrue(self.tile_input("a").isVisible())
        self.assertFalse(self.tile_input("b").isVisible())

    def test_draft_follows_spotlight(self):
        self.poll(session("a"), session("b"))
        field = self.tile_input("a")
        field.setProperty("text", "half done")
        self.c.select("b")
        self.wait()
        self.c.select("a")
        self.wait()
        self.assertEqual(field.property("text"), "half done")
        self.assertEqual(field.property("cursorPosition"), 9)

    def test_poll_reorder_keeps_spotlight(self):
        self.poll(session("a"), session("b"))
        self.c.select("b")
        self.poll(session("a"), dataclasses.replace(session("b"), status="waiting"))
        self.assertEqual([r["key"] for r in self.c._agents.rows], ["b", "a"])
        self.assertEqual(self.c.selectedKey, "b")
        self.assertTrue(self.big("b"))

    def test_spotlight_scrolled_into_view(self):
        self.root.setProperty("height", 600)
        self.poll(*(session(f"s{i:02}") for i in range(30)))
        self.c.select("s29")
        self.wait(600)
        tile, top = self.tile("s29"), self.grid.property("contentY")
        self.assertGreaterEqual(tile.y(), top)
        self.assertLessEqual(tile.y() + tile.height(), top + self.grid.height())

    def test_spinner_only_while_working(self):
        spinner = self.root.findChild(QObject, "spinner")
        self.poll(session("a"))
        self.assertFalse(spinner.property("running"))
        self.poll(dataclasses.replace(session("a"), status="busy"))
        self.assertTrue(spinner.property("running"))



class Agent:
    def __init__(self, sent):
        self.sent = sent

    def key(self, data):
        self.sent.append(data)


@unittest.skipIf(A is None, "PySide6 not installed")
class KeysTest(QmlCase):
    def setUp(self):
        super().setUp()
        self.sent = []
        self.c._act = lambda fn: fn(Agent(self.sent)) or True
        self.wait()

    def press(self, key, text=""):
        for kind in (QEvent.KeyPress, QEvent.KeyRelease):
            QGuiApplication.sendEvent(self.root, QKeyEvent(kind, key, Qt.NoModifier, text))
        self.wait(80)

    def letter(self, ch):
        self.press(getattr(Qt, "Key_" + ch.upper()), ch)

    def navigating(self):
        return self.item("navigator").hasActiveFocus()

    def test_starts_in_nav(self):
        self.poll(session("a"))
        self.assertTrue(self.navigating())
        self.assertFalse(self.root.property("typing"))
        self.assertEqual(self.item("modeBadge").property("text"), "NAV")

    def test_enter_types_and_esc_returns(self):
        self.poll(session("a"), session("b"))
        self.press(Qt.Key_Return, "\r")
        field = self.tile_input("a")
        self.assertTrue(field.hasActiveFocus())
        self.assertEqual(self.item("modeBadge").property("text"), "TYPE")
        self.letter("w")
        self.assertEqual((field.property("text"), self.c.selectedKey), ("w", "a"))
        self.press(Qt.Key_Escape)
        self.assertTrue(self.navigating())
        self.assertEqual(self.c.draft("a"), "w")

    def test_number_answers(self):
        self.poll(dataclasses.replace(session("a"), status="waiting"))
        self.c._question = Question("q", [("Yes", b"y"), ("No", b"n")])
        self.press(Qt.Key_2, "2")
        self.assertEqual(self.sent, [b"n"])

    def test_x_interrupts_esc_does_not(self):
        self.poll(dataclasses.replace(session("a"), status="busy"))
        self.press(Qt.Key_Return, "\r")
        self.press(Qt.Key_Escape)
        self.assertEqual(self.sent, [])
        self.letter("x")
        self.assertEqual(len(self.sent), 1)

    def test_letters_go_to_search_and_dialog(self):
        self.poll(dataclasses.replace(session("a"), status="busy"))
        self.trigger("search")
        self.letter("x")
        self.assertEqual(self.item("searchField").property("text"), "x")
        self.press(Qt.Key_Escape)
        self.trigger("new")
        self.wait()
        self.letter("x")
        self.assertFalse(self.navigating())
        self.assertEqual(self.sent, [])

    def test_focus_falls_back_when_spotlight_vanishes(self):
        self.poll(session("a"), session("b"))
        self.press(Qt.Key_Return, "\r")
        self.assertTrue(self.tile_input("a").hasActiveFocus())
        self.poll(session("b"))
        self.wait()
        self.assertTrue(self.navigating())
        self.assertEqual(self.c.selectedKey, "b")

    def test_zoom_keys(self):
        self.poll(session("a"), session("b"))
        self.letter("o")
        self.assertTrue(self.root.property("zoomed"))
        self.letter("d")
        self.assertEqual(self.c.selectedKey, "b")
        self.press(Qt.Key_Escape)
        self.assertFalse(self.root.property("zoomed"))
        self.assertTrue(self.navigating())

    def test_help_overlay(self):
        self.poll(session("a"))
        self.press(Qt.Key_Question, "?")
        self.assertTrue(self.item("helpOverlay").property("visible"))
        self.press(Qt.Key_Escape)
        self.assertFalse(self.item("helpOverlay").property("visible"))

    def test_selection_change_while_typing_goes_to_nav(self):
        self.poll(session("a"), session("b"))
        self.press(Qt.Key_Return, "\r")
        self.c.select("b")
        self.wait()
        self.assertTrue(self.navigating())
        self.letter("d")
        self.assertEqual(self.c.draft("a"), "")

    def test_alt_move_while_typing_stays_in_type(self):
        self.poll(session("a"), session("b"))
        self.press(Qt.Key_Return, "\r")
        self.trigger("next")
        self.wait()
        self.assertTrue(self.tile_input("b").hasActiveFocus())

    def test_zoomed_agent_vanishing_goes_to_nav(self):
        self.poll(session("a"), session("b"))
        self.letter("o")
        self.press(Qt.Key_Return, "\r")
        self.assertTrue(self.item("agentInput").hasActiveFocus())
        self.poll(session("b"))
        self.wait()
        self.assertTrue(self.navigating())

    def test_poll_keeps_user_scroll(self):
        self.root.setProperty("height", 600)
        sessions = [session(f"s{i:02}") for i in range(30)]
        self.poll(*sessions)
        self.wait(400)
        grid = self.item("agentGrid")
        grid.setProperty("contentY", 400)
        self.poll(*sessions)
        self.wait(300)
        self.assertEqual(grid.property("contentY"), 400)

    def test_keys_wait_while_results_show(self):
        self.poll(session("a"), session("b"))
        self.c._query = "x"
        self.c.changed.emit()
        self.wait()
        self.press(Qt.Key_Return, "\r")
        self.letter("d")
        self.assertTrue(self.navigating())
        self.assertEqual(self.c.selectedKey, "a")
        self.press(Qt.Key_Escape)
        self.assertEqual(self.c.query, "")

    def test_tty_enter_stays_nav(self):
        self.poll(session("a", attachable=False))
        self.press(Qt.Key_Return, "\r")
        self.assertTrue(self.navigating())


if __name__ == "__main__":
    unittest.main()
