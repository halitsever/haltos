# HaltOS Agents: grid

## Intent

The terminal-style inbox works, but with one agent filling the screen and the rest in a narrow
list it feels like working on one task at a time. The owner runs several agents in parallel and
wants to see that: all of them on screen at once, like claudegrid's grid, without going back to
managing terminals. They picked layout A from three browser mockups: equal tiles.

## Goals

- **Grid is the main view.** The left agent list goes away. Every live agent is a tile of the same
  size, in the existing order: need, work, done. Done tiles are dimmed.
- **Tile:** header row with status glyph (`!` yellow, `▶` blue, `✓` dim), name, dim project
  name, `tty` when not attachable, age on the right, and a `⋮` menu (arşivle, durdur…). Body shows
  the last few feed lines in the same terminal style as today (`$`, `⏺ Name(arg) +N -M`,
  `⎿ line`, indented agent text), bottom-aligned. A pending question replaces the tail's bottom
  with `? text` and `[1] Evet  [2] Hayır` buttons. A `>` input line at the bottom.
- **Selection:** one tile is selected, shown with a blue border. Typing goes to the selected
  tile's input. Clicking anywhere in a tile (input, buttons, ⋮ included) selects it first.
- **Zoom:** Ctrl+O (or the key bar entry, or a double click on a tile header) opens the selected
  agent in today's full detail view: full feed, header with `project:branch · model`, question,
  input. Its header gets a clickable `← grid`. Ctrl+O again returns to the grid.
- **Top bar:** search field and `+` (new agent), as in the left panel today. A non-empty search
  replaces the grid with today's search results; Esc in the search field clears it and returns.
- **Key bar** text in the grid: `alt+←↑↓→ geç · ctrl+o büyüt · esc kes · ctrl+n yeni · ctrl+f ara
  · ctrl+t terminal`. In zoom: `ctrl+o grid · alt+←→ önceki/sonraki · esc kes · ctrl+n yeni ·
  ctrl+t terminal`. Every entry stays a clickable flat button.

## Keyboard

| Key | Grid | Zoom |
|---|---|---|
| Alt+← / Alt+→ | previous / next tile in order | previous / next agent |
| Alt+↑ / Alt+↓ | tile one row up / down (clamped) | previous / next agent |
| Ctrl+O | zoom into selected | back to grid |
| Esc | interrupt the selected agent when working (unchanged) | same |
| Ctrl+N, Ctrl+F, Ctrl+T | unchanged | unchanged |

Focus rules from the terminal-style work stay: focus moves only on user actions; a poll never
moves it. Moving between tiles focuses the newly selected tile's input. A notification's "Aç"
shows the window, selects that agent's tile and focuses its input, in whichever mode is open.

## Constraints

- Same stack and theme as the terminal-style work: Kirigami 6, PySide6 from apt, monospace,
  Ansi colours. No new packages.
- Controller actions (`send`, `answer`, `interrupt`, `kill`, `archive`, `openTerminal`) keep
  acting on the selected agent; tiles select before acting.
- Tile data (last lines and pending question per agent) is read off the UI thread during the
  poll, and a transcript is only re-read when its mtime or the agent's status changed. Ten
  agents must not make the 2 s poll noticeably heavier.
- Existing tests stay green; tests that assume the left list are rewritten for the grid.

## Approaches

1. **Grid home, zoom into the existing detail view.** Picked: everything visible at once, long
   replies still readable in zoom, and the detail view, search and dialogs are reused.
2. Pure grid with a full scrolling feed per tile, like claudegrid. Rejected: tiles get too small
   to read past five or six agents.
3. Keep the list and pin two to four agents side by side. Rejected: the owner still picks what is
   visible, so the one-task feeling stays.

Within approach 1 the owner picked equal tiles over a done-strip layout and a large focus tile.

## Non-goals

- Resizing or reordering tiles by hand, pinning, saved layouts.
- A full scrolling feed inside tiles.
- Changes to search, the new agent dialog, notifications, tray or session handling beyond what
  the grid needs.

## Calls made during the builder check (Claude's, not the owner's)

- **Search and zoom:** the top bar stays in both modes. A non-empty search replaces whichever view
  is open; clearing it (Esc) returns to that same view. Picking a result selects the resumed agent
  and keeps the mode.
- **Notifications:** unchanged. Only the selected agent is muted while the window is active.
- **Drafts:** unsent text is kept per agent, shared by its tile and the zoom input, and survives
  moving between tiles, zooming and poll updates. Row updates move, insert and remove rows
  instead of resetting the model, so a focused tile is never recreated.

## Left to the builder

- Column count from window width (a minimum tile width), tile height, and how many tail lines fit.
- With more tiles than fit, the grid scrolls vertically and keeps the selected tile in view.
- Empty state text when there are no agents.
- How tile inputs that are not selected look (an empty `>` line is fine).
