import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtCore import QEventLoop, QObject, QTimer
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtWidgets import QApplication

    from haltos_agents import app as A
    from haltos_agents.claude import ClaudeError, Session, UntrustedDir
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

    def test_rows_carry_age_and_feed_roles(self):
        self.assertIn("age", self.c._agents.keys)
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


if __name__ == "__main__":
    unittest.main()
