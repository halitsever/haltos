# Testing a release

Run this on a fresh server before tagging a release. Every step lists the command and what it should print. If a step fails, keep its output and `/root/bootstrap.log`.

CI already installs, reinstalls and undoes both layers in an Ubuntu 26.04 container on every pull request. To run the same checks locally:

```sh
docker run --rm -v "$PWD":/src:ro ubuntu:26.04 /src/tests/system.sh
docker run --rm -v "$PWD":/src:ro ubuntu:26.04 /src/tests/user.sh
```

This list covers what a container cannot: the bootstrap, RDP, the live Plasma session and the login screens.

## 0. Prepare

- [ ] A fresh **Ubuntu 25.04 or 26.04** VPS, amd64, 4 GB RAM or more.
- [ ] Your SSH key works for `root`. claude-code-vps copies it to the new user.
- [ ] The provider firewall allows ports **22** (SSH) and **53389** (RDP).

## 1. Refusal on Plasma 5 (optional, Ubuntu 24.04)

- [ ] Run the install command from step 2. It stops with `HaltOS needs Plasma 6 ...`.
- [ ] `ls /opt/claude-vps /opt/haltos` finds neither directory: nothing was installed.

## 2. Install

As root:

```sh
curl -fsSL https://raw.githubusercontent.com/halitsever/haltos/main/bootstrap.sh | bash -s -- --user dev --yes 2>&1 | tee /root/bootstrap.log
```

- [ ] The last lines read `[haltos] done. connect over RDP ...`.
- [ ] Note the password and RDP address from the claude-code-vps summary.

## 3. Over SSH, as `dev`

| Command | Expected |
| --- | --- |
| Login banner | ASCII `H` logo and an `apt` line, no Ubuntu ads |
| `lsb_release -d` | `HaltOS 1.2 (SIGKILL)` |
| `grep ^ID= /etc/os-release` | `ID=ubuntu` |
| `dpkg-divert --list \| grep -cE 'os-release\|lsb-release\|issue'` | `3` |
| `fastfetch` | HALTOS banner, the `os` line says HaltOS, not Kubuntu |
| `code --version` | The latest VS Code release |
| `ls /etc/apt/sources.list.d/ \| grep -c vscode` | `1` |
| `sudo apt update` | No "configured multiple times" warnings |
| `readlink -f "$(command -v haltos)"` | `/opt/haltos/install.sh` |
| `claude --version && claudegrid --version` | Two version numbers |
| `grep -c '# >>> haltos' ~/.config/claude-vps/local-only` | `1` |
| `ls ~/.config/claude-vps/post-apply.d/50-haltos` | The file exists |
| `ls ~/.config/autostart/haltos-firstrun.desktop` | The file exists, since nobody has logged in over RDP yet |

## 4. First RDP login (`dev`, port 53389)

- [ ] The splash screen shows the ASCII boot log while the session starts.
- [ ] The top bar is slim (32 px), translucent and floating, with the dot start icon, no virtual desktop pager and the date and time on one line.
- [ ] The wallpaper shows the HALTOS wordmark.
- [ ] `ls ~/.config/autostart/haltos-firstrun.desktop` now finds nothing: the first-run step ran and removed itself.
- [ ] Konsole opens with the HaltOS profile, the two-line prompt and fastfetch.
- [ ] The settings dialog of Kate or Dolphin shows outline buttons that turn white when pressed.
- [ ] Window titlebars are flat and use JetBrains Mono.
- [ ] About This System (kinfocenter) shows the HaltOS name and logo.
- [ ] VS Code starts from the application menu.
- [ ] After `claude` is logged in, `claudegrid -l 2x2` opens four Claude Code panes.
- [ ] HaltOS Agents starts from the application menu with the A icon and sits in the tray. Closing its window keeps the tray icon.
- [ ] HaltOS Agents is pinned to the task bar, uses the pixel creature icon and opens maximized. It is dark (HaltMono, JetBrains Mono) even when the desktop uses a light theme.
- [ ] Agents sit in three sections, "Waiting for you", "Working" and "Done", each with its count. Every tile has the same size, and selecting one only moves the blue border.
- [ ] "+ New agent" asks only for the task and the folder, with name, model and worktree under "More options". The new agent's tile shows a spinner in "Working" and its Claude Code window opens on its own.
- [ ] The arrow keys, W/A/S/D and h/j/k/l move the selection, and up/down cross sections. `?` shows every key and Esc closes it.
- [ ] A click, Enter or `t` on a tile opens that agent in Claude Code itself: a HaltOS themed Konsole without menu or tab bar, titled with the agent's name. Slash commands, Shift+Tab and `@` files work there. Opening it again does not start a second window, and closing it leaves the agent running.
- [ ] On an agent waiting with a question, `1`, `2`... on the grid answer it. `x` or Ctrl+K interrupts a working agent, `n` opens the new agent dialog and `/` jumps to search (Esc there goes back).
- [ ] An agent that ran for over a minute raises a notification whose "Open" button opens that agent in Claude Code.
- [ ] Enter on a session that is already open in a terminal says so instead of opening a second one.
- [ ] The feed shows `$` prompts, `⏺ Edit(file) +N -M` tool calls with `⎿` results under them, and the header shows `project:branch · model`.
- [ ] Searching a word from an old session lists it, and clicking the result resumes it as an agent.

## 5. Second login

- [ ] HaltOS Agents is back in the tray without being opened by hand.

- [ ] Log out and back in. The bar, wallpaper and theme are unchanged.

## 6. Sync

| Command | Expected |
| --- | --- |
| `claude-vps sync` | `kept local ...` lines for the HaltOS files, the theme is unchanged |
| `claude-vps sync` again | `already up to date` |
| `claude-vps autosync on`, then `systemctl --user list-timers` | `claude-vps-sync.timer` is listed |

## 7. Update

- [ ] `sudo claude-vps update && sudo haltos update` finishes without errors.

## 8. Removal (optional, throwaway servers only)

- [ ] `haltos undo-user`, then `sudo haltos undo-system`.
- [ ] `lsb_release -d` shows Ubuntu again and the SSH banner is Ubuntu's.
- [ ] After logging out and back in, the desktop is Breeze again. VS Code stays installed.
