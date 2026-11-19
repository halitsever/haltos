# HaltOS Agents: Claude Code in tabs

## Intent

The owner wants HaltOS Agents to replace claudegrid without falling behind Claude Code. A click on an
agent has to open the real Claude Code, with all of its keys and features, inside the app's own
window, the way a browser opens a new tab. A separate Konsole window felt like a popup.

## Goals

- **A tab bar under the top bar.** The first tab is always `Agents`, the grouped grid. Each opened
  agent adds a tab with a status dot, its name and `×`.
- **A click, Enter or `t` on a tile opens that agent's tab,** or switches to it when it is already
  open. A notification's Open and a newly launched agent do the same. A launched agent does not
  switch tabs while the user is typing into the new agent dialog or search.
- **An agent tab is the real Claude Code.** It is `claude attach <id>` on a pseudo-terminal, drawn
  by a terminal emulator in HaltMono colours and JetBrains Mono.
  - Every key goes to Claude Code, except the tab keys below.
  - The terminal follows the tab's size.
  - The mouse wheel scrolls back through the output.
  - Ctrl+Shift+V pastes.
- **Closing a tab** (`×` or Ctrl+Shift+W) detaches. The agent keeps running.
- **Tab keys**, none of which Claude Code uses:
  - Ctrl+Tab and Ctrl+Shift+Tab: next and previous tab.
  - Alt+0: `Agents`.
  - Alt+1 to Alt+9: the tab in that position.
- A session already open in another terminal cannot be attached twice. Its tab says so.

## Constraints

- **New dependency:** `python3-pyte` from apt, the VT emulator. The owner approved it. `install.sh`
  installs it with the other agents modules.
- **Qt-free modules:** key encoding and screen rendering live in modules without Qt, so they can be
  tested without it. The pyte tests skip when pyte is missing.
- **One attachment per agent:** the actions (answer, interrupt) and the tab share it.

## Approaches

1. **Embedded terminal per tab (picked).** pyte plus QML text rows, on the PTY the app already
   keeps.
2. **A separate Konsole window (built, rejected by the owner).** It felt like a popup.
3. **Rebuilding Claude Code's features in our own chat view (rejected).** It would always lag
   behind Claude Code.

## Left to the builder

How the rows are drawn, the colour mapping from pyte to HaltMono, and the refresh throttle.
