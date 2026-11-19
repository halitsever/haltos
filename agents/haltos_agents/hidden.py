"""Agents the owner archived but Claude Code would not remove, kept out of the list across restarts."""
import json
from pathlib import Path

PATH = Path.home() / ".local" / "state" / "haltos-agents" / "hidden.json"


def load(path: Path = PATH) -> set[str]:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return set()
    return {k for k in data if isinstance(k, str)} if isinstance(data, list) else set()


def add(path: Path, key: str) -> None:
    keys = load(path) | {key}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(sorted(keys)))
    tmp.replace(path)
