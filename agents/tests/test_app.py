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
    from tests.test_attach import wait_until
    from haltos_agents.layout import grouped, neighbour
    from haltos_agents.transcript import Question
except ImportError:  # CI runners have no PySide6; the Qt layer is checked on a desktop.
    A = None


# Settings go to a scratch file, never the user's ~/.config.
os.environ["HALTOS_AGENTS_SETTINGS"] = os.path.join(tempfile.mkdtemp(), "agents.ini")

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


class FakeAttachment:
    def __init__(self):
        self.listener, self.sent, self.sizes = None, [], []

    def key(self, data):
        self.sent.append(data)
        return True

    def type_paste(self, text):
        self.sent.append(("paste", text))
        return True

    def resize(self, cols, rows):
        self.sizes.append((cols, rows))

    def close(self):
        self.closed = True


def fake_attachments(controller):
    """Tabs and actions share one attachment per agent; these record instead of running claude attach."""
    made = {}
    controller._attachment_for = lambda key: made.setdefault(key, FakeAttachment())
    return made


NO_PYTE = "pyte not installed"


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
        os.environ["HALTOS_AGENTS_SETTINGS"] = os.path.join(tempfile.mkdtemp(), "agents.ini")
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

    def spawned(self):
        """Records Konsole launches instead of opening windows."""
        calls = []

        class Proc:
            def __init__(self, argv, **kw):
                calls.append(argv)
                self.done = False

            def poll(self):
                return 0 if self.done else None

        orig = A.subprocess.Popen
        A.subprocess.Popen = Proc
        self.addCleanup(setattr, A.subprocess, "Popen", orig)
        return calls

    def test_notification_click_opens_the_agent_tab(self):
        fake_attachments(self.c)
        shown = []
        self.c.showRequested.connect(lambda: shown.append(1))
        self.c._on_polled([session("a"), session("b")], "")
        self.c.notice_keys[7] = "b"
        self.c._on_action("signal ... org.freedesktop.Notifications.ActionInvoked (uint32 7, 'default')")
        self.assertEqual((self.c.selectedKey, self.c.currentTab, shown), ("b", 1, [1]))

    def test_without_pyte_a_tab_asks_for_it_instead_of_a_popup(self):
        calls = self.spawned()
        orig = A.screen.pyte
        A.screen.pyte = None
        self.addCleanup(setattr, A.screen, "pyte", orig)
        self.c._on_polled([session("a")], "")
        self.assertFalse(self.c.openTab("a"))
        self.assertEqual((calls, self.c.currentTab), ([], 0))
        self.assertIn("sudo apt install python3-pyte", self.c.error)

    def test_launched_agent_is_selected_and_announced(self):
        ready = []
        self.c.launchReady.connect(ready.append)
        self.c._on_polled([session("a")], "")
        self.c._want = "b"
        self.c._on_polled([session("a"), session("b")], "")
        self.assertEqual((self.c.selectedKey, ready), ("b", ["b"]))

    @unittest.skipIf(A is not None and A.screen.pyte is None, "pyte not installed")
    def test_tabs_open_once_switch_and_close(self):
        made = fake_attachments(self.c)
        self.c._on_polled([session("a"), session("b")], "")
        self.assertTrue(self.c.openTab("b"))
        self.assertTrue(self.c.openTab("a"))
        self.assertTrue(self.c.openTab("b"))
        self.assertEqual([r["key"] for r in self.c.tabs.rows], ["b", "a"])
        self.assertEqual((self.c.currentTab, self.c.selectedKey), (1, "b"))
        self.c.showTab(0)
        self.assertEqual(self.c.currentTab, 0)
        self.c.closeTab("b")
        self.assertEqual([r["key"] for r in self.c.tabs.rows], ["a"])
        self.assertIsNone(made["b"].listener)
        self.assertFalse(self.c.openTab("missing"))

    @unittest.skipIf(A is not None and A.screen.pyte is None, "pyte not installed")
    def test_terminal_draws_output_and_sends_keys(self):
        made = fake_attachments(self.c)
        self.c._on_polled([session("a")], "")
        self.c.openTab("a")
        term = self.c.terminal("a")
        made["a"].listener(b"\x1b[32mready")
        term._refresh()
        self.assertIn("ready", term.rows.rows[0]["html"])
        self.assertEqual(term.cursorX, 5)
        term.key(0x01000013, "", 0)
        term.paste("hi")
        self.assertEqual(made["a"].sent, [b"\x1b[A", ("paste", "hi")])
        term.resize(100, 30)
        term._refresh()
        self.assertEqual(made["a"].sizes[-1], (100, 30))
        self.assertEqual(len(term.rows.rows), 30)

    def launches(self):
        seen = []
        self.c._launch = lambda argv, cwd: seen.append((argv, cwd))
        return seen

    def test_quick_agent_starts_in_the_last_folder(self):
        seen = self.launches()
        folder = tempfile.mkdtemp(prefix="shop-")
        self.c.newAgent(folder, "", "", False, "first task")
        base = A.slug(Path(folder).name.replace("-", " ").replace("_", " "), set())
        self.c._on_polled([dataclasses.replace(session("a"), name=base)], "")
        self.c.newAgentQuick()
        argv, cwd = seen[-1]
        self.assertEqual(cwd, folder)
        self.assertEqual(argv[-2:], ["--name", base + "-2"])

    def test_quick_agent_without_history_uses_the_selected_agent_folder(self):
        seen = self.launches()
        folder = tempfile.mkdtemp()
        self.c._on_polled([dataclasses.replace(session("a"), cwd=folder)], "")
        self.c.newAgentQuick()
        self.assertEqual(seen[-1][1], folder)

    def test_grid_layout_is_remembered(self):
        self.assertEqual(self.c.gridLayout, "2x2")
        self.c.setGridLayout("3x2")
        self.c.setGridLayout("9x9")
        self.assertEqual(A.Controller().gridLayout, "3x2")

    @unittest.skipIf(A is not None and A.screen.pyte is None, "pyte not installed")
    def test_fill_grid_opens_waiting_then_working_agents(self):
        fake_attachments(self.c)
        need = dataclasses.replace(session("a"), status="waiting")
        work = dataclasses.replace(session("b"), status="busy", state="")
        tty = dataclasses.replace(session("t", attachable=False), status="waiting")
        self.c._on_polled([session("d"), work, tty, need], "")
        self.c.fillGrid(2)
        self.assertEqual(self.c.tabKeys, ["a", "b"])
        self.assertEqual(self.c.currentTab, 0)
        self.c.fillGrid(4)
        self.assertEqual(self.c.tabKeys, ["a", "b", "d"])

    def deleting(self, removed=True):
        calls, hid = [], []
        patches = {"stop": lambda key: calls.append(("stop", key)),
                   "remove": lambda key: calls.append(("rm", key)) or removed}
        for name, fn in patches.items():
            orig = getattr(A, name)
            setattr(A, name, fn)
            self.addCleanup(setattr, A, name, orig)
        orig_add = A.hidden.add
        A.hidden.add = lambda path, key: hid.append(key)
        self.addCleanup(setattr, A.hidden, "add", orig_add)
        self.c.pool.start = lambda job: job.run()
        # The real refresh would ask claude for its sessions; these tests stay offline.
        self.c.refresh = lambda: None
        return calls, hid

    def test_delete_stops_a_running_agent_then_removes_it(self):
        calls, hid = self.deleting()
        made = fake_attachments(self.c) if A.screen.pyte else None
        work = dataclasses.replace(session("a"), status="busy", state="")
        self.c._on_polled([work, session("b")], "")
        if made is not None:
            self.c.openTab("a")
        self.c.deleteAgent("a")
        self.assertEqual(calls, [("stop", "a"), ("rm", "a")])
        self.assertEqual(hid, [])
        self.assertNotIn("a", self.c.tabKeys)
        self.assertIn("a", self.c.hidden)

    def test_delete_hides_what_claude_will_not_remove(self):
        calls, hid = self.deleting(removed=False)
        self.c._on_polled([session("a"), session("t", attachable=False)], "")
        self.c.deleteAgent("a")
        self.c.deleteAgent("t")
        self.assertEqual(calls, [("rm", "a")])
        self.assertEqual(hid, ["a"])
        self.assertIn("t", self.c.hidden)

    def test_status_line_counts_who_waits(self):
        self.assertEqual(self.c.statusLine, "HaltOS Agents")
        need = dataclasses.replace(session("a"), status="waiting")
        work = dataclasses.replace(session("b"), status="busy", state="")
        self.c._on_polled([need, work], "")
        self.assertEqual(self.c.statusLine, "HaltOS Agents · 1 waiting · 1 working")

    def test_open_folder_and_code(self):
        seen = []
        orig = A.subprocess.Popen
        A.subprocess.Popen = lambda argv, **kw: seen.append(argv)
        self.addCleanup(setattr, A.subprocess, "Popen", orig)
        self.c._on_polled([dataclasses.replace(session("a"), cwd="/srv/shop")], "")
        self.c.openFolder("a")
        self.c.openInCode("a")
        self.assertEqual(seen, [["xdg-open", "/srv/shop"], ["code", "/srv/shop"]])

    def test_clear_done_deletes_every_finished_agent(self):
        calls, hid = self.deleting()
        work = dataclasses.replace(session("w"), status="busy", state="")
        self.c._on_polled([work, session("d1"), session("d2")], "")
        self.c.clearDone()
        self.assertEqual(calls, [("rm", "d1"), ("rm", "d2")])

    def test_delete_many_and_keys_in_a_section(self):
        calls, hid = self.deleting()
        need = [dataclasses.replace(session(k), status="waiting") for k in ("n1", "n2")]
        self.c._on_polled([*need, session("d")], "")
        self.assertEqual(self.c.keysIn("need"), ["n1", "n2"])
        self.c.deleteAgents(["n1", "d"])
        self.assertEqual(calls, [("stop", "n1"), ("rm", "n1"), ("rm", "d")])

    @unittest.skipIf(A is not None and A.screen.pyte is None, "pyte not installed")
    def test_closed_tab_stays_closed_and_frees_its_attachment(self):
        made = fake_attachments(self.c)
        self.c.attachments = made
        self.c._on_polled([session("a"), session("b")], "")
        self.c.fillGrid(2)
        first = made["a"]
        self.c.closeTab("a")
        self.c.fillGrid(2)
        self.assertEqual(self.c.tabKeys, ["b"])
        self.assertNotIn("a", self.c.attachments)
        self.assertTrue(wait_until(lambda: getattr(first, "closed", False)))
        self.c.openTab("a")
        self.assertEqual(self.c.tabKeys, ["b", "a"])

    @unittest.skipIf(A is not None and A.screen.pyte is None, "pyte not installed")
    def test_failing_attach_is_not_retried_in_a_loop(self):
        tries = []

        def broken(key):
            tries.append(key)
            raise A.ClaudeError("no attach")

        self.c._attachment_for = broken
        self.c._on_polled([session("a")], "")
        self.c.changed.connect(lambda: self.c.fillGrid(1))
        self.c.fillGrid(1)
        self.c.fillGrid(1)
        self.assertEqual(tries, ["a"])

    def test_delete_keeps_an_agent_that_would_not_stop(self):
        calls, hid = self.deleting()

        def refuse(key):
            raise A.ClaudeError("still busy")

        A.stop = refuse
        work = dataclasses.replace(session("a"), status="busy", state="")
        self.c._on_polled([work], "")
        self.c.deleteAgent("a")
        self.assertEqual((calls, hid), ([], []))
        self.assertNotIn("a", self.c.hidden)
        self.assertIn("still busy", self.c.error)

    def test_terminal_sessions_are_hidden_for_now_not_for_good(self):
        calls, hid = self.deleting()
        self.c._on_polled([dataclasses.replace(session("pid:42", attachable=False), status="busy")], "")
        self.c.deleteAgent("pid:42")
        self.assertEqual((calls, hid), ([], []))
        self.assertIn("pid:42", self.c.hidden)

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
        # The app opens on the grid, so the key bar starts with the grid's keys.
        self.assertEqual(keys, {
            "key:click": "click type into a pane",
            "key:ctrl+tab": "ctrl+tab next pane",
            "key:⤢": "⤢ own tab",
            "key:tasks": "alt+0 tasks",
        })
        QMetaObject.invokeMethod(root, "trigger", Q_ARG(str, "newDialog"))
        self.assertTrue(root.findChild(QObject, "newAgentDialog").property("visible"))
        self.assertTrue(QFontInfo(root.property("font")).fixedPitch())
        wait(300)
        del root, bar, engine


@unittest.skipIf(A is None, "PySide6 not installed")
class QmlCase(unittest.TestCase):
    # Most tests drive the Tasks overview; the app itself opens on the grid.
    start_in_tasks = True
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
        if self.start_in_tasks:
            self.trigger("tasks")
            self.wait()

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

    def konsoles(self):
        """Records Konsole launches instead of opening windows."""
        calls = []

        orig = A.subprocess.Popen

        class Proc:
            def poll(self):
                return None

        def popen(argv, **kw):
            if argv[0] != "konsole":
                return orig(argv, **kw)
            calls.append(argv[-1])
            return Proc()

        A.subprocess.Popen = popen
        self.addCleanup(setattr, A.subprocess, "Popen", orig)
        return calls

    def tile(self, key):
        items = self.grid.property("contentItem").childItems()
        return next(i for i in items if i.objectName() == "agentTile" and i.property("agentKey") == key)

    def tile_input(self, key):
        # PySide drops a child's wrapper with its parent's, so the tile wrapper has to outlive this call.
        tile = self.tile(key)
        self.keep.append(tile)
        return tile.findChild(QQuickItem, "tileInput")


@unittest.skipIf(A is None, "PySide6 not installed")
class GridDefaultTest(QmlCase):
    start_in_tasks = False

    @unittest.skipIf(A is not None and A.screen.pyte is None, NO_PYTE)
    def test_opens_on_the_grid_filled_with_agents(self):
        fake_attachments(self.c)
        need = dataclasses.replace(session("a"), status="waiting")
        self.poll(need, session("b"), session("c"))
        self.wait(300)
        self.assertTrue(self.item("gridPage").isVisible())
        self.assertEqual(self.c.tabKeys, ["a", "b", "c"])
        self.letter_free()

    def letter_free(self):
        """Letters on the grid never drive the hidden Tasks view."""
        before = self.c.selectedKey
        for kind in (QEvent.KeyPress, QEvent.KeyRelease):
            QGuiApplication.sendEvent(self.root, QKeyEvent(kind, Qt.Key_D, Qt.NoModifier, "d"))
        self.wait()
        self.assertEqual(self.c.selectedKey, before)

    def shortcuts(self):
        return {n: self.root.findChild(QObject, "shortcut:" + n).property("enabled") for n in ("new", "find", "interrupt", "grid")}

    def test_claude_code_keys_are_left_alone_on_the_grid(self):
        self.poll(session("a"))
        self.assertEqual(self.shortcuts(), {"new": False, "find": False, "interrupt": False, "grid": False})
        self.trigger("tasks")
        self.wait()
        self.assertEqual(self.shortcuts(), {"new": True, "find": True, "interrupt": True, "grid": True})

    def test_tasks_chip_switches_to_the_overview(self):
        self.poll(session("a"))
        self.trigger("tasks")
        self.wait()
        self.assertFalse(self.item("gridPage").isVisible())
        self.assertTrue(self.grid.isVisible())


@unittest.skipIf(A is None, "PySide6 not installed")
class ThemeTest(QmlCase):
    def test_window_is_haltmono(self):
        self.assertEqual(self.root.property("color"), QColor("#09090b"))
        if "JetBrains Mono" in QFontDatabase.families():
            self.assertEqual(self.root.property("font").family(), "JetBrains Mono")

    def test_empty_state_and_new_button(self):
        self.poll(session("a"))
        self.assertFalse(self.item("emptyState").property("visible"))
        self.assertEqual(self.item("newButton").property("text"), "+ New agent")
        self.poll()
        self.assertTrue(self.item("emptyState").property("visible"))


@unittest.skipIf(A is None, "PySide6 not installed")
class GridTest(QmlCase):

    def need(self, key, question=None):
        if question:
            self.c._tiles[key] = (None, [], {"text": question, "options": ["Yes", "No"]})
        return dataclasses.replace(session(key), status="waiting")

    def work(self, key):
        return dataclasses.replace(session(key), status="busy", state="")

    def test_grid_shows_every_agent(self):
        self.poll(session("a"), session("b"), session("c"))
        self.assertEqual(self.grid.property("count"), 3)

    def test_poll_does_not_move_focus(self):
        self.poll(session("a"))
        search = self.item("searchField")
        self.trigger("search")
        self.assertTrue(search.hasActiveFocus())
        self.poll(session("b"))
        self.assertTrue(search.hasActiveFocus())
        bar = self.item("keyBar")
        policies = {b.property("focusPolicy") for b in bar.childItems() if b.objectName().startswith("key:")}
        self.assertEqual(policies, {0})

    def test_sections_in_order_and_hidden_when_empty(self):
        self.poll(self.need("a"), session("b"))
        need, work, done = (self.item("section:" + g) for g in ("need", "work", "done"))
        self.assertEqual(need.property("text"), "● Waiting for you  1")
        self.assertEqual(done.property("text"), "✓ Done  1")
        self.assertFalse(work.property("visible"))
        self.assertLess(need.y(), done.y())

    def test_tiles_sit_in_their_sections(self):
        self.poll(self.need("a"), self.work("b"), self.work("c"), session("d"))
        self.wait(600)
        cols = self.grid.property("columns")
        ch, hh = self.grid.property("cellHeight"), self.grid.property("headerHeight")
        order = [g for g, _, _ in self.c.sections(cols)]
        for key, (col, row), group in zip("abcd", self.c.tiles(cols), ["need", "work", "work", "done"]):
            self.assertEqual(self.tile(key).y(), row * ch + (order.index(group) + 1) * hh, key)
            self.assertEqual(self.tile(key).x(), col * self.grid.property("cellWidth"), key)

    def test_tiles_keep_size_on_selection(self):
        self.poll(session("a"), session("b"), session("c"))
        size = (self.grid.property("cellWidth"), self.grid.property("cellHeight"))
        for key in "abc":
            self.c.select(key)
            self.wait(400)
            self.assertEqual({(self.tile(k).width(), self.tile(k).height()) for k in "abc"}, {size})

    @unittest.skipIf(A is not None and A.screen.pyte is None, NO_PYTE)
    def test_click_opens_a_tab(self):
        fake_attachments(self.c)
        self.poll(session("a"), session("b"))
        QMetaObject.invokeMethod(self.tile("b"), "open")
        self.wait()
        self.assertEqual((self.c.selectedKey, self.c.currentTab), ("b", 1))
        self.assertEqual(self.item("tabBar").property("count"), 2)
        self.assertEqual(self.root.property("activeFocusItem").objectName(), "terminalView")

    def test_waiting_tile_shows_buttons(self):
        self.poll(self.need("a", "Commit?"), session("b"))
        tile_a, tile_b = self.tile("a"), self.tile("b")
        self.keep += [tile_a, tile_b]
        self.assertTrue(tile_a.findChild(QQuickItem, "answerButtons").isVisible())
        self.assertFalse(tile_b.findChild(QQuickItem, "answerButtons").isVisible())

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

    def test_selection_scrolled_into_view(self):
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
        self.poll(self.work("a"))
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

    def press(self, key, text="", mods=None):
        for kind in (QEvent.KeyPress, QEvent.KeyRelease):
            QGuiApplication.sendEvent(self.root, QKeyEvent(kind, key, mods or Qt.NoModifier, text))
        self.wait(80)

    def letter(self, ch):
        self.press(getattr(Qt, "Key_" + ch.upper()), ch)

    def navigating(self):
        return self.item("navigator").hasActiveFocus()

    def question(self):
        self.c._question = Question("q", [("Yes", b"y"), ("No", b"n")])
        self.c.changed.emit()

    def test_starts_on_grid(self):
        self.poll(session("a"))
        self.assertTrue(self.navigating())

    def test_arrows_and_wasd_move(self):
        need = dataclasses.replace(session("a"), status="waiting")
        work = dataclasses.replace(session("b"), status="busy", state="")
        self.poll(need, work, session("c"))
        self.letter("s")
        self.assertEqual(self.c.selectedKey, "b")
        self.press(Qt.Key_Down)
        self.assertEqual(self.c.selectedKey, "c")
        self.letter("w")
        self.assertEqual(self.c.selectedKey, "b")
        self.letter("a")
        self.assertEqual(self.c.selectedKey, "a")
        self.press(Qt.Key_Right)
        self.assertEqual(self.c.selectedKey, "b")

    @unittest.skipIf(A is not None and A.screen.pyte is None, NO_PYTE)
    def test_enter_opens_a_tab_that_takes_every_key(self):
        made = fake_attachments(self.c)
        self.poll(dataclasses.replace(session("a"), status="busy", state=""), session("b"))
        self.press(Qt.Key_Return, "\r")
        self.wait()
        self.assertEqual(self.root.property("activeFocusItem").objectName(), "terminalView")
        self.letter("x")
        self.press(Qt.Key_Escape, "\x1b")
        self.assertEqual(made["a"].sent, [b"x", b"\x1b"])
        self.assertEqual(self.sent, [])
        self.c.showTab(0)
        self.wait()
        self.assertTrue(self.navigating())
        self.c.showTab(1)
        self.wait()
        self.c.closeTab("a")
        self.wait()
        self.assertEqual(self.c.currentTab, 0)
        self.assertTrue(self.navigating())

    def test_tty_agent_shows_hint_instead(self):
        calls = self.konsoles()
        self.poll(session("a", attachable=False))
        self.press(Qt.Key_Return, "\r")
        self.assertEqual(calls, [])
        self.assertTrue(self.root.findChild(QObject, "gridHint").property("visible"))

    def test_ctrl_k_and_x_interrupt(self):
        self.poll(dataclasses.replace(session("a"), status="busy", state=""))
        self.letter("x")
        self.trigger("interrupt")
        self.assertEqual(len(self.sent), 2)

    @unittest.skipIf(A is not None and A.screen.pyte is None, NO_PYTE)
    def test_launched_agent_opens_a_tab(self):
        fake_attachments(self.c)
        self.poll(session("a"))
        self.c._want = "b"
        self.poll(session("a"), session("b"))
        self.assertEqual(self.c.currentTab, 1)

    def test_launch_never_steals_focus_from_the_dialog(self):
        calls = self.konsoles()
        fake_attachments(self.c)
        self.poll(session("a"))
        self.trigger("newDialog")
        self.wait()
        self.c._want = "b"
        self.poll(session("a"), session("b"))
        self.assertEqual((calls, self.c.currentTab, self.c.selectedKey), ([], 0, "b"))
        self.trigger("search")
        self.c._want = "c"
        self.poll(session("a"), session("b"), session("c"))
        self.assertEqual((calls, self.c.currentTab), ([], 0))

    @unittest.skipIf(A is not None and A.screen.pyte is None, NO_PYTE)
    def test_grid_mode_shows_open_tabs_side_by_side(self):
        fake_attachments(self.c)
        self.poll(session("a"), session("b"))
        self.c.openTab("a")
        self.c.openTab("b")
        self.trigger("grid")
        self.wait(300)
        page = self.item("gridPage")
        self.assertTrue(page.isVisible())
        self.assertEqual(page.property("keys"), ["a", "b"])
        self.assertEqual((page.property("cols"), page.property("rows")), (2, 2))
        self.assertEqual(self.root.property("activeFocusItem").objectName(), "terminalView")
        self.c.setGridLayout("3x2")
        self.wait()
        self.assertEqual((page.property("cols"), page.property("rows")), (3, 2))
        self.trigger("grid")
        self.wait()
        self.assertFalse(page.isVisible())
        self.assertTrue(self.navigating())

    def test_new_button_starts_an_agent_at_once(self):
        seen = []
        self.c._launch = lambda argv, cwd: seen.append(argv)
        self.poll(session("a"))
        QMetaObject.invokeMethod(self.item("newButton"), "clicked")
        self.wait()
        self.assertEqual(len(seen), 1)
        self.assertFalse(self.root.findChild(QObject, "newAgentDialog").property("visible"))

    def test_delete_key_asks_then_deletes_the_agent_it_asked_about(self):
        removed = []
        orig = A.remove
        A.remove = lambda key: removed.append(key) or True
        self.addCleanup(setattr, A, "remove", orig)
        self.c.pool.start = lambda job: job.run()
        self.c.refresh = lambda: None
        self.poll(session("a"), session("b"))
        self.press(Qt.Key_Delete)
        self.wait()
        dialog = self.root.findChild(QObject, "deleteDialog")
        self.assertTrue(dialog.property("visible"))
        self.assertEqual(dialog.property("target"), "a")
        self.c.select("b")
        QMetaObject.invokeMethod(dialog, "accept")
        self.wait()
        self.assertEqual(removed, ["a"])

    def test_window_title_and_clear_done_dialog(self):
        self.poll(dataclasses.replace(session("a"), status="waiting"), session("d"))
        self.assertEqual(self.root.property("title"), "HaltOS Agents · 1 waiting")
        QMetaObject.invokeMethod(self.item("clearDone"), "clicked")
        self.wait()
        self.assertTrue(self.root.findChild(QObject, "clearDoneDialog").property("visible"))

    def test_ctrl_click_marks_and_delete_removes_them_all(self):
        removed = []
        orig = A.remove
        A.remove = lambda key: removed.append(key) or True
        self.addCleanup(setattr, A, "remove", orig)
        self.c.pool.start = lambda job: job.run()
        self.c.refresh = lambda: None
        self.poll(session("a"), session("b"), session("c"))
        for key in "ab":
            QMetaObject.invokeMethod(self.tile(key), "markToggled")
        self.wait()
        self.assertEqual(self.tile("a").property("marked"), True)
        self.press(Qt.Key_Delete)
        self.wait()
        dialog = self.root.findChild(QObject, "deleteDialog")
        self.assertEqual(dialog.property("targets").toVariant(), ["a", "b"])
        QMetaObject.invokeMethod(dialog, "accept")
        self.wait()
        self.assertEqual(removed, ["a", "b"])
        self.assertFalse(self.tile("c").property("marked"))

    def test_esc_clears_marks_and_right_click_opens_the_menu(self):
        self.poll(session("a"), session("b"))
        QMetaObject.invokeMethod(self.tile("b"), "markToggled")
        self.wait()
        self.press(Qt.Key_Escape)
        self.assertFalse(self.tile("b").property("marked"))
        QMetaObject.invokeMethod(self.tile("b"), "menuRequested")
        self.wait()
        self.assertTrue(self.root.findChild(QObject, "tileMenu").property("visible"))

    def test_grid_digit_answers(self):
        self.poll(dataclasses.replace(session("a"), status="waiting"))
        self.question()
        self.press(Qt.Key_1, "1")
        self.assertEqual(self.sent, [b"y"])

    def test_letters_go_to_search_and_dialog(self):
        self.poll(dataclasses.replace(session("a"), status="busy", state=""))
        self.trigger("search")
        self.letter("x")
        self.assertEqual(self.item("searchField").property("text"), "x")
        self.press(Qt.Key_Escape)
        self.trigger("newDialog")
        self.wait()
        self.letter("x")
        self.assertFalse(self.navigating())
        self.assertEqual(self.sent, [])

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
        calls = self.konsoles()
        self.press(Qt.Key_Return, "\r")
        self.letter("d")
        self.assertEqual(calls, [])
        self.assertEqual(self.c.selectedKey, "a")
        self.press(Qt.Key_Escape)
        self.assertEqual(self.c.query, "")

    def test_help_overlay(self):
        self.poll(session("a"))
        self.press(Qt.Key_Question, "?")
        self.assertTrue(self.item("helpOverlay").property("visible"))
        self.press(Qt.Key_Escape)
        self.assertFalse(self.item("helpOverlay").property("visible"))

if __name__ == "__main__":
    unittest.main()
