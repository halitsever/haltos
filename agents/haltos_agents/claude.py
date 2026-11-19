"""Thin wrapper around the `claude` CLI's background session commands."""
import json
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Mapping

GROUPS = ("need", "work", "done")


class ClaudeError(Exception):
    pass


class UntrustedDir(ClaudeError):
    """`claude --bg` cannot show the trust prompt, so the owner has to accept it once in a terminal."""

    def __init__(self, cwd: str):
        super().__init__(f"{cwd} is not trusted yet.")
        self.cwd = cwd


@dataclass(frozen=True)
class Session:
    key: str
    session_id: str
    name: str
    cwd: str
    kind: str
    state: str
    status: str
    started_at: float
    attachable: bool

    @property
    def group(self) -> str:
        return group_for(self.state, self.status)


def group_for(state: str, status: str = "") -> str:
    """`status` is live process activity and wins over `state`, which lags a turn behind."""
    if status == "waiting":
        return "need"
    if status == "busy":
        return "work"
    if state == "blocked":
        return "need"
    if state == "done" or (not state and status == "idle"):
        return "done"
    return "work"


def parse_agents(text: str) -> list[Session]:
    try:
        rows = json.loads(text)
    except json.JSONDecodeError as e:
        raise ClaudeError(f"claude agents printed something that is not JSON: {e}") from e
    if not isinstance(rows, list):
        raise ClaudeError("claude agents did not return a list")
    sessions = []
    for r in rows:
        try:
            sessions.append(_session(r))
        except (TypeError, ValueError, KeyError):
            # One odd row from a newer CLI must not hide every other agent.
            continue
    return sessions


def _session(r: dict) -> Session:
    sid = r.get("sessionId")
    if not isinstance(sid, str) or not sid:
        raise ValueError("no session id")
    background = r.get("kind") == "background" and bool(r.get("id"))
    return Session(
        key=str(r["id"]) if background else f"pid:{r.get('pid')}",
        session_id=sid,
        name=str(r.get("name") or sid[:8]),
        cwd=str(r.get("cwd") or ""),
        kind=str(r.get("kind") or ""),
        state=str(r.get("state") or ""),
        status=str(r.get("status") or ""),
        started_at=float(r.get("startedAt") or 0) / 1000,
        attachable=background,
    )


def clean_env(environ: Mapping[str, str]) -> dict[str, str]:
    """Inherited session markers make a new claude think it is a child and stop saving its transcript."""
    return {k: v for k, v in environ.items() if not k.startswith("CLAUDE") or k == "CLAUDE_CONFIG_DIR"}


def start_argv(name: str, prompt: str, model: str | None, worktree: bool) -> list[str]:
    argv = ["claude", "--bg", "--permission-mode", "auto", "--name", name]
    if model:
        argv += ["--model", model]
    if worktree:
        argv += ["-w", name]
    return argv + [prompt]


def resume_argv(session_id: str) -> list[str]:
    return ["claude", "--bg", "--resume", session_id]


def _call(argv: list[str], run, cwd: str | None = None) -> subprocess.CompletedProcess:
    try:
        return run(argv, capture_output=True, text=True, env=clean_env(os.environ), timeout=30, cwd=cwd)
    except FileNotFoundError as e:
        raise ClaudeError("claude is not installed or not on PATH") from e
    except OSError as e:
        raise ClaudeError(f"claude could not be started: {e}") from e
    except subprocess.TimeoutExpired as e:
        raise ClaudeError(f"{' '.join(argv[:2])} timed out") from e


def list_sessions(run=subprocess.run) -> list[Session]:
    p = _call(["claude", "agents", "--json"], run)
    if p.returncode != 0:
        raise ClaudeError((p.stderr or p.stdout).strip() or f"claude agents exited with {p.returncode}")
    return parse_agents(p.stdout)


def stop(key: str, run=subprocess.run) -> None:
    p = _call(["claude", "stop", key], run)
    if p.returncode != 0:
        raise ClaudeError((p.stderr or p.stdout).strip())


def remove(key: str, run=subprocess.run) -> bool:
    """False when claude refuses, for example while the session still has unsaved work."""
    return _call(["claude", "rm", key], run).returncode == 0


def launch(argv: list[str], cwd: str, run=subprocess.run) -> str:
    """Starts a background session and returns the id `claude attach` takes."""
    if not os.path.isdir(cwd):
        raise ClaudeError(f"{cwd} does not exist.")
    p = _call(argv, run, cwd=cwd)
    out = (p.stdout or "") + (p.stderr or "")
    if p.returncode != 0:
        if "Workspace not trusted" in out:
            raise UntrustedDir(cwd)
        raise ClaudeError(out.strip() or f"claude exited with {p.returncode}")
    found = re.search(r"claude attach (\S+)", out)
    if not found:
        raise ClaudeError(out.strip() or "claude --bg printed no session id")
    return found.group(1)
