"""Emulates the terminal `claude attach` draws into and renders it as HTML rows, without importing Qt."""
import html
import threading

try:
    import pyte
except ImportError:  # CI runners have no pyte; the screen is checked on a desktop.
    pyte = None

FG = "#fafafa"
BG = "#09090b"
# The HaltMono Konsole scheme, so the tab looks like the HaltOS terminal.
PALETTE = {
    "black": "#18181b", "red": "#ef4444", "green": "#22c55e", "brown": "#eab308",
    "blue": "#3b82f6", "magenta": "#a855f7", "cyan": "#06b6d4", "white": "#d4d4d8",
    "brightblack": "#52525b", "brightred": "#f87171", "brightgreen": "#4ade80", "brightbrown": "#facc15",
    "brightblue": "#60a5fa", "brightmagenta": "#c084fc", "brightcyan": "#22d3ee", "brightwhite": "#fafafa",
}


def colour(name: str, default: str) -> str:
    if name == "default":
        return default
    if name in PALETTE:
        return PALETTE[name]
    return "#" + name if len(name) == 6 else default


def style(char) -> str:
    fg, bg = colour(char.fg, FG), colour(char.bg, "")
    if char.reverse:
        fg, bg = bg or BG, fg
    parts = [] if fg == FG else [f"color:{fg}"]
    if bg:
        parts.append(f"background-color:{bg}")
    if char.bold:
        parts.append("font-weight:bold")
    if char.italics:
        parts.append("font-style:italic")
    if char.underscore:
        parts.append("text-decoration:underline")
    return ";".join(parts)


class Screen:
    """The reader thread feeds it, the UI thread reads rows, so both go through one lock."""

    def __init__(self, cols: int, rows: int, history: int = 5000):
        self.screen = pyte.HistoryScreen(cols, rows, history=history, ratio=0.5)
        self.stream = pyte.ByteStream(self.screen)
        self.lock = threading.Lock()
        self.changed = True

    @property
    def cols(self) -> int:
        return self.screen.columns

    def feed(self, data: bytes) -> None:
        with self.lock:
            self.stream.feed(data)
            self.changed = True

    def take_changed(self) -> bool:
        with self.lock:
            changed, self.changed = self.changed, False
            return changed

    def resize(self, cols: int, rows: int) -> None:
        with self.lock:
            self.screen.resize(rows, cols)
            self.changed = True

    def scroll(self, pages: int) -> None:
        with self.lock:
            for _ in range(abs(pages)):
                (self.screen.prev_page if pages < 0 else self.screen.next_page)()
            self.changed = True

    def cursor(self) -> tuple[int, int, bool]:
        with self.lock:
            c = self.screen.cursor
            return c.x, c.y, not c.hidden

    def rows(self) -> list[str]:
        with self.lock:
            return [self._row(y) for y in range(self.screen.lines)]

    def _row(self, y: int) -> str:
        line = self.screen.buffer[y]
        out, run, current = [], [], None
        for x in range(self.screen.columns):
            char = line[x]
            # A wide character's second cell is empty in pyte and already drawn by the first.
            if char.data == "":
                continue
            st = style(char)
            if st != current and run:
                out.append(self._span(current, run))
                run = []
            current = st
            run.append(char.data)
        if run:
            out.append(self._span(current, run))
        return "".join(out)

    @staticmethod
    def _span(st: str | None, chars: list[str]) -> str:
        text = html.escape("".join(chars), quote=False).replace(" ", "&nbsp;")
        return f'<span style="{st}">{text}</span>' if st else text
