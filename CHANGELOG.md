# Changelog

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
