# HaltOS Agents: terminal style

## Intent

The user writes prompts all day but wants the app to feel like a coder's tool. They picked
direction C from three browser mockups: everything monospace, laid out like Claude Code's
own output, with a key hint bar.

## Goals

- Every surface uses the monospace font (JetBrains Mono through `Kirigami.Theme.fixedWidthFont`):
  list, header, feed, question card, input, search results, new agent dialog.
- Flat look: no cards, no rounded panels. Thin separators, HaltMono background, Konsole ANSI
  colours for accents (red 239,68,68 · green 34,197,94 · yellow 234,179,8 · blue 59,130,246 ·
  cyan 6,182,212).
- **List:** one row per agent, ordered need, work, done. A status glyph leads the row: `!` yellow
  for need, `▶` blue for work, `✓` dimmed for done. Right side shows `need`, the elapsed time
  (`4m`, `1h12m`) or `done`. A dimmed `AGENTS` label replaces the section headers.
- **Header:** `name` in green, then `project:branch · model` dimmed. The model comes from the
  last assistant message in the transcript, shortened (`claude-opus-5-5` becomes `opus-5.5`).
- **Feed**, styled like Claude Code:
  - prompt: `$ text`, `$` in green
  - agent text: plain text, indented two spaces, muted colour. No markdown rendering.
  - tool call: `⏺ Name(arg)` with `⏺ Name` in cyan. Edit, MultiEdit and Write add `+N -M` line
    counts in green and red.
  - tool result: `  ⎿ first line`, dimmed, at most 80 characters. A result marked `is_error` is red.
- **Question card:** the question text, then options as flat `[1] Evet  [2] Hayır` buttons.
- **Input:** a `>` prompt line under a separator, no box. Enter sends, Shift+Enter adds a line.
- **Key bar** at the bottom: `esc kes · ctrl+n yeni · ctrl+f ara · ctrl+t terminal · alt+↑↓ geç`.

## Keyboard (agreed with the user)

Typing always goes to the input, like Claude Code. Shortcuts:

| Key | Action |
|---|---|
| Esc | interrupt the selected agent when it is working; in the search field, clear it and go back to the input |
| Ctrl+N | new agent dialog |
| Ctrl+F | focus search |
| Ctrl+T | open the selected agent in Konsole |
| Alt+↑ / Alt+↓ | previous / next agent in list order |

The input takes focus when the window opens and after an agent is selected.

The mouse keeps working everywhere (the user asked for this): clicking a list row selects it,
the search field and the `+` button stay at the top of the left panel, search results are
clickable, and every entry in the key bar is a flat button that does the same as its key.

## Non-goals

- Diff bodies, token counts and a status line with timers (mockup B). Only the `+N -M` counts.
- Single-letter shortcuts (`j/k`, `n`).
- A real terminal UI. The app stays the same Kirigami app with the same tray, notifications,
  search and controller.

## Constraints

- Same stack: Kirigami 6, PySide6 from apt. No new packages; JetBrains Mono already ships with
  HaltOS.
- The controller's slots stay as they are. New data (tool result line, line counts, error flag,
  model) is parsed in `transcript.py` and passed through the feed model and `selected`.
- Existing behaviour and tests stay green.

## Approaches

1. **Restyle the existing QML** with custom delegates and a fixed-width font. Picked: keeps every
   working piece and only touches the views and the transcript parser.
2. Hand-drawn QtQuick without Kirigami. Rejected: loses the HaltMono theme, dialogs and tray
   integration for no visible gain.
3. A real TUI in Konsole. Rejected: the user asked for a HaltOS-native app, not another terminal.

## Left to the builder

- Exact spacing, font sizes, and whether glyphs need a fallback font.
- Whether the key bar hides the Ctrl+T hint when the agent cannot be attached.
- Turning off markdown also closes the deferred minor about remote images in agent replies.
