import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

from haltos_agents.attach import Attachment, attach_argv
from haltos_agents.claude import ClaudeError

RECORDER = """
import os, sys, termios, time, tty
tty.setraw(0)
out = open(sys.argv[1], "wb")
time.sleep(float(sys.argv[2]) if len(sys.argv) > 2 else 0)
# Like claude attach, input typed before the TUI is up is lost.
termios.tcflush(0, termios.TCIFLUSH)
os.write(1, b"\\x1b[?2004h")
while True:
    data = os.read(0, 1024)
    if not data:
        break
    out.write(data)
    out.flush()
"""


def wait_until(cond, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


class AttachTest(unittest.TestCase):
    def setUp(self):
        self.out = Path(tempfile.mkdtemp()) / "got.bin"

    def recorder(self, delay=0.0):
        a = Attachment([sys.executable, "-c", RECORDER, str(self.out), str(delay)], {})
        a.start()
        self.addCleanup(a.close)
        self.assertTrue(wait_until(self.out.exists))
        return a

    def recorded(self, size):
        wait_until(lambda: self.out.stat().st_size >= size)
        return self.out.read_bytes()

    def test_paste_clears_input_then_writes_bracketed_utf8_and_enter(self):
        a = self.recorder()
        a.paste("çalış\nikinci")
        want = b"\x15\x1b[200~" + "çalış\nikinci".encode() + b"\x1b[201~\r"
        self.assertEqual(self.recorded(len(want)), want)

    def test_paste_before_ready_waits_for_bracketed_paste_mode(self):
        a = self.recorder(delay=0.5)
        a.paste("erken")
        want = b"\x15\x1b[200~erken\x1b[201~\r"
        self.assertEqual(self.recorded(len(want)), want)

    def test_key_writes_raw_bytes(self):
        a = self.recorder()
        a.key(b"\x1b")
        self.assertEqual(self.recorded(1), b"\x1b")

    def test_dead_child_reports_not_alive_and_writes_are_noops(self):
        a = Attachment(["true"], {})
        a.start()
        self.assertTrue(wait_until(lambda: not a.alive))
        a.paste("x")
        a.key(b"1")
        a.close()

    def test_noisy_child_does_not_block(self):
        a = Attachment(["yes"], {})
        a.start()
        time.sleep(1)
        self.assertTrue(a.alive)
        a.close()
        self.assertFalse(a.alive)

    def test_attach_argv(self):
        self.assertEqual(attach_argv("3c4701cd"), ["claude", "attach", "3c4701cd"])


class AttachFailureTest(unittest.TestCase):
    def fds(self):
        return len(os.listdir("/proc/self/fd"))

    def test_missing_binary_raises_and_leaks_no_fds(self):
        before = self.fds()
        a = Attachment(["/nonexistent/claude-binary"], {})
        with self.assertRaises(ClaudeError):
            a.start()
        self.assertEqual(self.fds(), before)

    def test_never_ready_times_out_and_drops_text(self):
        a = Attachment(["sleep", "30"], {}, ready_timeout=0.5)
        a.start()
        self.addCleanup(a.close)
        self.assertTrue(a.paste("kaybolmasın"))
        self.assertTrue(wait_until(lambda: a.failed, 3))
        self.assertEqual(a.pending, [])
        self.assertIs(a.paste("tekrar"), False)

    def test_paste_on_dead_child_returns_false(self):
        a = Attachment(["true"], {})
        a.start()
        wait_until(lambda: not a.alive)
        self.assertIs(a.paste("x"), False)
        a.close()

if __name__ == "__main__":
    unittest.main()
