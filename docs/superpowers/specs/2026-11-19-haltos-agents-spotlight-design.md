# HaltOS Agents: spotlight and keyboard

## Intent

The grid works the way the owner asked, but it should be more than that: good enough that people
see it and want HaltOS for it. It has to look like HaltOS, feel fast, and run entirely from the
keyboard. The owner named one interaction outright: picking a session with the arrow keys or
WASD. They handed the rest of the UI and UX to Claude. From three browser mockups they picked
**C, spotlight**: the selected tile grows and shows more, the rest sit around it, small.

Success: a screenshot or a short clip of this window makes someone curious about HaltOS, and the
owner keeps it open all day without reaching for the mouse.

## Goals

- **Spotlight grid.** All agents share one screen. The selected agent is a large tile (2 columns
  wide when there are 3+ columns) with its recent feed, its question and buttons, and its
  `>` input. Every other agent is a small tile: header plus its last line or two, or its pending
  question on one line. Moving the selection moves the spotlight; tiles slide and resize into
  their new places.
- **Two keyboard modes**, shown in the bottom bar as a badge: `GEZİN` (navigate) and `YAZ`
  (type). The app starts in GEZİN with the first agent selected. In GEZİN, letter keys are
  commands. In YAZ, keys go to the spotlight's input.
- **Looks like HaltOS everywhere.** The window always uses the HaltMono palette (the Konsole and
  Plasma scheme in this repo: background `9,9,11`, surfaces `24,24,27`, text `250,250,250`, faint
  `161,161,170`, accent blue `59,130,246`, ANSI colours as in `Ansi.qml`) and JetBrains Mono
  when it is installed, whatever the desktop theme is. Dialogs and menus included.
- **Status at a glance.**
  - Top bar: a small HaltOS mark and "agents", then counters: `N seni bekliyor` (yellow),
    `N çalışıyor` (blue), `N bitti` (dim). A counter with zero is hidden. Search and `+` on the
    right.
  - Each tile has a coloured left rail: yellow for need, blue for work, dim for done. Done tiles
    are dimmed.
  - A working agent shows a braille spinner in its header in place of the `▶` glyph.
  - When an agent starts needing the user, its rail pulses once.
  - The spotlight has an accent border with a soft glow.
- **Help overlay.** `?` shows every key on one card over the grid. Esc or `?` closes it.
- **Empty state.** With no agents: the HaltOS mark, "henüz ajan yok", and `n yeni ajan`.

## Keyboard

| Key | GEZİN | YAZ |
|---|---|---|
| `w` `a` `s` `d`, arrows, `h` `j` `k` `l` | `a`/`d`: previous/next agent in order. `w`/`s`: the tile visually above/below, nearest by centre. Clamped at the edges. | typed (arrows move the cursor) |
| Enter, `i` | YAZ on the spotlight (nothing on a `tty` tile; show "bu oturum bir terminalde açık") | Enter sends, Shift+Enter is a newline |
| Esc | closes the help overlay or zoom, otherwise nothing | back to GEZİN, the draft stays |
| `1`-`9` | answer the spotlight's question with that option | typed |
| `o`, Space, Ctrl+O | zoom: today's full detail view. Again: back to the grid | Ctrl+O only |
| `x` | interrupt the spotlight agent | typed |
| `n` / Ctrl+N, `/` / Ctrl+F, `t` / Ctrl+T | new agent, search, terminal | Ctrl forms only |
| `?` | help overlay | typed |
| Alt+arrows | same as the arrow keys | move the spotlight, stay in YAZ |

Esc no longer interrupts the agent; `x` does. In zoom the same two modes apply: `a`/`d` step
through agents, Esc in GEZİN returns to the grid.

The mouse still works:
- A click on a small tile makes it the spotlight. A click in the spotlight's input enters YAZ.
- A double click zooms.
- Clicking `[n]` buttons answers. The `⋮` menu (arşivle, durdur…) stays.

## Constraints

- Same stack: Kirigami 6, PySide6 from apt, no new packages. Only `agents/` is installed, so any
  asset (the HaltOS mark) lives under `agents/`.
- Keys act on the target the user sees right now. A key during a slide animation applies to the
  new layout immediately; animations never delay input. Animation lengths come from
  `Kirigami.Units`, so they vanish when animations are turned off.
- Everything from the grid work still holds:
  - Polls never move focus, change the mode or move the spotlight unless the selected agent
    is gone.
  - Drafts are kept per agent.
  - Rows update in place.
  - Tile data is read off the UI thread.
  - Controller actions act on the selected agent.
- The spotlight shows up to 16 feed lines, so the tail read per agent grows from 6 items to 16.
  The cache and window ladder stay.
- Search, the new agent dialog, notifications and tray behave as today.

## Approaches

Layout, picked by the owner from mockups:
1. **A, mission control:** today's equal tiles, polished. Safest. Not picked.
2. **B, lanes:** need, work and done columns. Clear triage, but small tiles. Not picked.
3. **C, spotlight.** Picked. Overview and focus on one screen, and the strongest screenshot.

Keyboard, Claude's call (the owner handed over the how and asked for WASD):
1. **Two modes, GEZİN and YAZ.** Picked: it is the only way letters can move the selection.
2. Always typing, plain arrows move only when the input is empty. Rejected: no WASD, and arrows
   change meaning depending on whether you typed something.

## Non-goals

- Manual tile sizes, pinning, reordering, saved layouts.
- Other colour themes, or a light mode.
- Changes to session handling, notifications, search results or the new agent dialog beyond
  colours and keys.
- A new README clip or screenshots (a follow-up once this lands).

## Anti-goals

- Anything that feels like a web dashboard or a toy: rounded pastel cards, bouncy animations,
  emoji.
- A key press landing on the wrong agent, or typed text being lost.
- Motion that makes the eye chase tiles: one short slide per move, nothing looping except the
  spinner.

## Calls made during the builder check (Claude's, not the owner's)

- **Spotlight height.** The grid keeps uniform rows. The spotlight spans 2 columns and as many
  rows as it takes to reach about half the visible height (at least 2). Its feed shows as many
  of the 16 lines as fit, so 16 is a cap. Tiles beside it stay small.
- **More agents than fit.** The grid scrolls vertically and keeps the spotlight in view, as it
  does today. Tiles do not compress below their small size.
- **Mode when focus comes back.** A notification's "Aç", the tray, picking a search result and
  closing the new agent dialog all land in GEZİN with that agent in the spotlight, so `1`-`9`
  answers right away and Enter starts a reply. The mode badge makes the mode clear.
- **Poll reorders.** When an agent changes group, tiles reflow with the same short slide and the
  spotlight stays on the same agent wherever it lands. Direction keys are resolved against the
  layout at the moment of the key press, never a stale one.

## Left to the builder

- Packing: tiles in order (need, work, done), filled row by row into the free cells, with the
  spotlight taking a 2 by 2 block at its turn. With 2 columns it spans both; with 1 column it
  is one column, two rows tall.
- Small tile height, column count from width, how many lines fit, and the spinner frames.
- How the palette is forced (Kirigami theme overrides or a Qt palette from Python).
- The HaltOS mark (the existing `branding/haltos-logo.svg` copied under `agents/`, or text).
- The look of the help overlay and how the mode badge is coloured.
