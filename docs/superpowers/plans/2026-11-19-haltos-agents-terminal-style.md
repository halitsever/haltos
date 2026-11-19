# HaltOS Agents Terminal Style Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle HaltOS Agents as a monospace, Claude Code-like tool with keyboard shortcuts, keeping every mouse path.

**Architecture:** `transcript.py` learns tool results, `+N -M` line counts and the model. The controller passes them to QML through the feed model and `selected`, and gains `step()` for Alt+↑/↓. QML gets a root monospace font, an `Ansi` colour singleton and redrawn list, detail, search and key bar.

**Tech Stack:** Python 3, PySide6 6.10 (apt), Kirigami 6 QML, unittest.

**Spec:** `docs/superpowers/specs/2026-11-19-haltos-agents-terminal-style-design.md`

## Global Constraints

- No new packages. Font: JetBrains Mono through `Kirigami.Theme.fixedWidthFont`.
- ANSI colours: red `#ef4444`, green `#22c55e`, yellow `#eab308`, blue `#3b82f6`, cyan `#06b6d4`.
- Glyphs: need `!` yellow, work `▶` blue, done `✓` dimmed. Prompt `$` green, tool `⏺ Name(arg)` cyan, result `  ⎿ line` dimmed (red when `is_error`), input `>`.
- Key bar copy, exactly: `esc kes`, `ctrl+n yeni`, `ctrl+f ara`, `ctrl+t terminal`, `alt+↑↓ geç`.
- Every keyboard action is also clickable. Agent text is plain text, never markdown.
- Run tests with `cd agents && python3 -m unittest discover -s tests`.

## Review Focus

1. Esc on an agent that is waiting: Esc on a permission prompt means "deny", so Esc must do nothing unless the agent is working. Task 2 pins it in the controller.
2. `tool_result` content that is a list with image blocks, empty, or not text: no item, no crash. Task 1.
3. Edit/MultiEdit/Write inputs with missing or non-string fields: counts `0`, no crash. Task 1.
4. A transcript with no model or only `<synthetic>`: model `""`, header shows no ` · `. Tasks 1 and 3.
5. Alt+↑/↓ with no agents or at the list ends: selection stays, no crash. Task 2.

---

### Task 1: Transcript: results, line counts, model

**Files:**
- Modify: `agents/haltos_agents/transcript.py`
- Test: `agents/tests/test_transcript.py`

**Interfaces:**
- Produces:
  - `FeedItem(kind: str, text: str, name: str = "", added: int = 0, removed: int = 0, error: bool = False)`. Kinds: `prompt`, `text`, `tool` (`name` = tool name, `text` = argument only), `result` (`text` = first non-empty line, `error` from `is_error`).
  - `line_counts(name: str, args: dict) -> tuple[int, int]`
  - `last_model(path: Path, tail_bytes: int = 512_000) -> str`
  - `short_model(model: str) -> str`
- `tool_summary` and `pending_question` keep their current output. The tool argument in the feed is truncated so that `Name(arg)` stays within 80 characters.

- [ ] **Step 1: Write the failing tests** (update `test_feed_kinds_and_order` and `test_tool_summary_uses_file_path_and_is_truncated` to the new shape)

```python
def test_feed_kinds_and_order(self):
    p = self.write([user("build it"), text("Building now."), tool("Bash", "t1", command="npm run build"), result("t1")])
    items = read_feed(p)
    self.assertEqual([i.kind for i in items], ["prompt", "text", "tool", "result"])
    self.assertEqual((items[2].name, items[2].text), ("Bash", "npm run build"))
    self.assertEqual(items[3].text, "ok")

def test_result_first_line_error_and_list_content(self):
    rows = [
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "a", "is_error": True, "content": "\n\nboom\nmore"}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "b", "content": [{"type": "image"}, {"type": "text", "text": "42 passed"}]}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "c", "content": [{"type": "image"}]}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "d", "content": "x" * 300}]}},
    ]
    items = read_feed(self.write(rows))
    self.assertEqual([(i.text[:9], i.error) for i in items], [("boom", True), ("42 passed", False), ("x" * 9, False)])
    self.assertLessEqual(len(items[2].text), 80)

def test_line_counts(self):
    self.assertEqual(line_counts("Edit", {"old_string": "a\nb\nc", "new_string": "a\nB\nC\nd"}), (3, 2))
    self.assertEqual(line_counts("Write", {"content": "1\n2\n3\n"}), (3, 0))
    self.assertEqual(line_counts("MultiEdit", {"edits": [{"old_string": "a", "new_string": "b"}, {"old_string": "", "new_string": "c"}]}), (2, 1))
    self.assertEqual(line_counts("Edit", {"old_string": None}), (0, 0))
    self.assertEqual(line_counts("MultiEdit", {"edits": ["x", None]}), (0, 0))
    self.assertEqual(line_counts("Bash", {"command": "ls"}), (0, 0))

def test_tool_item_carries_counts(self):
    item = read_feed(self.write([tool("Edit", "t1", file_path="/a.py", old_string="x", new_string="y\nz")]))[0]
    self.assertEqual((item.name, item.text, item.added, item.removed), ("Edit", "/a.py", 2, 1))

def test_model_is_last_real_one_and_shortened(self):
    rows = [
        {"type": "assistant", "message": {"model": "claude-sonnet-5-5", "content": []}},
        {"type": "assistant", "message": {"model": "claude-opus-5-5", "content": []}},
        {"type": "assistant", "message": {"model": "<synthetic>", "content": []}},
    ]
    self.assertEqual(last_model(self.write(rows)), "claude-opus-5-5")
    self.assertEqual(last_model(self.write([user("hi")], name="none.jsonl")), "")
    self.assertEqual(short_model("claude-opus-5-5"), "opus-5.5")
    self.assertEqual(short_model("claude-haiku-4-5-20251001"), "haiku-4.5")
    self.assertEqual(short_model("claude-fable-5-2[1m]"), "fable-5.2[1m]")
    self.assertEqual(short_model(""), "")
```

The truncation test keeps `len(item.name) + len(item.text) + 2 <= 80` for a 300-character command.

- [ ] **Step 2: Run to verify they fail**

Run: `cd agents && python3 -m unittest tests.test_transcript`
Expected: FAIL / ImportError on `line_counts`, `last_model`, `short_model`.

- [ ] **Step 3: Implement in `transcript.py`**

`line_counts` counts changed lines with `difflib.SequenceMatcher` over `splitlines()` (Edit: old vs new; MultiEdit: sum per dict edit; Write: all lines added). Non-string fields count as empty. `short_model`: drop the `claude-` prefix and an 8-digit date suffix, then turn the trailing `-N-M` into `-N.M`, keeping any `[...]` tag.

- [ ] **Step 4: Run to verify they pass**

Run: `cd agents && python3 -m unittest discover -s tests`
Expected: OK

- [ ] **Step 5: Commit** `feat(agents): read tool results, line counts and model from transcripts`

### Task 2: Controller: feed roles, model, age, step, safe interrupt

**Files:**
- Modify: `agents/haltos_agents/app.py`, `agents/haltos_agents/names.py`
- Test: `agents/tests/test_app.py`, `agents/tests/test_names.py`

**Interfaces:**
- Consumes: Task 1's `FeedItem` fields, `last_model`, `short_model`.
- Produces:
  - `names.age(seconds: float) -> str`
  - feed roles `kind, body, name, added, removed, error`
  - agent roles add `age` (`"need"`, `age(now - started_at)` or `"done"`)
  - `selected` adds `project` (cwd basename) and `model` (short form, `""` if unknown)
  - `@Slot(int) step(delta)` selects the agent `delta` rows away in list order and clamps at the ends
  - `interrupt()` only acts when the selected agent's group is `work`

- [ ] **Step 1: Write the failing tests**

```python
# test_names.py
def test_age(self):
    self.assertEqual([age(s) for s in (0, 59, 61, 3599, 3600, 4320)], ["0m", "0m", "1m", "59m", "1h0m", "1h12m"])

# test_app.py (ControllerTest)
def test_step_moves_and_clamps(self):
    self.c._on_polled([session("a"), session("b")], "")
    self.c.select("a")
    self.c.step(1)
    self.assertEqual(self.c.selectedKey, "b")
    self.c.step(1)
    self.assertEqual(self.c.selectedKey, "b")
    self.c.step(-5)
    self.assertEqual(self.c.selectedKey, "a")

def test_step_without_agents_does_nothing(self):
    self.c.step(1)
    self.assertEqual(self.c.selectedKey, "")

def test_interrupt_only_while_working(self):
    sent = []
    self.c._act = lambda fn: sent.append(fn) or True
    self.c.sessions = [Session("a", "s", "a", "/tmp", "background", "", "waiting", 0.0, True)]
    self.c._selected = "a"
    self.c.interrupt()
    self.assertEqual(sent, [])
    self.c.sessions = [Session("a", "s", "a", "/tmp", "background", "", "busy", 0.0, True)]
    self.c.interrupt()
    self.assertEqual(len(sent), 1)

def test_selected_has_project_and_model(self):
    # a transcript with model claude-opus-5-5 under a temp projects root, found by session id
    ...
    self.assertEqual((sel["project"], sel["model"]), ("kahvefalin", "opus-5.5"))
```

For the last test, point the module's `find_transcript` at a temp root (patch `A.find_transcript` to a lambda returning the temp file) and use a session with cwd `/tmp/kahvefalin`.

- [ ] **Step 2: Run to verify they fail**

Run: `cd agents && python3 -m unittest tests.test_app tests.test_names`
Expected: FAIL / AttributeError on `step`, `age`; `interrupt` test fails on the waiting case.

- [ ] **Step 3: Implement**

`_load_feed` stores `self._model = short_model(last_model(path))` (or `""`) and fills the new roles. `step` walks the order of `self._agents` rows and calls `select`.

- [ ] **Step 4: Run to verify they pass**

Run: `cd agents && python3 -m unittest discover -s tests`
Expected: OK

- [ ] **Step 5: Commit** `feat(agents): expose model, age and agent stepping to the UI`

### Task 3: Terminal-style QML

**Files:**
- Create: `agents/qml/Ansi.qml` (`pragma Singleton`, the five colours), `agents/qml/qmldir` (lists `singleton Ansi 1.0 Ansi.qml` and every component), `agents/qml/KeyBar.qml`
- Modify: `agents/qml/Main.qml`, `agents/qml/AgentList.qml`, `agents/qml/AgentDetail.qml`, `agents/qml/SearchResults.qml`, `agents/qml/NewAgentDialog.qml` (only if the root font does not reach it)
- Delete: `agents/qml/StatusDot.qml`
- Test: `agents/tests/test_app.py` (`BannerTest` class gets the QML checks)

**Interfaces:**
- Consumes: Task 2's roles, `selected.project`, `selected.model`, `step(int)`, `interrupt()`.
- Produces: `Main.trigger(action: string)` with actions `interrupt`, `new`, `search`, `terminal`, `prev`, `next`. Shortcuts (`Ctrl+N`, `Ctrl+F`, `Ctrl+T`, `Alt+Up`, `Alt+Down`) and key bar buttons both call it. Esc is handled in the input's and search field's `Keys.onEscapePressed`, not as a window Shortcut, so dialogs keep their own Esc.

Layout follows mockup C in the spec: `AGENTS` label, rows `glyph name … age`, header `name` green + `project:branch · model` dimmed (no ` · ` when the model is empty), feed rows by kind, question options as flat `[1] Evet` buttons, `>` input under a separator, key bar at the bottom of the window. The root window sets `font: Kirigami.Theme.fixedWidthFont`. Agent text uses `Text.PlainText`, indented two spaces.

- [ ] **Step 1: Write the failing QML test**

```python
def test_terminal_ui(self):
    # load Main as BannerTest does
    bar = root.findChild(QObject, "keyBar")
    labels = [b.property("text") for b in bar.findChildren(QObject) if b.property("objectName", "").startswith("key:")]
    self.assertEqual(labels, ["esc kes", "ctrl+n yeni", "ctrl+f ara", "ctrl+t terminal", "alt+↑↓ geç"])
    QMetaObject.invokeMethod(root, "trigger", Q_ARG("QVariant", "new"))
    self.assertTrue(root.findChild(QObject, "newAgentDialog").property("opened"))
    self.assertIn("JetBrains Mono", root.property("font").family())
```

Key bar buttons get `objectName: "key:" + action`. If reading children order is unreliable, compare as sets plus a count.

- [ ] **Step 2: Run to verify it fails**

Run: `cd agents && python3 -m unittest tests.test_app`
Expected: FAIL (`keyBar` not found).

- [ ] **Step 3: Implement the QML**

- [ ] **Step 4: Run the suite and the smoke run**

Run: `cd agents && python3 -m unittest discover -s tests && ./haltos-agents --smoke`
Expected: OK, smoke exit 0 with no QML warnings in the output.

- [ ] **Step 5: Look at it**

Render the window offscreen to a PNG (`QQuickWindow.grabWindow()` from a short scratchpad script with live sessions) and compare against mockup C. Fix what differs.

- [ ] **Step 6: Commit** `feat(agents): terminal style UI with keyboard shortcuts`

### Task 4: Docs and finish

**Files:**
- Modify: `docs/testing.md` (new manual checks: shortcuts, Esc only interrupts a working agent, mouse paths), `AGENTS.md` if it describes the UI.

- [ ] **Step 1:** Update the docs; run `cd agents && python3 -m unittest discover -s tests` → OK.
- [ ] **Step 2: Commit** `docs(agents): describe terminal style and shortcuts`, push `feat/agents`.
