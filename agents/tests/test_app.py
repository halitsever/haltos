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
    from PySide6.QtCore import Q_ARG, QEventLoop, QMetaObject, QObject, Qt, QTimer
    from PySide6.QtGui import QFontInfo
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtWidgets import QApplication

    from haltos_agents import app as A
    from haltos_agents.claude import ClaudeError, Session, UntrustedDir
    from haltos_agents.transcript import Question
except ImportError:  # CI runners have no PySide6; the Qt layer is checked on a desktop.
    A = None


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
        self.c = A.Controller()
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
        self.assertIn("Terminal", self.c.error)

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
        self.assertEqual(self.c._agents.rows[0]["question"]["options"], ["İzin ver", "Reddet"])

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

    def test_drafts_kept_per_agent(self):
        self.c._on_polled([session("a"), session("b")], "")
        self.c.setDraft("a", "half typed")
        self.assertEqual((self.c.draft("a"), self.c.draft("b")), ("half typed", ""))
        self.c._on_polled([session("b")], "")
        self.assertEqual(self.c.draft("a"), "")

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
        c = A.Controller()
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
        loop = QEventLoop()
        QTimer.singleShot(300, loop.quit)
        loop.exec()
        del root, banner, engine

    def test_terminal_ui(self):
        c = A.Controller()
        c.pool.start = lambda job: None
        engine = QQmlApplicationEngine()
        engine.rootContext().setContextProperty("agentsController", c)
        engine.setInitialProperties({"hideOnClose": False, "startHidden": True})
        engine.load(A.QML)
        root = engine.rootObjects()[0]
        bar = root.findChild(QQuickItem, "keyBar")
        self.assertIsNotNone(bar)
        # Repeater items hang off the item tree, not the QObject tree.
        keys = {b.objectName(): b.property("text") for b in bar.childItems() if b.objectName().startswith("key:")}
        self.assertEqual(keys, {
            "key:next": "alt+←↑↓→ geç",
            "key:zoom": "ctrl+o büyüt",
            "key:interrupt": "esc kes",
            "key:new": "ctrl+n yeni",
            "key:search": "ctrl+f ara",
            "key:terminal": "ctrl+t terminal",
        })
        QMetaObject.invokeMethod(root, "trigger", Q_ARG(str, "new"))
        self.assertTrue(root.findChild(QObject, "newAgentDialog").property("visible"))
        self.assertTrue(QFontInfo(root.property("font")).fixedPitch())
        loop = QEventLoop()
        QTimer.singleShot(300, loop.quit)
        loop.exec()
        del root, bar, engine


@unittest.skipIf(A is None, "PySide6 not installed")
class GridTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.c = A.Controller()
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
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    def poll(self, *sessions):
        self.c._on_polled(list(sessions), "")
        self.wait()

    def trigger(self, action):
        QMetaObject.invokeMethod(self.root, "trigger", Q_ARG(str, action))

    def tile(self, key):
        items = self.grid.property("contentItem").childItems()
        return next(i for i in items if i.objectName() == "agentTile" and i.property("agentKey") == key)

    def tile_input(self, key):
        # PySide drops a child's wrapper with its parent's, so the tile wrapper has to outlive this call.
        tile = self.tile(key)
        self.keep.append(tile)
        return tile.findChild(QQuickItem, "tileInput")

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
        self.trigger("next")
        self.assertTrue(self.tile_input("b").hasActiveFocus())
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

    def test_alt_arrows_move_by_rows_and_clamp(self):
        self.poll(*(session(k) for k in "abcde"))
        self.c.select("a")
        cols = self.grid.property("columns")
        self.trigger("down")
        self.assertEqual(self.c.selectedIndex, min(cols, 4))
        for _ in range(3):
            self.trigger("down")
        self.assertEqual(self.c.selectedIndex, 4)
        self.trigger("up")
        self.assertEqual(self.c.selectedIndex, max(0, 4 - cols))

    def keys(self):
        bar = self.root.findChild(QQuickItem, "keyBar")
        return [b.property("text") for b in bar.childItems() if b.objectName().startswith("key:")]

    def test_zoom_toggles_view_and_keys(self):
        self.poll(session("a"))
        detail = self.root.findChild(QQuickItem, "agentDetail")
        self.assertEqual(self.keys(), ["alt+←↑↓→ geç", "ctrl+o büyüt", "esc kes", "ctrl+n yeni", "ctrl+f ara", "ctrl+t terminal"])
        self.assertFalse(detail.property("visible"))
        self.trigger("zoom")
        self.wait()
        self.assertTrue(detail.property("visible"))
        self.assertFalse(self.grid.property("visible"))
        self.assertEqual(self.keys(), ["ctrl+o grid", "alt+←→ önceki/sonraki", "esc kes", "ctrl+n yeni", "ctrl+t terminal"])
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
        self.assertTrue(full.hasActiveFocus())
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

    def test_narrow_window_has_one_column(self):
        self.root.setProperty("width", self.root.property("minimumWidth"))
        self.wait()
        self.assertEqual(self.grid.property("columns"), 1)


if __name__ == "__main__":
    unittest.main()
