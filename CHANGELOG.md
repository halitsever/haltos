# Changelog

## 1.3.0

- HaltOS Agents is claudegrid as a system app. The HaltOS H button in the task bar brings your last grid back with every Claude Code agent resumed in its own folder, and a New grid button next to it opens a fresh one.
- The H icon sits in the system tray all the time. A left click lists your recent grids to reopen, with an X to remove each, and the right click menu has the same. A user service keeps it running and brings it back if it stops.
- claudegrid's Konsole windows group under the H button instead of Konsole's.
- VS Code opens in a HaltMono theme with JetBrains Mono and the terminal's colours. A theme or font you pick yourself still wins, and `undo-user` takes it out.
- The wallpaper, the readme, the GIF and the launch video no longer show the release number.
- The install retries the VS Code signing key download when Microsoft answers with 429.

## 1.2.1

- `haltos harden` is removed. claudegrid agents run as your own account again, and `bootstrap.sh` no longer sets up the agent isolation on new servers.
- On a server hardened with 1.2.0, run `sudo haltos undo-harden` before you update, because 1.2.1 no longer ships that command.

## 1.2.0

- `sudo haltos harden` isolates claudegrid's Claude Code agents: they run as an unprivileged `agent` user with no sudo, no Docker and no access to your home, SSH keys or tokens. Projects live in `/srv/agents`, shared with your account.
- Claude Code runs sandboxed through `/etc/claude-code/managed-settings.json`, and the agent gets its own deny rules and domain allowlist.
- An egress firewall lets the agent reach only DNS, Anthropic, npm, PyPI and GitHub. Your own traffic, SSH and RDP are untouched, and a 5-minute guard rolls the ufw change back unless it is confirmed.
- On Ubuntu, a narrow AppArmor profile lets bubblewrap run Claude Code's sandbox without lifting the user namespace restriction for other programs.
- New servers get this by default from `bootstrap.sh`. `--no-harden` skips it, `sudo haltos harden --status` checks every layer and `sudo haltos undo-harden` removes it.
- `undo-system` keeps the hardening backups in `/var/lib/haltos`.

## 1.1.0

- Central updates: `sudo haltos update` installs the newest release instead of whatever is on main, updates claude-code-vps too, re-applies the system and user settings and prints what changed. `--edge` follows main and `--stable` switches back.
- `haltos version` shows the installed version, the channel and whether a newer release exists.
- A daily timer checks for new releases and the SSH login banner says when one is available.
- New servers start on the newest release tag.
- `tools/release.sh` and a release workflow publish a version with one command.
- The panel clock keeps a fixed small size instead of growing with the bar.
- The website gained a blog with nine posts and a guide on running Claude Code on a VPS.

## 1.0.0 (SIGKILL)

The first release: a Claude Code workstation OS for your VPS.

- One command on a fresh Ubuntu 25.04+ server (`bootstrap.sh`) installs [claude-code-vps](https://github.com/halitsever/claude-code-vps) and then HaltOS. It checks for Plasma 6 before touching anything.
- [claudegrid](https://github.com/halitsever/claudegrid) runs several Claude Code agents side by side in one window.
- The latest VS Code from Microsoft's apt repository.
- OS identity: `os-release`, `lsb_release`, `/etc/issue` and the KDE About page say HaltOS 1.0 (SIGKILL), through `dpkg-divert`, with `ID=ubuntu` kept so apt and PPAs keep working.
- A monochrome look from shadcn's zinc palette: Plasma colour scheme, a generated Kvantum widget theme, a slim translucent top bar with its own Plasma theme, flat titlebars and JetBrains Mono everywhere.
- GTK and libadwaita apps follow the same palette.
- ASCII splash with a boot log, an SDDM login card and a Plymouth splash.
- Konsole profile, a two-line prompt with git branch and exit code, and fastfetch with the HALTOS banner.
- An SSH banner with uptime, load, memory, disk and pending updates instead of Ubuntu's ads.
- `haltos refresh` and a claude-code-vps post-apply hook keep the theme across `claude-vps sync`; the theme files are listed in claude-vps's local-only list so they are never synced or published.
- `haltos update`, `haltos undo-user` and `sudo haltos undo-system`.
- A website with the launch video: https://halitsever.github.io/haltos/
