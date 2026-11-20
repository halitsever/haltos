# HaltOS Agents Spotlight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the equal-tile grid into a spotlight grid with GEZİN/YAZ keyboard modes, HaltMono looks everywhere, counters, spinner, help overlay and an empty state.

**Architecture:**
- **Layout.** A pure Python module `layout.py` packs tiles into grid cells and finds the neighbour above or below. It needs no Qt, so CI tests it too.
- **Controller.** It exposes the packing and a direction move as slots, plus a `counts` property.
- **QML.** `AgentGrid` becomes a Flickable with a Repeater whose tiles sit at the packed rects and slide there. Only the spotlight tile has an input.
- **Mode.** The mode is derived from focus: YAZ while a text input has active focus, GEZİN otherwise. A `navigator` item holds focus in GEZİN and handles the letter keys.

**Tech Stack:** Kirigami 6 / QtQuick, PySide6 from apt, unittest.

**Spec:** `docs/superpowers/specs/2026-11-19-haltos-agents-spotlight-design.md`

## Global Constraints

- No new packages. Only `agents/` is installed, so every asset lives under `agents/`.
- HaltMono palette:
  - background `#09090b`
  - surface `#18181b`
  - text `#fafafa`
  - faint `#a1a1aa`
  - accent `#3b82f6`
  - ANSI colours stay as in `Ansi.qml`.
- Font: `JetBrains Mono` when `Qt.fontFamilies()` has it, else `Kirigami.Theme.fixedWidthFont`.
- Animation lengths are `Kirigami.Units.longDuration` (slides) or `shortDuration`. Keys act on the current layout at once; animations never gate input.
- Polls never move focus, change the mode, or move the spotlight unless the selected agent is gone. Drafts stay per agent. Controller actions act on the selected agent.
- Mode badge text: `GEZİN` / `YAZ`.
- Key bar text (each entry with an action stays a NoFocus flat button; entries without one are plain labels):
  - **GEZİN, grid:** `wasd seç`, `enter yaz`, `1-9 cevapla`, `o büyüt`, `x kes`, `n yeni`, `/ ara`, `? tuşlar`.
  - **GEZİN, zoom:** `a d önceki/sonraki`, `enter yaz`, `1-9 cevapla`, `esc grid`, `x kes`, `t terminal`.
  - **YAZ:** `enter gönder`, `shift+enter satır`, `esc gezin`.
- Copy:
  - counters: `N seni bekliyor`, `N çalışıyor`, `N bitti` (a zero counter is hidden)
  - empty state: `henüz ajan yok` and `n yeni ajan`
  - tty hint: `bu oturum bir terminalde açık`
- Comments: short English, why not what, no em dashes and no ` -- `. Commits: conventional subject line only.
- Test command: `python3 -m unittest discover -s agents/tests -t agents` from the repo root.

## Review Focus

1. **Spotlight agent disappears while YAZ has focus** (archived, exited): focus falls back to GEZİN on the new spotlight and nothing is lost but that agent's tile (Task 4 test).
2. **Letter key while the search field, the new agent dialog or the stop dialog has focus:** the letter is typed there, and no GEZİN command fires (Task 4 test).
3. **`w`/`s` on the top or bottom row, or with tiles of mixed size above:** clamps, and picks the tile nearest by centre (Task 1 test).
4. **More agents than fit, spotlight moved to the last row:** the view scrolls so the whole spotlight is visible (Task 3 test).
5. **Window narrower than two small tiles:** one column, the spotlight one column wide and `bigRows` tall, no horizontal scroll (Task 1 and Task 3 tests).

---

### Task 1: Packing, direction moves and counts

**Files:**
- Create: `agents/haltos_agents/layout.py`
- Create: `agents/tests/test_layout.py`
- Modify: `agents/haltos_agents/app.py` (`TILE_LINES`, `Controller.moveRow` goes, `go`, `pack`, `counts`)
- Test: `agents/tests/test_app.py`

**Interfaces:**
- Produces: `layout.pack(n: int, sel: int, cols: int, big_rows: int) -> list[tuple[int, int, int, int]]`.
  - It returns one `(col, row, w, h)` per tile, in order.
  - The spotlight is `sel` (-1 for none). It is `min(2, cols)` wide and `max(2, big_rows)` tall. Every other tile is 1 by 1.
  - Each tile goes in the first free cell block, scanning row by row and then by column.
- Produces: `layout.neighbour(rects, here: int, direction: str) -> int`, where `direction` is `"up"` or `"down"`.
  - **down:** candidates have `row >= here.row + here.h`. Pick the smallest `row`, then the smallest `|centre x - here centre x|`, then the lowest index.
  - **up:** candidates have `row + h <= here.row`. Pick the largest `row + h`, then the same tie-breaks.
  - With no candidate it returns `here`.
- Produces: `Controller.pack(columns: int, bigRows: int) -> list` (Slot). It returns `[[col, row, w, h], ...]` for the current rows and selection.
- Produces: `Controller.go(direction: str, columns: int, bigRows: int)` (Slot).
  - `"left"`/`"right"` call `step(-1)`/`step(1)`, which already clamps.
  - `"up"`/`"down"` select `rows[neighbour(pack(...), here, direction)]`.
  - `moveRow` is removed.
- Produces: `Controller.counts` (`QVariantMap`, notify `changed`): `{"need": int, "work": int, "done": int}` over the shown rows.
- Produces: `TILE_LINES = 16`.

- [ ] **Step 1: Write the failing tests** in `agents/tests/test_layout.py`, plain `unittest`, no Qt:

```python
from haltos_agents.layout import neighbour, pack

def test_spotlight_takes_two_by_two_at_its_turn(self):
    self.assertEqual(pack(5, 1, 3, 2), [(0, 0, 1, 1), (1, 0, 2, 2), (0, 1, 1, 1), (0, 2, 1, 1), (1, 2, 1, 1)])

def test_spotlight_after_a_full_row(self):
    self.assertEqual(pack(4, 3, 3, 2), [(0, 0, 1, 1), (1, 0, 1, 1), (2, 0, 1, 1), (0, 1, 2, 2)])

def test_two_columns_spotlight_spans_both(self):
    self.assertEqual(pack(3, 0, 2, 3), [(0, 0, 2, 3), (0, 3, 1, 1), (1, 3, 1, 1)])

def test_one_column(self):
    self.assertEqual(pack(2, 1, 1, 2), [(0, 0, 1, 1), (0, 1, 1, 2)])

def test_no_selection_is_all_small(self):
    self.assertEqual(pack(2, -1, 3, 2), [(0, 0, 1, 1), (1, 0, 1, 1)])

# pack(6, 1, 3, 2) == [(0,0,1,1), (1,0,2,2), (0,1,1,1), (0,2,1,1), (1,2,1,1), (2,2,1,1)]
def test_down_picks_nearest_centre_below(self):
    rects = pack(6, 1, 3, 2)
    self.assertEqual(neighbour(rects, 1, "down"), 4)  # tiles 4 and 5 tie on |dx|, lower index wins
    self.assertEqual(neighbour(rects, 0, "down"), 2)

def test_up_prefers_nearest_bottom_edge_then_centre(self):
    self.assertEqual(neighbour(pack(6, 1, 3, 2), 4, "up"), 1)

def test_up_and_down_clamp(self):
    rects = pack(3, 0, 3, 2)
    self.assertEqual(neighbour(rects, 0, "up"), 0)
    self.assertEqual(neighbour(rects, 2, "down"), 2)
```

Also add `ControllerTest.test_counts_and_go`:
- poll rows need `a`, work `b`, done `c`, done `d`
- assert `counts == {"need": 1, "work": 1, "done": 2}`
- `select("a")`, then `go("down", 3, 2)` selects `"d"`, since `pack(4, 0, 3, 2)` puts only tile 3 below the spotlight
- `go("right", 3, 2)` from `"d"` stays on `"d"` (last row), and `go("left", 3, 2)` selects `"c"`
- `hasattr(c, "moveRow")` is false

- [ ] **Step 2: Run them:** `python3 -m unittest discover -s agents/tests -t agents -k test_layout -k test_counts_and_go`. Expected: errors on the missing module and attributes.
- [ ] **Step 3: Implement** `layout.py` (occupancy set of `(col, row)`, first fit, row-major), then the controller slots and the property, and set `TILE_LINES = 16`. Remove `moveRow` and its uses (`Main.qml` `up`/`down` call `go` from Task 4. Until then, point them at `go("up"/"down", agentGrid.columns, 2)`).
- [ ] **Step 4: Run the whole suite.** Expected: green, apart from the GridTest tests that assert the old Alt row moves. Those are rewritten in Task 3 and Task 4, so record a ruling if any fail now.
- [ ] **Step 5: Commit** `feat(agents): pack a spotlight grid and move by direction`.

### Task 2: HaltMono everywhere and the top bar

**Files:**
- Create: `agents/qml/haltos-mark.svg` (copy of `branding/haltos-logo.svg`)
- Create: `agents/haltos_agents/HaltMono.colors` (copy of `plasma/color-schemes/HaltMono.colors`)
- Modify: `agents/haltos_agents/app.py` (`run`), `agents/qml/Main.qml`, `agents/qml/Ansi.qml`
- Test: `agents/tests/test_app.py`

**Interfaces:**
- Produces: `Ansi` gains the palette:
  - `bg` `#09090b`
  - `surface` `#18181b`
  - `text` `#fafafa`
  - `faint` `#a1a1aa`
  - `line` (text at 0.12 alpha)
  - `accent` (`#3b82f6`)
- Produces: the root window's `color` is `Ansi.bg`. The root sets `Kirigami.Theme.inherit: false` with:
  - `backgroundColor`, `textColor`, `disabledTextColor`, `highlightColor` and `alternateBackgroundColor` from that palette
  - `Kirigami.Theme.colorSet: Kirigami.Theme.View`
- Produces: `run()` sets `app.setProperty("KDE_COLOR_SCHEME_PATH", <HaltMono.colors path>)` before the engine loads. This is so dialogs, menus and the KDE style draw in HaltMono on Plasma.
- Produces: the top bar has these objectNames:
  - `brand`: the mark image and `agents`
  - `counter:need`, `counter:work`, `counter:done`: Labels with the copy above, `visible` only when the count is above 0
  - `searchField`
  - `+`

- [ ] **Step 1: Write the failing tests** in a new `ThemeTest` (same setup as `GridTest`, so reuse its helpers by moving them into a base class `QmlCase`):
  - `test_window_is_haltmono`: `root.property("color")` equals `QColor("#09090b")`. The root font family is `"JetBrains Mono"` when `QFontDatabase.families()` has it.
  - `test_counters`:
    - Poll need `a`, work `b` and `c`. `counter:need` text is `"1 seni bekliyor"`, `counter:work` text is `"2 çalışıyor"`, `counter:done` is not visible.
    - Poll none. `findChild(QQuickItem, "emptyState")` is visible.
- [ ] **Step 2: Run** `... -k ThemeTest`. Expected: FAIL (wrong colour, missing objects).
- [ ] **Step 3: Implement** the palette and theme overrides, the scheme property in `run()`, the font choice and the top bar. The empty state lives in `AgentGrid` (objectName `emptyState`): a 64 px mark, `henüz ajan yok`, and `n yeni ajan` in faint text. Replace the separator under the top bar with a 1 px `Ansi.line` rectangle.
- [ ] **Step 4: Run the suite** and take a screenshot with the scratchpad `shot.py`, under the current light desktop theme. Expected: green, and the window, dialogs and search field render dark. If a Kirigami dialog stays light, give it the same `Kirigami.Theme` overrides and record a ruling.
- [ ] **Step 5: Commit** `feat(agents): draw the app in HaltMono with counters in the top bar`.

### Task 3: Spotlight grid

**Files:**
- Modify: `agents/qml/AgentGrid.qml` (rewrite), `agents/qml/AgentTile.qml`
- Test: `agents/tests/test_app.py` (`GridTest` rewritten)

**Interfaces:**
- Consumes: `Controller.pack(columns, bigRows)`, `selectedIndex`, `counts`, roles `tail`/`question`.
- Produces: `AgentGrid`:
  - `readonly property int columns`: `max(1, floor(width / (gridUnit * 16)))`
  - `readonly property int bigRows`: `max(2, round(visible height / 2 / cellHeight))`
  - `cellHeight`: `gridUnit * 5`
  - `function focusSelected()`: focuses the spotlight's input
  - `function spotlight(): Item`
  - `signal zoomRequested()`
  - inner Flickable objectName `agentGrid`, with a `count` property for the tile count
  - tiles are Repeater delegates at `x/y/width/height` from `pack`, with `Behavior` on all four
  - when the selection or layout changes, `contentY` is clamped so the spotlight rect is fully visible
  - a single `Timer` drives `property int frame` for the spinner, running only while `counts.work > 0` and the grid is visible
- Produces: `AgentTile`:
  - `property bool big`
  - `property int frame`
  - small tiles show the header plus the last 2 tail lines, or `? question` on one line
  - big tiles show up to all tail lines that fit, the question with `[n]` buttons, and the `tileInput` (`visible: big`)
  - left rail 3 px: `Ansi.yellow` need, `Ansi.accent` work, `Ansi.line` done
  - header glyph:
    - work: braille spinner `"⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"[frame % 10]`
    - need: `!`
    - done: `✓`
  - the big tile has an `Ansi.accent` border and a glow (`Kirigami.ShadowedRectangle` shadow with the accent at 0.35 alpha, size `gridUnit`)
  - when `group` changes to `need` from something else, the rail pulses once (opacity 1 → 0.3 → 1, two `longDuration` steps)
  - a click selects, and a double click emits `zoomRequested`
  - the draft loads when `big` becomes true

- [ ] **Step 1: Rewrite `GridTest`** for the spotlight. Its helpers find tiles among the Flickable's `contentItem` children.
  - `test_spotlight_follows_selection`: poll `a b c`. Tile `a` is `big`, the others are not. `select("c")` makes `c` big and `a` small.
  - `test_tiles_sit_where_pack_says`: after the slide (`wait(500)`), each tile's `x`/`y` equals `rect.col * cellWidth` / `rect.row * cellHeight`, from `c.pack(columns, bigRows)`.
  - `test_only_spotlight_has_input`: a small tile's `tileInput` is not visible.
  - `test_draft_follows_spotlight`:
    - Type into `a`'s input, then select `b` and back to `a`.
    - The text is back and the cursor is at the end.
  - `test_poll_reorder_keeps_spotlight`: select `b` (done). A poll turns `b` into need, which moves it first. `b` is still big and `selectedKey == "b"`.
  - `test_spotlight_scrolled_into_view` (Review Focus 4):
    - 30 agents, window height `gridUnit * 30`.
    - Select the last one. Its tile rect lies within `[contentY, contentY + height]`.
  - `test_narrow_window_one_column` (Review Focus 5):
    - Width at minimum.
    - `columns == 1`, and the big tile's width equals the grid width.
  - `test_spinner_only_while_working`: the timer's `running` is true with a work agent and false without one.
- [ ] **Step 2: Run** `... -k GridTest`. Expected: FAIL on the missing `big`/`pack` positions.
- [ ] **Step 3: Implement** `AgentGrid`, then `AgentTile`. Keep the `act()` / `choose()` / `loadDraft()` helpers and the stop dialog's captured target. In the delegate, compute the tile's rect as `grid.rects[index]`, where `rects` is `controller.pack(columns, bigRows)`, re-read on `controller.changed` and on the `columns`/`bigRows` changes.
- [ ] **Step 4: Run the suite and take a screenshot.** Expected: green. The screenshot shows mockup C: the spotlight two columns wide with a glow, small tiles around it, and the rails.
- [ ] **Step 5: Commit** `feat(agents): show the selected agent in a spotlight tile`.

### Task 4: GEZİN and YAZ

**Files:**
- Create: `agents/qml/HelpOverlay.qml` (add to `qmldir`)
- Modify: `agents/qml/Main.qml`, `agents/qml/KeyBar.qml`, `agents/qml/AgentTile.qml`, `agents/qml/AgentDetail.qml`, `docs/testing.md`, `Readme.md`
- Test: `agents/tests/test_app.py`

**Interfaces:**
- Produces: `Main.qml`:
  - `readonly property bool typing`: true while `activeFocusItem` has a `cursorPosition` property (TextEdit, TextInput)
  - `function navigate()`: forces focus to the `navigator` Item (objectName `navigator`)
  - `trigger(action)` gains `"type"`, `"help"`, `"answer:N"` (0-based) and `"up"`/`"down"`/`"left"`/`"right"`, which call `controller.go(..., agentGrid.columns, agentGrid.bigRows)` in the grid
  - in zoom, `left`/`right` step, and `up`/`down` step too
- Produces: navigator `Keys.onPressed`, only reached when no text input has focus. It handles:
  - `w a s d`, `h j k l` and arrows: directions
  - Enter, Return and `i`: type
  - `1`-`9`: answer
  - `o` and Space: zoom
  - `x`: interrupt
  - `n`: new
  - `/`: search
  - `t`: terminal
  - `?`: help
  - Esc: help overlay open → close; zoom → grid; otherwise accepted, no-op

  Unmodified keys only. Ctrl shortcuts stay as `Shortcut`s. Alt+arrows stay `Shortcut`s that move and keep the mode: after a move in YAZ, call `focusInput()`.
- Produces: in the tile and detail inputs, Esc calls `root.navigate()` (via a signal `escaped()` on `AgentTile`/`AgentDetail`) and no longer interrupts.
- Produces: `type` on a non-attachable spotlight shows the tty hint as a `QQC2.ToolTip` on the spotlight for 2 s and stays in GEZİN.
- Produces: GEZİN is the landing mode. Startup (first agent), `onShowRequested`, SearchResults `onPicked`, NewAgentDialog close and a search Esc all call `navigate()` instead of `focusInput()`.
- Produces: when `activeFocusItem` becomes null while the window is active, `navigate()` runs. This covers the spotlight tile dying with focus in it.
- Produces: `KeyBar`:
  - `property bool typing` and `property bool zoomed`
  - a mode badge (objectName `modeBadge`, text `GEZİN` on `Ansi.accent` / `YAZ` on `Ansi.green`, `Ansi.bg` text)
  - the three entry lists from Global Constraints. Entry actions: `wasd seç` none, `enter yaz` type, `1-9 cevapla` none, `o büyüt` zoom, `x kes` interrupt, `n yeni` new, `/ ara` search, `? tuşlar` help, `a d önceki/sonraki` next, `esc grid` zoom, `t terminal` terminal, YAZ entries none.
- Produces: `HelpOverlay` (objectName `helpOverlay`):
  - a centred `Ansi.surface` card listing every key from the spec's table, in two columns
  - `open` toggled by `help`
  - a click outside closes it

- [ ] **Step 1: Write the failing tests** (new `KeysTest`, on `QmlCase`). Send keys with `QTest.keyClick(window, key)` from `PySide6.QtTest`, after `root.requestActivate()` and a wait.
  - `test_starts_in_gezin`: after the first poll, `navigator.hasActiveFocus()` is true, `typing` is false, and `modeBadge` text is `GEZİN`.
  - `test_wasd_moves_spotlight`: three agents. `d` selects the second, `a` selects the first, and `s` selects what `go("down")` would.
  - `test_enter_types_and_esc_returns`:
    - Enter: the spotlight `tileInput` has focus and the badge says `YAZ`.
    - Typing `w` changes the text, not the selection.
    - Esc: the navigator has focus and the draft is kept.
  - `test_number_answers`: a need agent with a question. Patch `c.answer` to record calls. `2` records `1`.
  - `test_x_interrupts_esc_does_not`: patch `c.interrupt`. Esc in YAZ does not call it. `x` in GEZİN does.
  - `test_letters_go_to_search_and_dialog` (Review Focus 2):
    - Focus the search field and type `x`. The search text is `"x"` and interrupt is not called.
    - Open the new agent dialog and press `n`. It does not open twice, and no command fires.
  - `test_focus_falls_back_when_spotlight_vanishes` (Review Focus 1): YAZ on `a`, then a poll without `a`. The navigator has focus and `b` is the spotlight.
  - `test_zoom_keys`: `o` zooms. `d` steps to the next agent. Esc returns to the grid.
  - `test_help_overlay`: `?` opens it, and Esc closes it.
  - `test_tty_enter_stays_gezin`: an unattachable spotlight. Enter leaves the navigator focused.
  - Update `BannerTest.test_terminal_ui` to the new key bar text.
- [ ] **Step 2: Run** `... -k KeysTest -k BannerTest`. Expected: FAIL.
- [ ] **Step 3: Implement** in the interface order above. Remove the old `placedFocus` startup rule in favour of `navigate()` on the first agent, unless the new agent dialog is open or the search has focus.
- [ ] **Step 4: Run the suite and take screenshots** of GEZİN with the help overlay, and of YAZ. Expected: green.
- [ ] **Step 5: Update docs.**
  - `docs/testing.md`: the agents checks use the new keys: WASD, Enter/Esc, `1`-`9`, `x`, `?`, the dark theme under a light desktop, and the spotlight.
  - `Readme.md`, Agents line: "a native, keyboard-driven grid of Claude Code's background agents: the selected agent opens in a spotlight tile, WASD moves between them, number keys answer their questions…" Keep the rest of the line.
- [ ] **Step 6: Commit** `feat(agents): drive the grid from the keyboard with GEZİN and YAZ modes`.
