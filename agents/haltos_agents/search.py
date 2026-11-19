"""Full-text search over every Claude Code transcript on the machine."""
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Hit:
    session_id: str
    title: str
    cwd: str
    mtime: float
    snippet: str


def fold(s: str) -> str:
    """unicode61 folds I to i, never to ı, so Turkish needs both sides mapped to one letter first."""
    return s.replace("I", "i").replace("İ", "i").replace("ı", "i").lower()


def _summarise(path: Path) -> tuple[str, str, str]:
    title = first_prompt = cwd = ""
    parts = []
    with open(path, encoding="utf8", errors="replace") as f:
        for line in f:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not isinstance(row, dict) or row.get("isMeta") or row.get("isSidechain"):
                continue
            cwd = row.get("cwd") or cwd
            if row.get("type") == "ai-title" and row.get("aiTitle"):
                title = row["aiTitle"]
            if row.get("type") not in ("user", "assistant"):
                continue
            content = (row.get("message") or {}).get("content")
            blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content or []
            for b in blocks:
                if not isinstance(b, dict) or b.get("type") != "text":
                    continue
                text = (b.get("text") or "").strip()
                if not text or text.startswith("<"):
                    continue
                if row["type"] == "user" and not first_prompt:
                    first_prompt = text
                parts.append(text)
    return (title or first_prompt)[:80], cwd, "\n".join(parts)


class Index:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, mtime REAL);
            CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5(
                session_id UNINDEXED, title UNINDEXED, cwd UNINDEXED, mtime UNINDEXED, original UNINDEXED, body,
                tokenize='unicode61 remove_diacritics 0');
            """
        )

    def close(self) -> None:
        self.db.close()

    def update(self, root: Path) -> int:
        known = dict(self.db.execute("SELECT path, mtime FROM files"))
        seen, changed = set(), 0
        for path in root.glob("*/*.jsonl"):
            key = str(path)
            seen.add(key)
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if known.get(key) == mtime:
                continue
            title, cwd, text = _summarise(path)
            with self.db:
                self.db.execute("DELETE FROM docs WHERE session_id = ?", (path.stem,))
                self.db.execute(
                    "INSERT INTO docs VALUES (?, ?, ?, ?, ?, ?)", (path.stem, title, cwd, mtime, text, fold(text))
                )
                self.db.execute("INSERT OR REPLACE INTO files VALUES (?, ?)", (key, mtime))
            changed += 1
        with self.db:
            for key in set(known) - seen:
                self.db.execute("DELETE FROM docs WHERE session_id = ?", (Path(key).stem,))
                self.db.execute("DELETE FROM files WHERE path = ?", (key,))
        return changed

    def search(self, query: str, limit: int = 50) -> list[Hit]:
        terms = fold(query).split()
        if not terms:
            return []
        # Quoting every term turns FTS5 operators and punctuation into plain text.
        match = " ".join('"' + t.replace('"', '""') + '"' for t in terms)
        try:
            rows = self.db.execute(
                "SELECT session_id, title, cwd, mtime, original FROM docs WHERE docs MATCH ? ORDER BY mtime DESC LIMIT ?",
                (match, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        return [Hit(sid, title, cwd, mtime, _snippet(original, terms[0])) for sid, title, cwd, mtime, original in rows]


def _snippet(original: str, term: str) -> str:
    at = fold(original).find(term)
    if at < 0:
        return original[:80].replace("\n", " ")
    start = max(0, at - 30)
    text = original[start : at + 50].replace("\n", " ")
    return ("…" if start else "") + text + ("…" if at + 50 < len(original) else "")
