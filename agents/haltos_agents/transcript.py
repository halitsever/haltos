"""Reads Claude Code session transcripts (JSONL) into a short feed and the open question, if any."""
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

PROJECTS = Path.home() / ".claude" / "projects"
APPROVE = b"1"
CANCEL = b"\x1b"
SUMMARY_ARGS = ("command", "file_path", "pattern", "description", "url", "query")


@dataclass
class FeedItem:
    kind: str
    text: str
    name: str = ""
    added: int = 0
    removed: int = 0
    error: bool = False


@dataclass
class Question:
    text: str
    options: list[tuple[str, bytes]] = field(default_factory=list)


def find_transcript(session_id: str, root: Path = PROJECTS) -> Path | None:
    """The project folder name is a lossy encoding of the cwd, so search by session id instead."""
    return next(iter(sorted(root.glob(f"*/{session_id}.jsonl"))), None)


def _rows(path: Path, tail_bytes: int):
    try:
        with open(path, "rb") as f:
            size = f.seek(0, 2)
            start = max(0, size - tail_bytes)
            f.seek(start)
            data = f.read()
    except OSError:
        return
    lines = data.split(b"\n")
    if start:
        lines = lines[1:]
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and not row.get("isMeta") and not row.get("isSidechain"):
            yield row


def _blocks(row):
    message = row.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def _text(block) -> str:
    return block.get("text") if isinstance(block.get("text"), str) else ""


def _input(block) -> dict:
    return block.get("input") if isinstance(block.get("input"), dict) else {}


def tool_summary(name: str, args: dict) -> str:
    arg = _arg(args)
    line = f"{name}: {arg}" if arg else name
    return _clip(line)


def _arg(args: dict) -> str:
    return next((str(args[k]) for k in SUMMARY_ARGS if args.get(k)), "")


def _clip(line: str, width: int = 80) -> str:
    return line if len(line) <= width else line[: width - 1] + "…"


def _lines(value) -> list[str]:
    return value.splitlines() if isinstance(value, str) else []


def _diff(old, new) -> tuple[int, int]:
    """Counts lines as multisets: linear, and close to a real diff for an Edit's small hunks."""
    a, b = Counter(_lines(old)), Counter(_lines(new))
    return sum((b - a).values()), sum((a - b).values())


def line_counts(name: str, args: dict) -> tuple[int, int]:
    if name == "Edit":
        return _diff(args.get("old_string"), args.get("new_string"))
    if name == "Write":
        return len(_lines(args.get("content"))), 0
    if name == "MultiEdit" and isinstance(args.get("edits"), list):
        pairs = [_diff(e.get("old_string"), e.get("new_string")) for e in args["edits"] if isinstance(e, dict)]
        return sum(a for a, _ in pairs), sum(r for _, r in pairs)
    return 0, 0


def _result_line(block) -> str:
    content = block.get("content")
    if isinstance(content, list):
        content = "\n".join(_text(b) for b in content if isinstance(b, dict))
    if not isinstance(content, str):
        return ""
    return _clip(next((line.strip() for line in content.splitlines() if line.strip()), ""))


def read_feed(path: Path, limit: int = 50, tail_bytes: int = 512_000) -> list[FeedItem]:
    items = []
    for row in _rows(path, tail_bytes):
        kind = row.get("type")
        for b in _blocks(row):
            t = b.get("type")
            if kind == "user" and t == "text":
                text = _text(b).strip()
                # Command echoes and injected context arrive as tagged user text.
                if text and not text.startswith("<"):
                    items.append(FeedItem("prompt", text))
            elif kind == "user" and t == "tool_result":
                line = _result_line(b)
                if line:
                    items.append(FeedItem("result", line, error=b.get("is_error") is True))
            elif kind == "assistant" and t == "text" and _text(b).strip():
                items.append(FeedItem("text", _text(b).strip()))
            elif kind == "assistant" and t == "tool_use":
                name, args = str(b.get("name", "?")), _input(b)
                added, removed = line_counts(name, args)
                # Shown as Name(arg), so the brackets count toward the width.
                arg = _clip(_arg(args), max(1, 78 - len(name)))
                items.append(FeedItem("tool", arg, name, added, removed))
    return items[-limit:]


def last_model(path: Path, tail_bytes: int = 512_000) -> str:
    model = ""
    for row in _rows(path, tail_bytes):
        message = row.get("message")
        value = message.get("model") if isinstance(message, dict) else None
        if isinstance(value, str) and value and not value.startswith("<"):
            model = value
    return model


def short_model(model: str) -> str:
    """claude-opus-5-5 reads as opus-5.5, the way Claude Code names it."""
    m = re.fullmatch(r"(?:claude-)?(.*?)(?:-\d{8})?(\[.*\])?", model)
    base, tag = m.group(1), m.group(2) or ""
    return re.sub(r"-(\d+)-(\d+)$", r"-\1.\2", base) + tag


def pending_question(path: Path, waiting: bool, tail_bytes: int = 512_000) -> Question | None:
    """A tool call without a result is a question only when it is AskUserQuestion or the agent is waiting."""
    open_calls = {}
    for row in _rows(path, tail_bytes):
        for b in _blocks(row):
            if b.get("type") == "tool_use":
                open_calls[b.get("id")] = b
            elif b.get("type") == "tool_result":
                open_calls.pop(b.get("tool_use_id"), None)
    if not open_calls:
        return None
    call = list(open_calls.values())[-1]
    args = _input(call)
    if call.get("name") == "AskUserQuestion":
        questions = [q for q in args.get("questions") or [] if isinstance(q, dict)] or [{}]
        first = questions[0]
        options = []
        if len(questions) == 1:
            labels = [str(o.get("label", "")) for o in first.get("options") or [] if isinstance(o, dict)]
            options = [(label, str(i).encode()) for i, label in enumerate(labels, 1) if i <= 9]
        return Question(str(first.get("question", "")), options)
    if not waiting:
        return None
    return Question(tool_summary(str(call.get("name", "?")), args), [("İzin ver", APPROVE), ("Reddet", CANCEL)])
