# HaltOS Agents: grouped grid and a Claude Code style agent view

## Intent

The spotlight grid confused the owner. The big tile moved the other tiles on every selection,
and the agents were not grouped. The bar is "the dumbest person in the world can use it, but it
feels like Claude Code". The owner picked status groups over project groups, and approved a
browser mockup with two screens:
- a grouped grid of equal tiles
- a Claude Code style view of one agent, opened with Enter and left with Esc

## Goals

- **Grid screen (home):**
  - **Top bar:** the HaltOS mark and `agents`, the search field, and a labelled `+ New agent`
    button.
  - **Sections in this order:**
    - `● Waiting for you N` in yellow
    - `◐ Working N` in blue
    - `✓ Done N` in dim
    - A section with no agents is hidden.
  - **Tiles:**
    - Every tile is the same size and stays where it is. Nothing grows.
    - The selected tile has a blue border.
    - Header: name, dim project, age. A working agent shows a braille spinner before its name.
    - Body: the last lines in Claude Code style.
    - A waiting tile shows its question and `1 Yes` / `2 No` style buttons.
    - Done tiles are dimmed.
  - **Hint bar:** `←↑↓→ select · enter open · 1 2 answer · n new agent · / search`.
  - **Empty state:** "No agents yet" with the `+ New agent` button.
- **Agent screen:**
  - **Header:**
    - `← Back`
    - the status dot, name, and `project:branch · model`
    - `■ Interrupt` while the agent works
    - the `⋮` menu (archive, stop…, open in terminal)
  - **Feed:** today's full feed in Claude Code style.
  - **Question block:** the pending question with its buttons.
  - **Input:** a bordered `>` input box, focused as soon as the screen opens, with the
    placeholder `Message <name>…`.
  - **Hint bar:** `enter send · shift+enter new line · 1 2 answer · esc back`.
- The look stays HaltMono and JetBrains Mono on any desktop theme, and the UI stays in English.

## Keys

| Key | Grid | Agent screen |
|---|---|---|
| arrows, `w a s d`, `h j k l` | move the selection. Up and down go to the nearest tile in the row above or below, across sections. Left and right step through the order. All clamp at the edges. | arrows move the cursor, letters type |
| Enter, click on a tile | open the agent screen | Enter sends, Shift+Enter is a new line |
| `1`-`9` | answer the selected agent's question | answer, only while the input is empty and a question is pending |
| Esc | close help, or clear the search | back to the grid, the draft stays |
| `n`, `/`, `t`, `x`, `?` | new agent, search, terminal, interrupt, help | typed |
| Ctrl+N, Ctrl+F, Ctrl+T | new agent, search, terminal | same |
| Ctrl+K | interrupt the selected agent | interrupt this agent |
| Alt+←/→ | same as ←/→ | previous / next agent, staying on the agent screen |

There are no hidden modes. The grid never has a text input, so letters there are always
commands. The agent screen always types.

## Constraints

- Same stack and rules as before:
  - Kirigami 6 and PySide6 from apt, no new packages.
  - Only `agents/` is installed.
  - Drafts are kept per agent.
  - Polls never move focus or the selection unless the selected agent is gone.
  - Controller actions act on the selected agent.
- A launched agent is selected when it appears. While the user types on the agent screen it waits
  until they leave, as the spotlight work did.
- A notification's "Open" shows the window on that agent's screen.

## Approaches

1. **Grouped grid plus a separate agent screen.** Picked by the owner from the mockup. There are
   two screens, no hidden modes, and nothing moves.
2. Spotlight with modes (the current branch). Rejected by the owner: tiles moving around and the
   NAV/TYPE modes were confusing.
3. Projects as groups. Rejected by the owner: finding who waits for you means scanning every
   group.

## Non-goals

- Collapsing sections, manual ordering, project grouping.
- Changes to search results, the new agent dialog or notifications beyond opening the agent
  screen.

## Calls Claude made (not in the mockup)

- **Opening an agent.** A single click on a tile opens it, which is the most obvious action. The
  keyboard selection is only the highlight.
- **Interrupting.** Ctrl+K interrupts. Esc means "back" everywhere, so it no longer interrupts.
  There is also the `■ Interrupt` button and `x` on the grid.
- **Answering on the agent screen.** `1`-`9` answer only while the input is empty and a question
  is pending. Otherwise they type, so a reply that starts with a number still works.
- **The spotlight leftovers go:**
  - the NAV/TYPE badge
  - the big tile and its packing (`layout.pack` is replaced by a sectioned layout)
  - the tile inputs

## Calls made during the builder check (Claude's)

- **A launched agent opens its own screen** as soon as it appears, so you watch the prompt run.
  The one exception: you are typing into another agent's screen and its input is not empty. Then
  it waits until you go back to the grid, and only gets selected there.
- **The top bar stays on both screens.** Search results replace whichever screen is open, and
  Esc in search clears it and returns to that screen.
- **A session open in a terminal** opens its screen read-only. The input is disabled with the
  placeholder `This session is open in a terminal`. The keys go to the window, so Esc goes back
  and Alt+arrows still step.

## Left to the builder

- Tile height, the minimum tile width, and how many lines a tile shows.
- How the sections are laid out (one model per group, or one model positioned by row).
