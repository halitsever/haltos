# HaltOS Agents Grouped Grid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the spotlight grid and NAV/TYPE modes with a status-grouped grid of equal tiles and a Claude Code style agent screen.

**Architecture:**
- **Layout.** The Qt-free `layout.py` places tiles by group, each group starting on a fresh row, and keeps `neighbour` for up/down moves.
- **Controller.** It exposes the placed rects and the section headers to QML. A notification click asks QML to open that agent.
- **QML.** There are two screens with no hidden modes. The grid has no text input, so a `navigator` item takes the keys. The agent screen's input always holds focus while that screen is open.

**Tech Stack:** Kirigami 6 / QtQuick, PySide6 from apt, unittest.

**Spec:** `docs/superpowers/specs/2026-11-19-haltos-agents-grouped-design.md`

## Global Constraints

- No new packages. Only `agents/` is installed.
- Tests use no PySide6.QtTest. They send QKeyEvents through `QGuiApplication.sendEvent`.
- HaltMono colours from `Ansi`, JetBrains Mono when installed, English UI.
- Polls never move focus or the selection unless the selected agent is gone. Drafts stay per agent. Controller actions act on the selected agent.
- Section headers:
  - `● Waiting for you` (yellow)
  - `◐ Working` (accent)
  - `✓ Done` (faint)
  - Each header is followed by its count. A section with no agents is hidden.
- Hint bar:
  - **Grid:** `←↑↓→ select`, `enter open`, `1 2 answer`, `n new agent`, `/ search`, `? keys`.
  - **Agent screen:** `enter send`, `shift+enter new line`, `1 2 answer`, `ctrl+k interrupt`, `esc back`.
- Copy:
  - `+ New agent`
  - `← Back`
  - `■ Interrupt`
  - `Message <name>…`
  - `No agents yet`
- Comments: short English, why not what, no em dashes, no ` -- `. Commits: conventional subject only.
- Test command: `python3 -m unittest discover -s agents/tests -t agents` from the repo root.

## Review Focus

1. **The selected agent disappears while its agent screen is open:** back to the grid with focus on the navigator, and the draft is kept (Task 3 test).
2. **Digits on the agent screen with text in the input:** they are typed and nothing is answered (Task 3 test).
3. **Up/down across a section boundary with a short row above:** picks the nearest tile by centre and clamps at the top and bottom (Task 1 test).
4. **More tiles than fit, selection moved to the last row:** the grid scrolls it into view, and a poll does not undo a user's scroll (Task 2 test).
5. **A letter key while search or a dialog has focus:** it is typed there and fires no grid command (Task 3 test).

---

### Task 1: Grouped layout, moves and the open request

**Files:**
- Modify: `agents/haltos_agents/layout.py` (`pack` goes, `grouped` comes, `neighbour` stays)
- Modify: `agents/haltos_agents/app.py` (`pack`/`go`/notification click)
- Test: `agents/tests/test_layout.py`, `agents/tests/test_app.py`

**Interfaces:**
- Produces: `layout.grouped(groups: list[str], cols: int) -> list[tuple[int, int, int, int]]`.
  - It returns one `(col, row, 1, 1)` per tile.
  - Tiles fill rows left to right.
  - A tile whose group differs from the previous tile's starts a new row.
- Produces: `layout.sections(groups: list[str], cols: int) -> list[tuple[str, int, int]]`. It returns `(group, count, first_row)` per group, in order.
- Produces: `Controller.tiles(columns: int) -> list` (Slot). It returns `[[col, row], ...]` for the current rows.
- Produces: `Controller.sections(columns: int) -> list` (Slot). It returns `[[group, count, first_row], ...]`.
- Produces: `Controller.go(direction: str, columns: int)`.
  - left/right step through the order.
  - up/down use `neighbour(grouped(...), here, direction)`.
  - The `bigRows` parameter and `Controller.pack` go.
- Produces: `Controller.agentRequested = Signal(str)`.
  - A notification's Open emits it after `select(key)`, in place of `showRequested`. The tray, a second launch and the local socket keep `showRequested`.
  - A launched agent (`_want`) emits it too, once it is selected.
  - `setTyping(bool)` now means "the agent screen's input has text". While it is true, `_want` waits.
  - When it turns false, `_want` resolves with `select()` only, with no `agentRequested`, so the user lands on the grid with it selected.
  - Test: `test_launched_agent_opens_unless_typing`.

- [ ] **Step 1: Write the failing tests:**
  - `grouped(["need", "need", "work", "done", "done", "done"], 2)` is `[(0,0,1,1), (1,0,1,1), (0,1,1,1), (0,2,1,1), (1,2,1,1), (0,3,1,1)]`.
  - `sections(...)` of the same input is `[("need", 2, 0), ("work", 1, 1), ("done", 3, 2)]`.
  - `neighbour(grouped(["need", "work", "work", "work"], 3), 0, "down")` is `1`: nearest by centre (0.5 vs 0.5, 1.5, 2.5).
  - `neighbour(..., 3, "up")` is `0`: one row up is the need row, and only tile 0 is there.
  - `ControllerTest.test_counts_and_go` reworked:
    - rows: need `a`; work `b`; done `c` and `d`.
    - `go("down", 3)` from `a` selects `b`, and `go("down", 3)` again selects `c`.
    - `go("up", 3)` from `c` selects `b`.
    - `go("right", 3)` from `c` selects `d`.
    - `hasattr(c, "pack")` is false.
  - `test_notification_click_requests_the_agent`: feed `read()` a `parse_action` line for a known notice id. `agentRequested` fires with the key, and `showRequested` does not.
- [ ] **Step 2: Run them.** Expected: FAIL / ImportError.
- [ ] **Step 3: Implement.** Point `Main.qml`/`AgentGrid.qml` callers of `pack`/`go` at the new signatures, so the app still loads until Task 2 replaces them.
- [ ] **Step 4: Run the suite.** Expected: green, apart from spotlight-specific GridTest/KeysTest cases. Remove those now, with a ruling, since Tasks 2 and 3 replace them.
- [ ] **Step 5: Commit** `feat(agents): lay agents out in status groups`.

### Task 2: Grouped grid screen

**Files:**
- Modify: `agents/qml/AgentGrid.qml`, `agents/qml/AgentTile.qml`, `agents/qml/Main.qml` (top bar)
- Test: `agents/tests/test_app.py` (`GridTest`, `ThemeTest`)

**Interfaces:**
- Consumes: `Controller.tiles`, `Controller.sections`, `selectedIndex`, `counts`.
- Produces: `AgentGrid`:
  - `readonly property int columns`: `max(1, floor(width / (gridUnit * 16)))`
  - `signal opened()`
  - Flickable objectName `agentGrid`, with `count`, `cellWidth`, `cellHeight` (`gridUnit * 7`) and `headerHeight` (`gridUnit * 2`)
  - **Placement:**
    - A tile's `y` is `row * cellHeight + (section index + 1) * headerHeight`.
    - A header (objectName `section:<group>`, text e.g. `● Waiting for you 2`) sits just above its first row.
    - Tiles slide with `longDuration` when a poll moves them.
  - **Scroll:** `reveal()` runs only when the selected key or its rect changes, never on a plain poll.
  - The spinner Timer runs only while `counts.work > 0` and the window is visible.
  - The empty state is `No agents yet` plus a `+ New agent` button.
- Produces: `AgentTile`:
  - no input, no `big`
  - `signal opened()`
  - Click: select, then emit `opened()`.
  - Header: a spinner for work, the name, the project in faint, the age.
  - Body: the last lines, whole lines only, then `? question` and a Flow of `N label` buttons (`1 Yes`) while asking and attachable.
  - The selected tile has an accent border. Done tiles are at 0.55 opacity.
  - Keep `act`/`choose`, the ⋮ menu and the stop dialog's captured target.
- Produces: the top bar is the mark plus `agents`, the search field, and a highlighted `+ New agent` button (objectName `newButton`). The counters go.

- [ ] **Step 1: Rewrite the grid tests:**
  - `test_sections_in_order_and_hidden_when_empty`:
    - Poll need `a`, done `b`.
    - `section:need` text is `"● Waiting for you 2"`… use counts 1/1.
    - `section:work` is not visible.
    - `section:need` y < `section:done` y.
  - `test_tiles_sit_in_their_sections`: tile y values follow the formula above for `c.tiles(columns)` and the section order.
  - `test_tiles_keep_size_on_selection`: select each agent in turn. Every tile's width and height stay equal to `cellWidth`/`cellHeight`.
  - `test_click_opens_agent`: invoke the tile's `opened` path (`QMetaObject.invokeMethod(tile, "open")`, where `open()` is a tile function doing select plus emit). The root's `agentOpen` is true and `selectedKey` is that tile's key.
  - `test_waiting_tile_shows_buttons`: with a question, the tile has a visible `answerButtons` Flow.
  - Keep `test_spotlight_scrolled_into_view` (renamed `test_selection_scrolled_into_view`), `test_poll_keeps_user_scroll`, `test_spinner_only_while_working`, `test_unselected_tile_acts_on_its_agent` and `test_stop_dialog_stops_the_agent_it_asked_about`. Point them at the new API.
  - `ThemeTest.test_counters` becomes the section header text check plus the empty state.
- [ ] **Step 2: Run** `-k GridTest -k ThemeTest`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the suite and take a screenshot.** Expected: green. The screenshot matches mockup screen 1.
- [ ] **Step 5: Commit** `feat(agents): group the grid by status with equal tiles`.

### Task 3: Agent screen and keys

**Files:**
- Modify: `agents/qml/Main.qml`, `agents/qml/AgentDetail.qml`, `agents/qml/KeyBar.qml`, `agents/qml/HelpOverlay.qml`, `docs/testing.md`, `Readme.md`
- Test: `agents/tests/test_app.py` (`KeysTest`, `BannerTest`)

**Interfaces:**
- Produces: `Main.qml`:
  - `property bool agentOpen`
  - `function openAgent()`: shows the agent screen and focuses its input
  - `function back()`: grid, then `navigate()`
  - `function navigate()`
  - `trigger(action)` with `open`, `back`, `prev`, `next`, `up`, `down`, `answer:N`, `new`, `search`, `terminal`, `interrupt`, `help`, `escape`
  - `controller.setTyping(agentOpen && agentInput text non-empty)`
  - On a non-attachable agent the input is disabled and focus goes to the navigator, which also handles Esc (back) while the agent screen is open.
  - The top bar stays on both screens.
  - the navigator's `Keys.onPressed` only acts when the grid is shown and nothing else has focus
  - Shortcuts: Ctrl+N, Ctrl+F, Ctrl+T, Ctrl+K (interrupt), Alt+←/→/↑/↓ (step on the agent screen, move on the grid)
  - `controller.agentRequested` shows the window and calls `openAgent()`
  - `showRequested` shows the grid
  - **The selected agent changes under an open agent screen without a user move** (the agent vanished): `back()`, so a draft is never sent to another agent. A user move goes through a guarded `move()`.
  - Search Esc clears and navigates. While results show, grid keys other than new, search, help and escape wait.
  - Focus that drops to nothing or to the root item: the input on the agent screen, else the navigator.
- Produces: `AgentDetail`:
  - **Header:** the `← Back` button (objectName `backButton`), a status dot in the group colour, the name, `project:branch · model`, a `■ Interrupt` button (objectName `interruptButton`, visible when work and attachable), and `⋮` (archive, stop…, open in terminal).
  - The feed is unchanged.
  - **Question block:** `N label` buttons.
  - **Input:** an `agentInput` TextArea inside a 1 px `Ansi.rule` bordered, rounded box, with a `>` prompt and placeholder `Message <name>…`.
  - Esc emits `escaped()`.
  - **Digits:** a `1`-`9` keypress with empty text and a pending question answers and is accepted.
- Produces: `KeyBar` with `property bool agentOpen` and the two hint lists from Global Constraints. Entries with an action stay NoFocus buttons with a `hint` property. The mode badge goes.
- Produces: `HelpOverlay` rows for the grid and the agent screen.

- [ ] **Step 1: Rewrite `KeysTest`:**
  - `test_starts_on_grid`: the navigator has focus and `agentOpen` is false.
  - `test_arrows_and_wasd_move`: three agents in different groups. `s`/`down`, `w`/`up` and `d`/`a` follow `c.go`.
  - `test_enter_opens_and_esc_returns`:
    - Enter: `agentOpen`, and `agentInput` has focus.
    - Type `hi`: the text is `hi`.
    - Esc: the grid shows, the navigator has focus, and the draft is `hi`.
  - `test_digits_answer_only_when_input_empty` (Review Focus 2):
    - Open a waiting agent with `_question` set and `2` pressed: records option 2.
    - Type `x` then `2`: the text is `x2`, nothing new is recorded.
  - `test_grid_digit_answers`: on the grid, `1` records option 1.
  - `test_ctrl_k_interrupts_and_esc_does_not`.
  - `test_letters_go_to_search_and_dialog` (Review Focus 5). Keep it, and also assert the dialog field text.
  - `test_open_agent_vanishing_goes_back` (Review Focus 1): open `a`, type `hi`, poll without `a`. The grid shows, the navigator has focus, and `draft("a") == "hi"`.
  - `test_alt_arrows_step_on_agent_screen`: open `a`, then Alt+→ via `trigger("next")`. Still open, `selectedKey` is `b`, and `agentInput` has focus.
  - `test_notification_opens_agent`: emit `agentRequested("b")` after `select("b")`. `agentOpen` is true.
  - `test_keys_wait_while_results_show` and `test_help_overlay`: keep.
  - `BannerTest.test_terminal_ui`: the grid hints.
- [ ] **Step 2: Run** `-k KeysTest -k BannerTest`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the suite and the smoke check, and take screenshots of both screens.** Expected: green, the smoke prints nothing, and the screenshots match the mockup.
- [ ] **Step 5: Docs:**
  - **`docs/testing.md`:** the agents lines describe sections, click or Enter to open, Esc back, digits, Ctrl+K and the notification opening the agent screen.
  - **`Readme.md`, Agents line:** "a native grid of Claude Code's background agents, grouped by who is waiting for you, working or done. Click or press Enter on one to talk to it like in Claude Code…" Keep the rest of the line.
- [ ] **Step 6: Commit** `feat(agents): open agents in a Claude Code style screen`.
