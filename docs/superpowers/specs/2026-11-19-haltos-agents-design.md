# HaltOS Agents: design

Date: 2026-11-19. Status: draft for owner approval.

## Intent

HaltOS is a Claude Code workstation, but running agents on it today means claudegrid: a settings page in a Chrome `--app` window that hands off to a grid of Konsole panes. The owner finds this neither native to HaltOS nor the right shape: they manage agents, they do not want to manage terminals.

HaltOS Agents is a HaltOS-only desktop app for managing Claude Code agents. It looks and behaves like part of the OS, it puts agents (not terminals) at the centre, and it never takes away anything Claude Code can do.

How the owner works today, which the app is built around: start Claude Code in auto mode, type "do this", let it work. Beyond that they need to start new sessions and search old ones.

## Goals

- **Inbox layout** (chosen from mockups A/B/C). Left sidebar: agents grouped as "seni bekliyor" (needs you), "çalışıyor" (working), "bitti" (done), with a session search field and a "+" for a new agent. Right pane for the selected agent: header (name, directory, model, branch, Terminal, Stop), a short progress feed, the agent's open question with quick-answer buttons, and an input box that sends text to the agent.
- **Full Claude Code parity.** Every agent is a real Claude Code session, not a re-implementation. Anything the inbox view does not cover is one click away in the terminal view of the same session.
- **Auto mode by default**: new agents start with `--permission-mode auto`.
- **Agents outlive the window.** Closing the app or dropping the RDP connection never stops an agent.
- **Plasma notifications** for state changes (rules under Notifications), also when the main window is closed.
- **New agent**: pick a directory, optional name, model, worktree toggle, first prompt.
- **Search old sessions**: full-text search over all Claude Code transcripts on the machine (`~/.claude/projects/**/*.jsonl`, 66 today). Opening a result resumes that session as an agent.
- **Native look with no custom theme code**: the app takes HaltMono colours, JetBrains Mono and Kvantum widgets from the system. It has a HaltOS icon in the app menu and the panel.

## Non-goals

- Replacing Konsole as a general terminal.
- Re-implementing Claude Code's UI, commands, permission logic or session management.
- Support outside HaltOS (macOS, other distros, Plasma 5). claudegrid stays the cross-platform tool and is not changed.
- Scheduled or self-starting "role" agents. A later version can add them on top of the same session model.
- Remote or phone control, multi-user setups.

## Anti-goals

These would make the app a failure even if it technically works:

- Something that works in Claude Code is blocked or broken in the app.
- An agent dies because the window closed or RDP dropped.
- The main window feels like a web page or like a grid of terminals.
- Sessions started from the app are missing from search (for example because transcript saving got switched off).

## Constraints

- Ubuntu with Plasma 6, the HaltOS target. Qt 6 only.
- PySide6 must come from Ubuntu's apt packages (`python3-pyside6.qtqml`, `python3-pyside6.qtquick`), not pip. Only the system Qt loads the KDE platform theme and Kirigami.
- Kirigami (`qml6-module-org-kde-kirigami`) is already present on HaltOS.
- No Qt 6 build of QMLTermWidget is packaged. Ubuntu's `qml-module-termwidget` is Qt 5, and `qmlkonsole` compiles its Qt 6 copy into its binary.
- The app must launch `claude` with a clean environment. A `claude` started with inherited `CLAUDE_CODE_*` variables (seen in the spike, launched from inside another session) turns transcript saving off, which breaks search.
- Claude Code's self-update currently fails on this machine (no write permission to the npm prefix). Agents would stay on an old version. This is out of scope for the app but should be fixed in claude-code-vps.
- HaltOS repo rules apply: see `AGENTS.md` (shellcheck list in CI, generated assets via `tools/build-*.py`, `install.sh user/system`, `haltos update`, `haltos undo-user`, no emoji, English code and docs).

## Approaches considered

1. **Kirigami app in QML + PySide6.** Chosen. It is the only option that is native rather than styled to look native.
2. **Tauri or Electron with xterm.js.** It reuses claudegrid's TypeScript and `ui.html`, and xterm.js renders Claude Code perfectly. Rejected because the main window stays a web page, which is the feeling the owner wants gone.
3. **Plasma panel widget + Konsole.** It feels the most like part of the OS. Rejected because a panel popup is too small to read an agent's progress. A small panel status indicator can come later on top of approach 1.

### Spike results (2026-11-19, throwaway code, not kept)

- Kirigami window from PySide6 with the inbox layout and fake data: HaltMono, JetBrains Mono, Kvantum buttons and Plasma notification styling all came from the system with zero theme code.
- Claude Code inside `qmlkonsole`, which uses the Qt 6 QMLTermWidget: colours, Turkish characters, logo, syntax highlighting and status lines render correctly. Box-drawing characters (table borders, the input box frame) render as broken, dashed lines with gaps between rows.
- Keyboard handling inside QMLTermWidget was not tested.

## Design

### Agents are Claude Code background sessions

Claude Code (2.1.326 on this machine) already runs agents in the background:

- `claude --bg` starts a session and prints its id.
- `claude agents --json` lists live sessions with id, sessionId, cwd, name, kind (`background` or `interactive`) and state (`busy`, `blocked`, `idle`, `done`).
- `claude attach <id>` opens a session in a terminal.
- `logs`, `stop`, `respawn` and `rm` manage it.
- `-w/--worktree [name]` creates a git worktree for it.

The app is a native front end to this system. It does not run its own tmux server, registry or status hooks:

- **Starting an agent**: `claude --bg --permission-mode auto --name <name> [--model M] [-w <name>] [prompt]`, in a clean environment, with the chosen directory as cwd.
- **Resuming a session**: `claude --bg --resume <session-id>` in the session's original directory.
- **Staying alive**: Claude Code keeps the sessions running. The app only views and controls them.
- **Listing** comes from `claude agents --json`, polled every few seconds while the app runs. The inbox shows every live session on the machine, including interactive ones started in Konsole or claudegrid. This costs nothing extra and matches "I manage my agents".
- **State mapping**: `blocked` maps to "seni bekliyor", `busy` to "çalışıyor", and `idle` and `done` to "bitti". The owner can archive an agent from "bitti": the app runs `claude rm` when Claude Code says it is safe and otherwise only hides the agent.
- **Worktrees** are left to Claude Code's `-w`, so they live where `claude` itself puts them. The toggle is on by default in git repos.

### Inbox view

- The progress feed is read from the session's transcript JSONL (located by sessionId): the owner's prompts, the assistant's text, and one-line summaries of tool calls.
- **Input**: for each agent the owner opens, the app keeps a `claude attach <id>` process on a pseudo-terminal it owns. The input box writes text into that PTY as a bracketed paste followed by Enter, so multi-line text and slash commands behave as if typed. The same PTY feeds the terminal view.
- **Quick-answer buttons** appear when the agent is `blocked`, and send the matching key into the PTY.
- **Stop** sends Escape (Claude Code's interrupt). Killing an agent (`claude stop`) is a separate, confirmed action.

### Terminal view

The terminal view shows the full Claude Code UI of the selected agent, where anything the inbox lacks can be done. In v1 it is a Konsole window (see "Terminal view in v1").

### New agent

- Directory picker that offers recent directories first (from `~/.claude/projects`).
- Name, generated from the prompt when left empty.
- Model.
- Worktree toggle.
- First prompt.

### Search

- A full-text index (SQLite FTS5 in `~/.cache/haltos-agents/`) over all transcripts, updated incrementally by file mtime.
- Results show session name or first prompt, directory, date and a matching snippet.
- Opening a result resumes it as an agent in its original directory.

### Running in the background

Closing the main window keeps the app running in the system tray, so state changes still produce notifications. The app autostarts at login. Quitting from the tray stops the app, not the agents.

### Packaging

- The app lives in this repo under `agents/` (Python + QML) and installs with `install.sh user` into `~/.local/share/haltos/agents`. It gets a `.desktop` entry, an autostart entry and an icon. The icon is generated by `tools/build-assets.py` like the other HaltOS assets.
- `haltos undo-user` removes it.
- `install.sh system` adds the apt dependencies.
- claudegrid stays installed beside the app for now. Replacing it is a later decision, made once the app has been used for a while.

### Notifications

The owner left these rules to Claude's judgement:

- **`blocked`**: always notify. The agent cannot continue without the owner.
- **`busy` to `idle`**: notify only when the agent was busy for at least a minute, since that means real work finished. Short replies stay quiet so many agents do not turn into noise.
- **No notification** when the owner is already looking at that agent in a focused window.
- Notifications go through Plasma, so Do Not Disturb and the notification history work as usual.
- Clicking a notification opens the app on that agent.

### Terminal view in v1

The owner left this to Claude's judgement. In v1 the Terminal button opens the same session in a Konsole window running `claude attach <id>`, with the HaltOS Konsole profile.

An embedded terminal (Qt 6 QMLTermWidget built and shipped from CI, or xterm.js in a QtWebEngine view) is deferred to v2. The reasons:

- The owner works mostly in the inbox view.
- The embedded widget is the most expensive and riskiest part: no package, a CI build matrix, an unfixed box-drawing glitch and untested keyboard handling.

## Risks and first tasks

1. **Writing into an attached PTY** must be proven against a real background session: plain text, multi-line paste, slash commands and Escape.
2. **Two attaches at once.** Check whether a session can be attached by the app's hidden PTY and a Konsole window at the same time. If not, the app releases its PTY while the Konsole window is open and re-attaches after it closes.
3. **Quick-answer key mapping** depends on how Claude Code draws its prompts. Prove it against a real permission prompt and a real question before building the buttons.
4. **`claude agents --json` is the app's main data source.** If its format changes between Claude Code releases, the app breaks. Parse it defensively and show unknown states as-is instead of failing.

## Left to the builder

- Module layout, the polling interval, the FTS schema and the transcript parsing details.
- Agent naming rules, layout spacing and empty states.
- Test strategy. The repo has no Python tests yet. Unit tests for state mapping, transcript parsing, search and the `claude agents --json` parser are expected.
