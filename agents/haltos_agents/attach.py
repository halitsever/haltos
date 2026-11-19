"""Keeps `claude attach <id>` running on a pseudo-terminal so the app can type into the session."""
import fcntl
import os
import select
import struct
import subprocess
import termios
import threading

PASTE_START = b"\x1b[200~"
PASTE_END = b"\x1b[201~"
CLEAR_LINE = b"\x15"
# Claude Code turns on bracketed paste once its input box can take text.
READY = b"\x1b[?2004h"


def attach_argv(key: str) -> list[str]:
    return ["claude", "attach", key]


class Attachment:
    def __init__(self, argv: list[str], env: dict[str, str], cols: int = 120, rows: int = 40):
        self.argv, self.env, self.size = argv, env, (rows, cols)
        self.proc: subprocess.Popen | None = None
        self.fd = -1
        self.reader: threading.Thread | None = None
        self.ready = False
        self.pending: list[bytes] = []
        self.lock = threading.Lock()

    def start(self) -> None:
        master, slave = os.openpty()
        fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", *self.size, 0, 0))
        env = dict(self.env, TERM=self.env.get("TERM", "xterm-256color"))
        # Popen instead of pty.fork: forking a threaded Qt process can deadlock in the child.
        self.proc = subprocess.Popen(
            self.argv, stdin=slave, stdout=slave, stderr=slave, env=env, start_new_session=True, close_fds=True
        )
        os.close(slave)
        self.fd = master
        self.reader = threading.Thread(target=self._drain, daemon=True)
        self.reader.start()

    def _drain(self) -> None:
        """Claude Code blocks once the PTY buffer fills, so its screen output is read and dropped."""
        tail = b""
        while self.fd >= 0:
            try:
                readable, _, _ = select.select([self.fd], [], [], 0.2)
                if not readable:
                    continue
                data = os.read(self.fd, 65536)
            except (OSError, ValueError):
                return
            if not data:
                return
            if not self.ready and READY in tail + data:
                self._flush()
            tail = data[-len(READY) :]

    def _flush(self) -> None:
        with self.lock:
            self.ready = True
            pending, self.pending = self.pending, []
        for chunk in pending:
            self._send(chunk)

    @property
    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def _write(self, data: bytes) -> None:
        """Text sent before the session is ready would be dropped by claude attach, so it waits."""
        if not self.alive:
            return
        with self.lock:
            if not self.ready:
                self.pending.append(data)
                return
        self._send(data)

    def _send(self, data: bytes) -> None:
        try:
            os.write(self.fd, data)
        except OSError:
            pass

    def paste(self, text: str) -> None:
        """Ctrl+U first, since an interrupted prompt can come back into Claude Code's input box."""
        self._write(CLEAR_LINE + PASTE_START + text.encode("utf8") + PASTE_END + b"\r")

    def key(self, data: bytes) -> None:
        self._write(data)

    def close(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        fd, self.fd = self.fd, -1
        if fd >= 0:
            os.close(fd)
        if self.reader is not None:
            self.reader.join(1)
