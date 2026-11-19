# HaltOS Agents Grid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the list + detail layout with a grid of equal agent tiles, with Ctrl+O zooming into today's detail view.

**Architecture:** The controller reads a short tail and pending question per agent during the poll (worker thread, mtime-cached) and exposes them as roles on the agents model. The agents model moves, inserts and removes rows instead of resetting, so tile delegates (and their focus and drafts) survive polls. QML gets `AgentTile` and `AgentGrid`; `Main.qml` owns a top bar, a `zoomed` flag and the key bar modes; `AgentList.qml` goes away.

**Tech Stack:** Kirigami 6 / QtQuick, PySide6 from apt, unittest.

**Spec:** `docs/superpowers/specs/2026-11-19-haltos-agents-grid-design.md`

## Global Constraints

- No new packages. PySide6 from apt only.
- Monospace everywhere (root `font: Kirigami.Theme.fixedWidthFont` stays), colours from `Ansi`.
- Controller actions keep acting on the selected agent; a tile selects its agent before any action.
- Focus moves only on user actions; a poll never moves it.
- Clickable controls that are not text inputs use `focusPolicy: Qt.NoFocus`.
- Key bar text, grid: `alt+←↑↓→ geç`, `ctrl+o büyüt`, `esc kes`, `ctrl+n yeni`, `ctrl+f ara`, `ctrl+t terminal`.
- Key bar text, zoom: `ctrl+o grid`, `alt+←→ önceki/sonraki`, `esc kes`, `ctrl+n yeni`, `ctrl+t terminal`.
- Comments: short, English, why not what, no em dashes and no ` -- `.
- Commits: conventional subject line only.
- Test command: `python3 -m unittest discover -s agents/tests -t agents` from the repo root.

## Review Focus

1. Typing in a tile while a new agent appears or another one changes group: the tile keeps focus and its text (Task 1 diff, Task 3 test).
2. Focus sits in a tile that is no longer the selected one (a poll moved the selection), then Enter, Esc or a `[n]` button: it acts on that tile's agent (Task 3 test).
3. Transcript missing, unreadable, or its last row bigger than `TILE_BYTES`: empty tail, the poll keeps working (Task 2 test).
4. Window at minimum width or a single agent: one column, no horizontal scroll (Task 3 test).
5. Alt+↑/↓ on the first or last row with a partial last row: clamps, never wraps (Task 3 test).

---

### Task 1: Keyed row diff in ListModel

**Files:**
- Modify: `agents/haltos_agents/app.py` (`ListModel.replace`)
- Test: `agents/tests/test_app.py`

**Interfaces:**
- Produces: `ListModel.replace(rows)` keeps its signature. Rows with a `"key"` (both old and new non-empty and keyed, or old empty) are synced with `beginRemoveRows`/`beginMoveRows`/`beginInsertRows` and `dataChanged`; no `modelReset` after the first fill. Rows without keys still reset.

- [ ] **Step 1: Write the failing tests** in `ControllerTest`:

```python
def test_reorder_moves_rows_without_reset(self):
    m = self.c._agents
    resets, moves, ins, rem = [], [], [], []
    m.modelReset.connect(lambda: resets.append(1))
    m.rowsMoved.connect(lambda *a: moves.append(1))
    m.rowsInserted.connect(lambda *a: ins.append(1))
    m.rowsRemoved.connect(lambda *a: rem.append(1))
    rows = lambda ks: [{"key": k, "age": k} for k in ks]
    m.replace(rows("abc"))
    m.replace(rows("cab"))
    m.replace(rows("ac"))
    m.replace(rows("dac"))
    self.assertEqual([r["key"] for r in m.rows], list("dac"))
    self.assertTrue(moves and ins and rem)
    self.assertLessEqual(len(resets), 1)

def test_keyed_diff_matches_target(self):
    import random
    m, rnd = self.c._agents, random.Random(7)
    role = A.Qt.UserRole + m.keys.index("key")
    for _ in range(200):
        ks = rnd.sample("abcdefgh", rnd.randint(0, 8))
        m.replace([{"key": k, "age": str(rnd.randint(0, 2))} for k in ks])
        self.assertEqual([m.data(m.index(i), role) for i in range(m.rowCount())], ks)
```

(`A.Qt` is imported in app.py; if not exposed, import `Qt` from `PySide6.QtCore` in the test.)

- [ ] **Step 2: Run** `python3 -m unittest discover -s agents/tests -t agents -k reorder -k keyed_diff`
Expected: FAIL, `resets` grows on every reorder.

- [ ] **Step 3: Implement** the keyed path of `replace`: remove gone keys from the bottom up, then walk the target; at index `i` keep and `dataChanged` a matching row, move a later row up with `beginMoveRows(QModelIndex(), j, j, QModelIndex(), i)` (j > i, so the destination is `i`), or insert. Keep the early `rows == self.rows` return and the reset path for unkeyed rows.

- [ ] **Step 4: Run the full suite.** Expected: all pass, `test_same_rows_update_in_place` included.

- [ ] **Step 5: Commit** `fix(agents): move and insert agent rows instead of resetting the model`

### Task 2: Tile data, selected index and drafts in the controller

**Files:**
- Modify: `agents/haltos_agents/app.py`
- Test: `agents/tests/test_app.py`

**Interfaces:**
- Consumes: `read_feed(path, limit, tail_bytes)`, `pending_question(path, waiting, tail_bytes)`, `find_transcript(sid)` from `transcript.py` (via the `A.` module names so tests can patch them).
- Produces:
  - constants `TILE_LINES = 6`, `TILE_BYTES = 128_000`
  - agents roles gain `"project"` (str, `Path(cwd).name`), `"tail"` (list of `{"kind","body","name","added","removed","error"}`), `"question"` (`{}` or `{"text": str, "options": [str]}`)
  - `Controller._read_tiles(sessions: list[Session]) -> None`, called from `_poll`; caches per key on `(path, mtime, status)`
  - `@Property(int, notify=changed) selectedIndex`: row index of the selected key, `-1` when none
  - `@Slot(str, result=str) draft(key)`, `@Slot(str, str) setDraft(key, text)`; drafts of agents gone from a poll are dropped
  - `_item(i: FeedItem) -> dict` shared by `_load_feed` and `_read_tiles`

- [ ] **Step 1: Write the failing tests:**

```python
def _transcript(self, *rows):
    path = os.path.join(tempfile.mkdtemp(), "s.jsonl")
    with open(path, "w") as f:
        f.write("".join(json.dumps(r) + "\n" for r in rows))
    return Path(path)

def test_tiles_reread_only_on_change(self):
    path = self._transcript({"type": "user", "message": {"content": "fix login"}})
    calls = []
    orig_find, orig_read = A.find_transcript, A.read_feed
    A.find_transcript = lambda sid: path
    A.read_feed = lambda *a, **k: calls.append(1) or orig_read(*a, **k)
    try:
        busy = Session("a", "s", "a", "/tmp/kahvefalin", "background", "", "busy", 0.0, True)
        self.c._read_tiles([busy])
        self.c._read_tiles([busy])
        self.assertEqual(len(calls), 1)
        self.c._read_tiles([busy._replace(status="waiting")])
        self.assertEqual(len(calls), 2)
        self.c._on_polled([busy], "")
    finally:
        A.find_transcript, A.read_feed = orig_find, orig_read
    row = self.c._agents.rows[0]
    self.assertEqual(row["project"], "kahvefalin")
    self.assertEqual(row["tail"][-1]["kind"], "prompt")
    self.assertEqual(row["tail"][-1]["body"], "fix login")

def test_waiting_tile_has_question(self):
    path = self._transcript({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "git push"}}]}})
    orig, A.find_transcript = A.find_transcript, lambda sid: path
    try:
        s = Session("a", "s", "a", "/tmp", "background", "", "waiting", 0.0, True)
        self.c._read_tiles([s])
        self.c._on_polled([s], "")
    finally:
        A.find_transcript = orig
    self.assertEqual(self.c._agents.rows[0]["question"]["options"], ["İzin ver", "Reddet"])

def test_tile_without_transcript_is_empty(self):
    orig = A.find_transcript
    try:
        for found in (None, Path("/nonexistent/s.jsonl")):
            A.find_transcript = lambda sid: found
            self.c._read_tiles([session("a")])
            self.c._on_polled([session("a")], "")
            self.assertEqual((self.c._agents.rows[0]["tail"], self.c._agents.rows[0]["question"]), ([], {}))
    finally:
        A.find_transcript = orig

def test_selected_index(self):
    self.assertEqual(self.c.selectedIndex, -1)
    self.c._on_polled([session("a"), session("b")], "")
    self.c.select("b")
    self.assertEqual(self.c.selectedIndex, 1)

def test_drafts_kept_per_agent(self):
    self.c._on_polled([session("a"), session("b")], "")
    self.c.setDraft("a", "half typed")
    self.assertEqual((self.c.draft("a"), self.c.draft("b")), ("half typed", ""))
    self.c._on_polled([session("b")], "")
    self.assertEqual(self.c.draft("a"), "")
```

Add `import json` to the test imports. If `Session` is not a namedtuple, build the waiting copy with the constructor instead of `_replace`.

- [ ] **Step 2: Run** the five tests. Expected: FAIL (`_read_tiles`, `selectedIndex`, `draft` missing).

- [ ] **Step 3: Implement** the Produces list. `_read_tiles` builds a fresh dict and assigns it to `self._tiles` in one statement (it runs on the worker thread; `_on_polled` reads it on the UI thread). A missing path or an `OSError` on `stat` gives `([], {})`. `_row` reads `self._tiles.get(s.key)`.

- [ ] **Step 4: Run the full suite.** Update `test_rows_carry_age_and_feed_roles` to also assert `"tail"`, `"question"` and `"project"` are roles. Expected: all pass.

- [ ] **Step 5: Commit** `feat(agents): read a short tail and question for every agent`

### Task 3: Grid of tiles replaces the list

**Files:**
- Create: `agents/qml/AgentTile.qml`, `agents/qml/AgentGrid.qml`
- Delete: `agents/qml/AgentList.qml`
- Modify: `agents/qml/Main.qml`, `agents/qml/Ansi.qml`, `agents/qml/AgentDetail.qml`, `agents/qml/KeyBar.qml`, `agents/qml/qmldir`
- Test: `agents/tests/test_app.py`

**Interfaces:**
- Consumes: Task 2 roles, `selectedIndex`, `draft`/`setDraft`; existing `select`, `send`, `answer`, `interrupt`, `archive`, `kill`, `step`.
- Produces:
  - `Ansi.esc(s)`, `Ansi.paint(color, s)`, `Ansi.line(item)` (StyledText for one feed item, same format as today's feed delegate). AgentDetail's helpers move here.
  - `AgentGrid` (objectName `"agentGrid"`): `required property QtObject controller`, `readonly property int columns` = `Math.max(1, Math.floor(width / (Kirigami.Units.gridUnit * 22)))`, `function focusSelected()`, `signal zoomRequested()`. A GridView with `cellWidth: width / columns`, `cellHeight: Kirigami.Units.gridUnit * 10`, `currentIndex` bound to `controller.selectedIndex` and kept in view, horizontal scrolling off, empty state `henüz ajan yok · ctrl+n yeni`. Owns the stop confirmation dialog for tiles.
  - `AgentTile` (objectName `"agentTile"`): `property string agentKey`, `function focusInput()`, `function choose(index)` (select, then `answer(index)`), `function act(fn)` (select when not selected, then `fn()`). Header: glyph, name, dim project, `tty`, age, `⋮` (arşivle when done, durdur… via the grid's dialog). Blue border when selected, `opacity: 0.55` when done. Body: the tail lines bottom-aligned and clipped at the top, then `? text` and `[n] option` NoFocus buttons when `question.text` exists. `>` line with a TextArea (objectName `"tileInput"`): text loaded from `controller.draft(agentKey)` on creation, `onTextChanged` calls `setDraft`; gaining focus selects the agent; Enter sends through `act`, Shift+Enter newline, Esc interrupts through `act`; disabled with `bu oturum bir terminalde açık` when not attachable. Double click on the header emits the grid's `zoomRequested`.
  - `Main.qml`: top bar row with `Kirigami.SearchField` (objectName `"searchField"`, Esc clears, `search("")`, `focusInput()`) and `+` (NoFocus, opens the dialog). Below it: `SearchResults` when `controller.query !== ""`, else `AgentGrid`. `function focusInput()` focuses the selected tile. `trigger` actions: `interrupt`, `new`, `search`, `terminal`, `prev` (`step(-1)`), `next` (`step(1)`), `up` (`step(-agentGrid.columns)`), `down` (`step(agentGrid.columns)`); the last four call `focusInput()` after. Shortcuts `Alt+Left` prev, `Alt+Right` next, `Alt+Up` up, `Alt+Down` down.
  - KeyBar grid entries: `next` "alt+←↑↓→ geç", `interrupt` "esc kes", `new` "ctrl+n yeni", `search` "ctrl+f ara", `terminal` "ctrl+t terminal" (Task 4 adds the zoom entry and the zoom set).

- [ ] **Step 1: Write the failing tests** in a new `GridTest` class with a `_load(hidden)` helper (engine, controller with stubbed pool, root) and `tiles(grid)` = `[i for i in grid.property("contentItem").childItems() if i.objectName() == "agentTile"]` after a 200 ms event loop wait:
  - `test_grid_shows_every_agent`: poll three sessions; `agentGrid.count == 3`; no item named `"agentList"` exists.
  - `test_poll_does_not_move_focus`: today's test, with "next" now focusing the `tileInput` whose tile `agentKey == c.selectedKey`.
  - `test_focus_and_draft_survive_new_agent`: poll `[a]`, focus a's `tileInput`, set its `text` to `"hello"`; poll a newer session `b` (`started_at=1.0`, sorts first) plus `a`; a's input still has active focus and `"hello"`, and `c.draft("a") == "hello"`.
  - `test_unselected_tile_acts_on_its_agent`: patch `A.find_transcript` to a temp file and `A.pending_question` to return `Question("q", [("Evet", b"1")])`; record `c._selected` inside a patched `c._act`; select `a`, call `choose(0)` on b's tile via `QMetaObject.invokeMethod`; recorded key is `"b"`.
  - `test_alt_arrows_move_by_rows_and_clamp`: five sessions, select the first, `trigger("down")` gives `selectedIndex == min(columns, 4)`; three more `down` stay at 4; `up` from 4 gives `max(0, 4 - columns)`.
  - `test_narrow_window_has_one_column`: set root `width` to its `minimumWidth`, wait; `columns == 1`.
  - Rewrite `test_terminal_ui` key expectations to the grid set above.
- [ ] **Step 2: Run** them. Expected: FAIL (no `agentGrid`).
- [ ] **Step 3: Implement** the Produces list. Delete `AgentList.qml` and its qmldir line; add `AgentTile` and `AgentGrid`. AgentDetail stays in the tree but hidden until Task 4 (keep its `objectName "agentInput"` input).
- [ ] **Step 4: Run the full suite.** Expected: all pass, no QML warnings in the output other than the known NewAgentDialog binding loop.
- [ ] **Step 5: Offscreen screenshot** with the scratchpad `shot.py` (live agents) and compare with mockup A.
- [ ] **Step 6: Commit** `feat(agents): show every agent as a tile in a grid`

### Task 4: Zoom into the detail view

**Files:**
- Modify: `agents/qml/Main.qml`, `agents/qml/AgentDetail.qml`, `agents/qml/KeyBar.qml`, `agents/qml/AgentGrid.qml`
- Modify: `docs/testing.md`, `Readme.md`
- Test: `agents/tests/test_app.py`

**Interfaces:**
- Consumes: Task 3 `AgentGrid`, `focusInput()`, `trigger`.
- Produces:
  - `Main.qml` `property bool zoomed: false`; `trigger("zoom")` toggles it and calls `focusInput()`; shortcut `Ctrl+O`. With `zoomed`, the view under the top bar is `AgentDetail`, otherwise `AgentGrid`; a non-empty query still shows `SearchResults` and clearing it returns to the same mode. In zoom, `up`/`down` step by 1. `focusInput()` focuses `agentDetail` when zoomed. `AgentGrid.zoomRequested` triggers `zoom`.
  - `AgentDetail`: `signal back()`, header `← grid` ToolButton (objectName `"backButton"`, NoFocus) emitting it, wired to `trigger("zoom")`. Its input loads `controller.draft(selectedKey)` when the selection changes or the view becomes visible and calls `setDraft` on text change; tiles reload their draft when the grid becomes visible.
  - KeyBar `property bool zoomed`; grid entries in order: `next` "alt+←↑↓→ geç", `zoom` "ctrl+o büyüt", `interrupt` "esc kes", `new` "ctrl+n yeni", `search` "ctrl+f ara", `terminal` "ctrl+t terminal"; zoom entries: `zoom` "ctrl+o grid", `next` "alt+←→ önceki/sonraki", `interrupt` "esc kes", `new` "ctrl+n yeni", `terminal` "ctrl+t terminal".

- [ ] **Step 1: Write the failing tests** in `GridTest`:
  - `test_zoom_toggles_view_and_keys`: grid key set as above; `trigger("zoom")` makes AgentDetail visible, the grid hidden and the key bar show the zoom set; `backButton` exists; `trigger("zoom")` restores both.
  - `test_zoom_shares_draft`: tile a input `"abc"`; zoom; `agentInput.text == "abc"`; set it to `"abcd"`; unzoom; a's tile input is `"abcd"`.
  - `test_zoom_arrows_step_by_one`: five sessions, zoomed, `trigger("down")` moves `selectedIndex` by exactly 1.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement** the Produces list.
- [ ] **Step 4: Docs.** `docs/testing.md`: replace the shortcuts line with the grid and zoom keys, add a check that typing in a tile survives a new agent appearing and that Ctrl+O opens and closes the full view. `Readme.md` Agents line: "a native, terminal-style grid of Claude Code's background agents" and mention Ctrl+O for the full view.
- [ ] **Step 5: Run the full suite** and an offscreen screenshot of the zoomed view. Expected: all pass.
- [ ] **Step 6: Commit** `feat(agents): zoom a tile into the full agent view with ctrl+o`
