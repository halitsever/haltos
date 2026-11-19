# HaltOS Agents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A native Kirigami desktop app that lists, controls, starts and searches Claude Code agents on HaltOS, built on Claude Code's own background sessions.

**Architecture:** A Qt-free Python core (`agents/haltos_agents/`) wraps the `claude` CLI (`agents --json`, `--bg`, `attach`, `stop`, `rm`), parses transcripts, indexes them for search and decides notifications. Each core module is unit-tested with stdlib `unittest`. A thin PySide6 layer (`app.py` + `qml/`) exposes the core to a Kirigami inbox window with a tray icon. `install.sh` ships it per user.

**Tech Stack:** Python 3 (stdlib only in the core), PySide6 6.10 from Ubuntu apt, QML + Kirigami 6, SQLite FTS5, `notify-send`, bash (`install.sh`, `tests/user.sh`).

**Spec:** `docs/superpowers/specs/2026-11-19-haltos-agents-design.md`

## Global Constraints

- Ubuntu with Plasma 6, Qt 6 only. PySide6 comes from apt (`python3-pyside6.qtqml`, `python3-pyside6.qtquick`, `python3-pyside6.qtwidgets`), never pip.
- No third-party Python packages. Tests use `unittest`: `python3 -m unittest discover -s agents/tests -t agents`.
- Only `app.py` and `qml/` import Qt. Every other module in `haltos_agents/` must import without PySide6, so CI can test it on a plain runner.
- Every `claude` process the app starts gets `clean_env()`: no inherited `CLAUDE_CODE_*` or `CLAUDECODE` variables.
- New agents start with `--permission-mode auto`.
- Group labels in the UI, verbatim: `seni bekliyor`, `çalışıyor`, `bitti`. UI copy is Turkish. Code, comments, logs and test names are English.
- State mapping, verbatim from the spec: `blocked` → seni bekliyor, `busy` → çalışıyor, `idle` and `done` → bitti.
- Notification rules: `blocked` always notifies. `busy` → `idle` notifies only after at least 60 seconds busy. No notice for the agent shown in the focused window.
- The v1 Terminal button opens Konsole: `konsole --profile HaltOS -e claude attach <id>`. No embedded terminal widget.
- Repo rules from `AGENTS.md`: new shell scripts go into the shellcheck list in `ci.yml`; generated icons come from `tools/build-assets.py`; no emoji; short comments that explain why; conventional-commit subjects with no body or trailer.

## Review Focus

1. **Interactive sessions in `claude agents --json`** have `pid` and `status` instead of `id` and `state`, and cannot be attached. They must still be listed under the right group, with attach, input, stop and archive disabled. Test: Task 2.
2. **A failing `claude` call** (binary missing, non-zero exit, non-JSON output such as an update banner) must leave the last good list on screen with an error line, and never crash the poller. Test: Task 2.
3. **Search queries containing FTS5 syntax** (`"`, `*`, `-`, `AND`, parentheses) or Turkish letters must search literally and never raise. Test: Task 4.
4. **Startup with sessions that are already blocked** (3 are blocked on this machine today) must not fire a burst of notifications. Test: Task 5.
5. **A transcript being written while it is read** (half-written last line) or a very large transcript must yield a feed without error, reading only the tail. Test: Task 3.

---

### Task 1: Probe Claude Code's control surface

No product code. This answers the spec's open risks before anything is built on them.

**Files:**
- Modify: `docs/superpowers/specs/2026-11-19-haltos-agents-design.md` (append a "Probe results" section)

**Interfaces:**
- Produces: a key table that Tasks 3, 6 and 8 rely on. It must give the bytes for: approve a permission prompt, deny it, pick option N in an AskUserQuestion prompt, interrupt. It also states whether two attaches to one session can coexist.

- [ ] **Step 1: Start a throwaway background session**

In a scratch git repo under the session scratchpad, with a clean environment:
Run: `env -u CLAUDECODE $(env | grep -o '^CLAUDE_CODE_[A-Z_]*' | sed 's/^/-u /') claude --bg --permission-mode auto --name probe "say hi"`
Expected: an id is printed, and `claude agents --json` shows `probe` going `busy` then `idle`.

- [ ] **Step 2: Write into an attached PTY from Python**

Use `pty.fork()` to run `claude attach probe`. Write `\x1b[200~what is 2+2\x1b[201~\r`, wait 20 s, then read the session's transcript (`~/.claude/projects/*/<sessionId>.jsonl`).
Expected: a `user` entry with content `what is 2+2` and an assistant answer. Repeat with a two-line text and with `/model`. Then write `\x1b` during a long answer and check that the state returns to `idle`.

- [ ] **Step 3: Check two attaches at once**

While the Python attach from Step 2 is open, run `konsole --profile HaltOS -e claude attach probe`, type in Konsole, and check that the Python side sees the output.
Expected: record "coexist: yes" or "coexist: no".

- [ ] **Step 4: Record the prompt keys**

Start `claude --bg --permission-mode default --name probe-perm "create the file x.txt with hi"` and attach. Find the bytes that approve and deny the permission prompt. Do the same with a prompt that makes Claude call AskUserQuestion with 3 options, and find how option N is chosen. Also record what `claude agents --json` reports while each prompt is open.

- [ ] **Step 5: Write the results into the spec and clean up**

Append a "Probe results" section to the spec with the key table and the coexist answer. Then `claude stop` and `claude rm` both probe sessions.
**Stop condition:** if Step 2 fails (text does not reach the session), stop and report to the owner. The input box design depends on it.

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/specs/2026-11-19-haltos-agents-design.md
git commit -m "docs: record claude attach probe results for agents"
```

### Task 2: Session list and CLI wrapper

**Files:**
- Create: `agents/haltos_agents/__init__.py` (empty)
- Create: `agents/haltos_agents/claude.py`
- Create: `agents/tests/__init__.py`, `agents/tests/test_claude.py`
- Modify: `.github/workflows/ci.yml` (new job `agents` on `ubuntu-latest`: `python3 -m unittest discover -s agents/tests -t agents`)

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class Session`: `key: str` (the bg `id`, or `pid:<pid>` for interactive), `session_id: str`, `name: str`, `cwd: str`, `kind: str` (`background` or `interactive`), `state: str` (raw), `started_at: float` (seconds), `attachable: bool` (true only for background).
  - `GROUPS = ("need", "work", "done")` and `group_for(state: str) -> str`. Mapping: `blocked`→`need`, `busy`→`work`, `idle`/`done`→`done`, anything else→`work`.
  - `parse_agents(text: str) -> list[Session]`, which raises `ClaudeError` on non-JSON.
  - `clean_env(environ: Mapping[str, str]) -> dict[str, str]`
  - `start_argv(name: str, prompt: str, model: str | None, worktree: bool) -> list[str]`
  - `resume_argv(session_id: str) -> list[str]`
  - `class ClaudeError(Exception)`
  - `list_sessions(run=subprocess.run) -> list[Session]`, which runs `claude agents --json` with `clean_env(os.environ)` and raises `ClaudeError` on a missing binary, a non-zero exit or bad JSON.
  - `stop(key: str, run=...) -> None`, `remove(key: str, run=...) -> bool` (False when `claude rm` refuses).

- [ ] **Step 1: Write the failing tests**

```python
BG = '{"id":"e9f3ca06","cwd":"/home/u","kind":"background","startedAt":1794845326807,"sessionId":"e9f3-...","name":"seo-fix","state":"blocked"}'
IA = '{"pid":4634,"cwd":"/home/u","kind":"interactive","startedAt":1794912111186,"sessionId":"64f5-...","name":"halit-b9","status":"idle"}'

def test_background_session(self):
    s = parse_agents(f"[{BG}]")[0]
    self.assertEqual((s.key, s.state, s.attachable), ("e9f3ca06", "blocked", True))
    self.assertEqual(group_for(s.state), "need")
    self.assertAlmostEqual(s.started_at, 1794845326.807)

def test_interactive_session_uses_status_and_pid(self):
    s = parse_agents(f"[{IA}]")[0]
    self.assertEqual((s.key, s.state, s.attachable), ("pid:4634", "idle", False))
    self.assertEqual(group_for(s.state), "done")

def test_groups(self):
    self.assertEqual([group_for(x) for x in ("blocked", "busy", "idle", "done", "weird")],
                     ["need", "work", "done", "done", "work"])

def test_bad_json_raises(self):
    with self.assertRaises(ClaudeError): parse_agents("Update available\n[")

def test_missing_binary_raises(self):
    def run(*a, **k): raise FileNotFoundError("claude")
    with self.assertRaises(ClaudeError): list_sessions(run=run)

def test_nonzero_exit_raises(self):
    run = lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "boom")
    with self.assertRaises(ClaudeError): list_sessions(run=run)

def test_clean_env_drops_claude_markers(self):
    env = clean_env({"HOME": "/h", "CLAUDECODE": "1", "CLAUDE_CODE_CHILD_SESSION": "x", "CLAUDE_CONFIG_DIR": "/c"})
    self.assertEqual(env, {"HOME": "/h", "CLAUDE_CONFIG_DIR": "/c"})

def test_start_argv(self):
    self.assertEqual(start_argv("seo-fix", "fix meta", "opus", True),
        ["claude", "--bg", "--permission-mode", "auto", "--name", "seo-fix", "--model", "opus", "-w", "seo-fix", "fix meta"])
    self.assertEqual(start_argv("x", "p", None, False), ["claude", "--bg", "--permission-mode", "auto", "--name", "x", "p"])

def test_resume_argv(self):
    self.assertEqual(resume_argv("abc"), ["claude", "--bg", "--resume", "abc"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s agents/tests -t agents`
Expected: FAIL with `ModuleNotFoundError: No module named 'haltos_agents.claude'`

- [ ] **Step 3: Implement `agents/haltos_agents/claude.py` with the interfaces above**

`clean_env` keeps `CLAUDE_CONFIG_DIR` (the user's choice, not a session marker) and drops `CLAUDECODE` and every `CLAUDE_CODE_*`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s agents/tests -t agents`
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add agents/ .github/workflows/ci.yml
git commit -m "feat(agents): parse claude background sessions"
```

### Task 3: Transcript feed and pending question

**Files:**
- Create: `agents/haltos_agents/transcript.py`
- Test: `agents/tests/test_transcript.py`, `agents/tests/fixtures/` (small hand-written `.jsonl` files)

**Interfaces:**
- Consumes: the key table from Task 1.
- Produces:
  - `find_transcript(session_id: str, root: Path = ~/.claude/projects) -> Path | None`, which globs `root/*/<session_id>.jsonl`.
  - `@dataclass FeedItem`: `kind: str` (`prompt`, `text` or `tool`), `text: str`.
  - `read_feed(path: Path, limit: int = 50, tail_bytes: int = 512_000) -> list[FeedItem]`
  - `@dataclass Question`: `text: str`, `options: list[tuple[str, bytes]]` (label, key bytes to send).
  - `pending_question(path: Path) -> Question | None`

- [ ] **Step 1: Write the failing tests**

Fixtures use the real line shapes: `{"type":"user","message":{"content":"..."}}`, `{"type":"assistant","message":{"content":[{"type":"text"|"tool_use"|"thinking",...}]}}`, `{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":...}]}}`, plus lines with `isMeta: true` and `isSidechain: true`.

```python
def test_feed_kinds_and_order(self):
    items = read_feed(FIX / "basic.jsonl")
    self.assertEqual([i.kind for i in items], ["prompt", "text", "tool"])
    self.assertEqual(items[2].text, "Bash: npm run build")

def test_feed_skips_meta_sidechain_and_thinking(self):
    self.assertNotIn("SECRET-THINKING", " ".join(i.text for i in read_feed(FIX / "noise.jsonl")))

def test_tool_summary_truncated(self):
    self.assertLessEqual(len(read_feed(FIX / "longcmd.jsonl")[-1].text), 80)

def test_half_written_last_line_is_ignored(self):
    self.assertEqual(len(read_feed(FIX / "partial.jsonl")), 2)

def test_large_file_reads_tail_only(self):
    p = self.tmp / "big.jsonl"  # 5 MB of prompts, last one "LAST"
    ...
    self.assertEqual(read_feed(p, limit=1)[0].text, "LAST")

def test_pending_ask_user_question(self):
    q = pending_question(FIX / "ask.jsonl")
    self.assertEqual(q.text, "Merge edeyim mi?")
    self.assertEqual([o[0] for o in q.options], ["Evet", "Hayır", "Sonra"])
    self.assertEqual(q.options[1][1], KEY_TABLE_OPTION(2))  # bytes from Task 1

def test_answered_question_is_not_pending(self):
    self.assertIsNone(pending_question(FIX / "ask_answered.jsonl"))

def test_pending_permission(self):
    q = pending_question(FIX / "perm.jsonl")
    self.assertEqual([o[0] for o in q.options], ["İzin ver", "Reddet"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s agents/tests -t agents`
Expected: FAIL, module missing.

- [ ] **Step 3: Implement `transcript.py`**

- **Tail reading:** seek to `max(0, size - tail_bytes)`, drop the first partial line, and skip any line that fails `json.loads`.
- **Tool summary:** `"<name>: <first of input.command | input.file_path | input.pattern | input.description>"`, cut to 80 characters.
- **Pending detection:** an assistant `tool_use` with no later `tool_result` that has the same `tool_use_id`. `AskUserQuestion` reads `input.questions[0].question` and the option labels. Any other tool is a permission prompt with the two options above. Keys come from the Task 1 table.

- [ ] **Step 4: Run the tests to verify they pass**

Expected: OK

- [ ] **Step 5: Commit**

```bash
git add agents/haltos_agents/transcript.py agents/tests/
git commit -m "feat(agents): read transcript feed and pending questions"
```

### Task 4: Session search index

**Files:**
- Create: `agents/haltos_agents/search.py`
- Test: `agents/tests/test_search.py`

**Interfaces:**
- Produces:
  - `@dataclass Hit`: `session_id: str`, `title: str`, `cwd: str`, `mtime: float`, `snippet: str`.
  - `class Index(db_path: Path)`
    - `update(root: Path) -> int`: number of files (re)indexed.
    - `search(query: str, limit: int = 50) -> list[Hit]`: newest first among matches.
- Data: `title` is the last `aiTitle` (from `type: ai-title` lines), falling back to the first user prompt. `cwd` is the last `cwd` field. Indexed text is user prompts plus assistant text, passed through `fold()` first. The table is FTS5 with `tokenize='unicode61 remove_diacritics 0'`, so `ş` and `s` stay distinct.
  - `fold(s: str) -> str`: maps `I`, `İ` and `ı` to `i`, then lower-cases. unicode61 folds `I` to `i`, never to `ı`, so without this `ÇALIŞIYOR` misses `çalışıyor`.

- [ ] **Step 1: Write the failing tests**

```python
def test_finds_prompt_and_reports_title_and_cwd(self):
    hits = self.index.search("meta etiketleri")
    self.assertEqual((hits[0].title, hits[0].cwd), ("SEO meta düzeltme", "/home/u/halit.org"))

def test_turkish_case_insensitive(self):
    self.assertTrue(self.index.search("ÇALIŞIYOR"))  # transcript says "çalışıyor"

def test_fts_syntax_is_literal(self):
    for q in ['"', 'foo*', '-x', 'AND', '(a', 'a OR', "'"]:
        self.index.search(q)  # must not raise

def test_incremental_update(self):
    self.assertEqual(self.index.update(self.root), 0)  # nothing changed since setUp
    touch_and_append(self.root / "p" / "s1.jsonl")
    self.assertEqual(self.index.update(self.root), 1)

def test_deleted_transcript_drops_out(self):
    (self.root / "p" / "s1.jsonl").unlink(); self.index.update(self.root)
    self.assertEqual(self.index.search("meta etiketleri"), [])
```

- [ ] **Step 2: Run the tests to verify they fail**

Expected: FAIL, module missing.

- [ ] **Step 3: Implement `search.py`**

- **Literal queries:** apply `fold()` to the query, split it on whitespace, wrap each term in double quotes with inner quotes doubled, and join the terms with spaces (implicit AND).
- **Snippet:** store the original text in an `UNINDEXED` column. Build the snippet in Python: about 60 characters of the original around the first place where `fold(original)` contains the first term. The FTS5 `snippet()` would show the folded text.
- **Incremental updates:** a `files(path PRIMARY KEY, mtime)` table drives the reindex.

- [ ] **Step 4: Run the tests to verify they pass**

Expected: OK

- [ ] **Step 5: Commit**

```bash
git add agents/haltos_agents/search.py agents/tests/test_search.py
git commit -m "feat(agents): full-text search over claude transcripts"
```

### Task 5: Notification policy

**Files:**
- Create: `agents/haltos_agents/notify.py`
- Test: `agents/tests/test_notify.py`

**Interfaces:**
- Consumes: `Session`, `group_for` (Task 2).
- Produces:
  - `@dataclass Notice`: `key: str`, `title: str`, `body: str`.
  - `class NotifyPolicy(min_busy: float = 60.0)`
    - `observe(sessions: list[Session], now: float, focused_key: str | None) -> list[Notice]`
  - Copy, verbatim:
    - blocked: title `"<name> seni bekliyor"`, body `"Cevabını bekliyor."`
    - finished: title `"<name> bitti"`, body `"<N> dk çalıştı."`

- [ ] **Step 1: Write the failing tests**

```python
def test_first_observation_is_silent(self):
    p = NotifyPolicy()
    self.assertEqual(p.observe([s("a", "blocked"), s("b", "blocked")], 0, None), [])

def test_becoming_blocked_notifies(self):
    p = NotifyPolicy(); p.observe([s("a", "busy")], 0, None)
    self.assertEqual([n.title for n in p.observe([s("a", "blocked")], 5, None)], ["a seni bekliyor"])

def test_short_busy_to_idle_is_silent(self):
    p = NotifyPolicy(); p.observe([s("a", "busy")], 0, None)
    self.assertEqual(p.observe([s("a", "idle")], 59, None), [])

def test_long_busy_to_idle_notifies(self):
    p = NotifyPolicy(); p.observe([s("a", "idle")], 0, None); p.observe([s("a", "busy")], 10, None)
    self.assertEqual(p.observe([s("a", "idle")], 190, None)[0].body, "3 dk çalıştı.")

def test_focused_agent_is_silent(self):
    p = NotifyPolicy(); p.observe([s("a", "busy")], 0, None)
    self.assertEqual(p.observe([s("a", "blocked")], 5, "a"), [])

def test_new_session_appearing_blocked_notifies(self):
    p = NotifyPolicy(); p.observe([], 0, None)
    self.assertEqual(len(p.observe([s("n", "blocked")], 3, None)), 1)
```

- [ ] **Step 2: Run the tests to verify they fail**

Expected: FAIL, module missing.

- [ ] **Step 3: Implement `notify.py`**

Keep a per-key last state and a busy-since timestamp. Minutes are rounded down, with a minimum of 1.

- [ ] **Step 4: Run the tests to verify they pass**

Expected: OK

- [ ] **Step 5: Commit**

```bash
git add agents/haltos_agents/notify.py agents/tests/test_notify.py
git commit -m "feat(agents): decide when agent state changes notify"
```

### Task 6: Attached PTY

**Files:**
- Create: `agents/haltos_agents/attach.py`
- Test: `agents/tests/test_attach.py`

**Interfaces:**
- Consumes: `clean_env` (Task 2), the key table (Task 1).
- Produces:
  - `class Attachment(argv: list[str], env: dict[str, str])`
    - `start() -> None`
    - `paste(text: str) -> None`: writes `b"\x1b[200~" + utf8 + b"\x1b[201~" + b"\r"`.
    - `key(data: bytes) -> None`
    - `close() -> None`
    - `alive: bool` property
  - `attach_argv(key: str) -> list[str]` = `["claude", "attach", key]`.
  - A daemon thread drains the PTY output so the child never blocks on a full buffer.

- [ ] **Step 1: Write the failing tests**

The child is a small Python script that copies its stdin bytes to a file, with the TTY in raw mode.

```python
def test_paste_writes_bracketed_utf8_and_enter(self):
    a = Attachment(recorder_argv(self.out), {}); a.start(); a.paste("çalış\nikinci"); a.close()
    self.assertEqual(self.out.read_bytes(), b"\x1b[200~" + "çalış\nikinci".encode() + b"\x1b[201~\r")

def test_key_writes_raw_bytes(self):
    a = Attachment(recorder_argv(self.out), {}); a.start(); a.key(b"\x1b"); a.close()
    self.assertEqual(self.out.read_bytes(), b"\x1b")

def test_dead_child_reports_not_alive_and_paste_is_noop(self):
    a = Attachment(["true"], {}); a.start(); wait_until(lambda: not a.alive)
    a.paste("x")  # must not raise

def test_noisy_child_does_not_block(self):
    a = Attachment(["yes"], {}); a.start(); time.sleep(1); self.assertTrue(a.alive); a.close()
```

- [ ] **Step 2: Run the tests to verify they fail**

Expected: FAIL, module missing.

- [ ] **Step 3: Implement `attach.py` with `pty.fork()`, a reader thread and SIGTERM on close**

Set the PTY size to 120x40 so Claude Code lays out normally.

- [ ] **Step 4: Run the tests to verify they pass**

Expected: OK

- [ ] **Step 5: Commit**

```bash
git add agents/haltos_agents/attach.py agents/tests/test_attach.py
git commit -m "feat(agents): drive claude attach through a pty"
```

### Task 7: Inbox window, polling and tray

**Files:**
- Create: `agents/haltos_agents/__main__.py`: arguments `--tray` (start hidden) and `--smoke` (load QML, then exit 0).
- Create: `agents/haltos_agents/app.py`
- Create: `agents/qml/Main.qml`, `agents/qml/AgentList.qml`, `agents/qml/AgentDetail.qml`
- Create: `agents/haltos-agents` (sh launcher: `PYTHONPATH=<dir> exec python3 -m haltos_agents "$@"`)
- Modify: `.github/workflows/ci.yml` (add `agents/haltos-agents` to shellcheck)

**Interfaces:**
- Consumes: `list_sessions`, `group_for`, `Session` (Task 2); `find_transcript`, `read_feed`, `pending_question` (Task 3).
- Produces (used by Tasks 8 and 9):
  - `class Controller(QObject)`
    - Properties: `agents` (`AgentModel`), `feed` (`FeedModel`), `error: str`, `selectedKey: str`.
    - Slots: `select(key)`, `refresh()`.
    - Signal: `sessionsChanged(list)`.
  - `AgentModel` roles: `key`, `name`, `group`, `state`, `cwd`, `branch`, `attachable`.
  - `FeedModel` roles: `kind`, `text`; it also exposes `question` (`text` plus option labels) or null.

- [ ] **Step 1: Smoke test (manual-free)**

Run: `QT_QPA_PLATFORM=offscreen python3 agents/haltos-agents --smoke`
Expected before implementation: fails. After: exit 0 and no QML warnings on stderr.

- [ ] **Step 2: Implement `app.py` and the QML**

- **Polling:** a `QTimer` every 2 s runs `list_sessions` on `QThreadPool`. On `ClaudeError`, keep the last list and set `error`, which shows as a `Kirigami.InlineMessage`.
- **Branch:** from `git -C <cwd> branch --show-current`, cached per cwd for 30 s.
- **Feed:** reloads when the selected transcript's mtime changes.
- **Layout:** follows inbox mockup A. The sidebar `ListView` uses `section.property: "group"`, ordered need, work, done. The detail pane has a header, the feed, the question card and an input field. Rows that are not attachable show the input and actions disabled, with the tooltip `Bu oturum bir terminalde açık, buradan yönetilemez.`
- **Tray and window:** a `QSystemTrayIcon` with the `haltos-agents` icon and the menu `Aç`, `Çık`. Closing the window hides it.
- **Single instance:** a `QLocalServer` named `haltos-agents`. A second launch sends "show" and exits.
- **Environment:** `QT_QUICK_CONTROLS_STYLE=org.kde.desktop` unless already set. App name `HaltOS Agents`, desktop file name `haltos-agents`.

- [ ] **Step 3: Run the smoke test**

Run: `QT_QPA_PLATFORM=offscreen python3 agents/haltos-agents --smoke`
Expected: exit 0, no `qml:` warnings.

- [ ] **Step 4: Check the real window**

Run: `SHOT_WINDOW=1 tools/clean-shot.sh /tmp/agents.png agents/haltos-agents`
Expected: the real sessions from `claude agents --json` appear under the three groups, in HaltMono. Show the screenshot to the owner.

- [ ] **Step 5: Commit**

```bash
git add agents/ .github/workflows/ci.yml
git commit -m "feat(agents): native inbox window with tray and live session list"
```

### Task 8: Acting on an agent

**Files:**
- Modify: `agents/haltos_agents/app.py`, `agents/qml/AgentDetail.qml`
- Create: `agents/haltos_agents/hidden.py` (archived keys in `~/.local/state/haltos-agents/hidden.json`)
- Test: `agents/tests/test_hidden.py`

**Interfaces:**
- Consumes: `Attachment`, `attach_argv` (Task 6); `stop`, `remove` (Task 2); `pending_question` (Task 3); the coexist answer (Task 1).
- Produces:
  - Controller slots: `send(text)`, `answer(index)`, `interrupt()`, `kill()`, `openTerminal()`, `archive()`.
  - `hidden.load(path) -> set[str]`, `hidden.add(path, key) -> None`.

- [ ] **Step 1: Write the failing tests for `hidden.py`**

```python
def test_missing_file_is_empty(self): self.assertEqual(load(self.p), set())
def test_add_persists(self): add(self.p, "a"); add(self.p, "a"); self.assertEqual(load(self.p), {"a"})
def test_corrupt_file_is_empty(self): self.p.write_text("{"); self.assertEqual(load(self.p), set())
```

- [ ] **Step 2: Run them to verify they fail, implement `hidden.py`, run them to verify they pass**

Run: `python3 -m unittest discover -s agents/tests -t agents`
Expected: FAIL, then OK.

- [ ] **Step 3: Wire the slots**

- **Attachments:** one `Attachment` per selected attachable agent, opened lazily and closed when the app quits.
- **`send`:** `paste`.
- **`answer(i)`:** `key(question.options[i][1])`.
- **`interrupt`:** `key(b"\x1b")`.
- **`kill`:** a `Kirigami.PromptDialog` with the text `<name> durdurulsun mu? Konuşma silinmez.`, then `stop`.
- **`openTerminal`:** `konsole --profile HaltOS -e claude attach <key>`, started with `clean_env`. If Task 1 said coexist is "no", close the attachment first and reopen it when that Konsole process exits.
- **`archive`** (only in the `bitti` group): try `remove`. When it returns False, call `hidden.add`. Hidden keys are filtered out of `AgentModel`.

- [ ] **Step 4: Verify against a real agent**

Start a throwaway agent from a terminal (`claude --bg --name try "count to 3"`). In the app, send `now count to 5`, then interrupt, open Terminal, archive.
Expected: each action shows in Konsole and in `claude agents --json`, and `try` leaves the list.

- [ ] **Step 5: Commit**

```bash
git add agents/
git commit -m "feat(agents): send, answer, interrupt, stop and archive agents"
```

### Task 9: New agent, search and notifications in the app

**Files:**
- Create: `agents/haltos_agents/names.py`
- Test: `agents/tests/test_names.py`
- Create: `agents/qml/NewAgentDialog.qml`, `agents/qml/SearchResults.qml`
- Modify: `agents/haltos_agents/app.py`, `agents/qml/AgentList.qml`

**Interfaces:**
- Consumes: `start_argv`, `resume_argv`, `clean_env` (Task 2); `Index`, `Hit` (Task 4); `NotifyPolicy`, `Notice` (Task 5).
- Produces:
  - `names.slug(prompt: str, taken: set[str]) -> str`: the first 4 words, ASCII-folded (`ç`→`c`, `ğ`→`g`, `ı`→`i`, `ö`→`o`, `ş`→`s`, `ü`→`u`), lower-case, joined with `-`, at most 30 characters, suffixed `-2`, `-3` and so on when taken.
  - `names.recent_dirs(root: Path, limit: int = 10) -> list[str]`: the `cwd` of the newest transcripts, unique and existing on disk.
  - Controller slots: `newAgent(dir, name, model, worktree, prompt)`, `search(query)`, `resume(sessionId, cwd)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_slug_folds_turkish(self): self.assertEqual(slug("Şu meta etiketlerini düzelt lütfen", set()), "su-meta-etiketlerini-duzelt")
def test_slug_dedupes(self): self.assertEqual(slug("fix it", {"fix-it"}), "fix-it-2")
def test_slug_empty_prompt(self): self.assertEqual(slug("   ", set()), "agent")
def test_recent_dirs_unique_existing_newest_first(self): ...  # three transcripts, one cwd missing on disk
```

- [ ] **Step 2: Run them to verify they fail, implement `names.py`, run them to verify they pass**

Expected: FAIL, then OK.

- [ ] **Step 3: Wire the dialog, search and notifications**

- **New agent dialog fields:**
  - directory: a combo of `recent_dirs` plus a folder picker
  - name: placeholder `otomatik`
  - model: a combo with `varsayılan`, `opus`, `sonnet`, `haiku`
  - worktree: a switch, on when the directory is a git repo
  - prompt: a multi-line text area
- **`newAgent`:** runs `start_argv` with `cwd=dir` and `env=clean_env(os.environ)`. When the name is empty, it uses `slug` against the current names. It then selects the new agent when it appears.
- **Search:** `Index` lives in `~/.cache/haltos-agents/index.sqlite` and updates in the thread pool on startup and every 60 s. A non-empty search field swaps the sidebar for `SearchResults` (title, directory, date, snippet). A click runs `resume_argv` in `hit.cwd`.
- **Notifications:** each poll calls `NotifyPolicy.observe(sessions, time.time(), selectedKey if window is active else None)`. Each `Notice` runs as `QProcess("notify-send", ["-a", "HaltOS Agents", "-i", "haltos-agents", "-A", "open=Aç", title, body])`. If the stdout is `open`, the app shows the window and selects `notice.key`.

- [ ] **Step 4: Verify against the real machine**

Expected:
- A new agent from the dialog appears under `çalışıyor`, and later under `bitti`, with a "bitti" notification if it ran for 60 s or more.
- Searching `HaltOS` lists past sessions, and opening one resumes it.

- [ ] **Step 5: Commit**

```bash
git add agents/
git commit -m "feat(agents): new agent dialog, session search and notifications"
```

### Task 10: Install, undo and docs

**Files:**
- Modify: `install.sh` (`install_system` apt list; new `install_agents` called from `install_user` and `refresh_user`; `undo_user` removals)
- Modify: `tools/build-assets.py` (generate `branding/icons/hicolor/scalable/apps/haltos-agents.svg`)
- Modify: `tests/user.sh`, `tests/system.sh`
- Modify: `AGENTS.md` (the unittest command under "Verify a change"; `agents/` under Gotchas), `Readme.md` (one bullet: **Agents**), `docs/testing.md` (manual checks from Tasks 7 to 9)

**Interfaces:**
- Consumes: the `agents/` tree from Tasks 2 to 9.
- Produces, as installed paths:
  - `$share/haltos/agents/` (copy of `agents/`, without `tests/`)
  - `$share/applications/haltos-agents.desktop` (`Exec=$share/haltos/agents/haltos-agents`)
  - `$conf/autostart/haltos-agents.desktop` (same `Exec`, plus `--tray`)
  - the `haltos-agents` icon

- [ ] **Step 1: Write the failing checks in `tests/user.sh`**

After `install.sh user`:
```bash
check "agents app installed" test -x "$share/haltos/agents/haltos-agents"
check "agents in app menu" grep -q "^Exec=$share/haltos/agents/haltos-agents$" "$share/applications/haltos-agents.desktop"
check "agents autostart in tray" grep -q -- "--tray$" "$conf/autostart/haltos-agents.desktop"
check "agents icon" test -f "$share/icons/hicolor/scalable/apps/haltos-agents.svg"
```
After `undo-user`:
```bash
check "agents menu entry removed" test ! -e "$share/applications/haltos-agents.desktop"
check "agents autostart removed" test ! -e "$conf/autostart/haltos-agents.desktop"
```
In `tests/system.sh`, after install: `check "pyside6 qml installed" dpkg -s python3-pyside6.qtqml`.

- [ ] **Step 2: Run them to verify they fail**

Run: `docker run --rm -v "$PWD:/r" -w /r ubuntu:26.04 tests/user.sh`
Expected: the four agents checks FAIL.

- [ ] **Step 3: Implement**

- **`install_system`:** add `python3-pyside6.qtqml python3-pyside6.qtquick python3-pyside6.qtwidgets qml6-module-org-kde-kirigami libnotify-bin` to the apt list.
- **`install_agents`:** copies with `rm -rf` then `cp -r` (and removes `tests/`), and writes both `.desktop` files with `printf`, the way `queue_firstrun` does.
- **`undo_user`:** already removes `$share/haltos` and `haltos-*` icons. Add the two `.desktop` files.
- **Icon:** in `build-assets.py`, write `haltos-agents.svg` with `grid_svg(FONT["A"], 10, 20, 6)` next to `haltos-logo.svg`.

- [ ] **Step 4: Run all checks**

Run: `python3 tools/build-assets.py && git status --short branding/`, then the docker command from Step 2, then `shellcheck -S warning install.sh agents/haltos-agents tests/user.sh tests/system.sh`, then `python3 -m unittest discover -s agents/tests -t agents`
Expected: only the new icon changes under `branding/`, `all checks passed`, no shellcheck output, unittest OK.

- [ ] **Step 5: Install for real and check by hand**

Run: `./install.sh user`, then open "HaltOS Agents" from the app menu and log out and in.
Expected: the app appears in the menu with its icon and starts in the tray after login.

- [ ] **Step 6: Commit**

```bash
git add install.sh tools/build-assets.py branding/ tests/ AGENTS.md Readme.md docs/testing.md
git commit -m "feat(agents): install the agents app with HaltOS"
```
