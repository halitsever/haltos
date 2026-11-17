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

## 5. Second login

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
