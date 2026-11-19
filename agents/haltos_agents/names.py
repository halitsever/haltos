"""Agent names from prompts, and the directories the owner worked in lately."""
import json
import re
from pathlib import Path

from .transcript import PROJECTS

TURKISH = str.maketrans("çğıöşüÇĞIİÖŞÜ", "cgiosucgiiosu")


def slug(prompt: str, taken: set[str]) -> str:
    words = [re.sub(r"[^a-z0-9]", "", w) for w in prompt.translate(TURKISH).lower().split()]
    base = "-".join(w for w in words if w)
    base = "-".join(base.split("-")[:4])[:30].strip("-") or "agent"
    name, n = base, 1
    while name in taken:
        n += 1
        name = f"{base}-{n}"
    return name


def _last_cwd(path: Path) -> str:
    try:
        with open(path, "rb") as f:
            f.seek(max(0, f.seek(0, 2) - 65536))
            lines = f.read().split(b"\n")
    except OSError:
        return ""
    for line in reversed(lines):
        try:
            cwd = json.loads(line).get("cwd")
        except (ValueError, AttributeError):
            continue
        if cwd:
            return cwd
    return ""


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def recent_dirs(root: Path = PROJECTS, limit: int = 10) -> list[str]:
    files = sorted(root.glob("*/*.jsonl"), key=_mtime, reverse=True)
    dirs: list[str] = []
    for path in files:
        cwd = _last_cwd(path)
        if cwd and cwd not in dirs and Path(cwd).is_dir():
            dirs.append(cwd)
            if len(dirs) == limit:
                break
    return dirs


def age(seconds: float) -> str:
    minutes = max(0, int(seconds)) // 60
    return f"{minutes}m" if minutes < 60 else f"{minutes // 60}h{minutes % 60}m"
