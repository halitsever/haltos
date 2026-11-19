"""Decides which agent state changes are worth a desktop notification."""
from dataclasses import dataclass

from .claude import Session


@dataclass
class Notice:
    key: str
    title: str
    body: str


class NotifyPolicy:
    def __init__(self, min_busy: float = 60.0):
        self.min_busy = min_busy
        self.groups: dict[str, str] | None = None
        self.work_since: dict[str, float] = {}

    def observe(self, sessions: list[Session], now: float, focused_key: str | None) -> list[Notice]:
        """The first call only records state, so agents already waiting at startup do not all fire at once."""
        first = self.groups is None
        before = self.groups or {}
        self.groups = {}
        notices = []
        for s in sessions:
            group = self.groups[s.key] = s.group
            old = before.get(s.key)
            if group == "work":
                self.work_since.setdefault(s.key, now)
            started = self.work_since.pop(s.key, None) if group != "work" else None
            if first or group == old or s.key == focused_key:
                continue
            if group == "need":
                notices.append(Notice(s.key, f"{s.name} seni bekliyor", "Cevabını bekliyor."))
            elif group == "done" and old == "work" and started is not None and now - started >= self.min_busy:
                minutes = max(1, int((now - started) // 60))
                notices.append(Notice(s.key, f"{s.name} bitti", f"{minutes} dk çalıştı."))
        for key in set(self.work_since) - set(self.groups):
            del self.work_since[key]
        return notices
