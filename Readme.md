<p align="center" class="logo-section">
<img src="branding/haltos-logo-tile.svg" alt="HaltOS logo" height="80" width="80"/>
<br/>
<img src="https://halitsever-api.vercel.app/api/repo-title?title=HaltOS">

<p align="center">
A Claude Code workstation OS for your VPS: a monochrome, terminal-flavoured layer that turns an Ubuntu server into a remote KDE Plasma desktop for Claude Code.<br>
<br/>
<br/>
<img src="https://img.shields.io/github/sponsors/halitsever"/>
</p>
<p align="center">
<a align="center" href="#installation">Documentation</a>
  </p>
</p>

<p align="center">
<img src="docs/haltos.gif" alt="HaltOS in 30 seconds: ASCII boot, claudegrid running four Claude Code agents, the one-command install and the desktop" width="600"/>
</p>

<p align="center">
<img src="https://halitsever-api.vercel.app/api/details"/>
</p>

- **OS identity**: `/etc/os-release`, `lsb_release`, `/etc/issue` and the KDE About page report `HaltOS 1.0 (SIGKILL)`. `ID=ubuntu` is kept, so apt, PPAs and vendor scripts keep working. Ubuntu's files are preserved with `dpkg-divert`.
- **Claude Code**: [claudegrid](https://github.com/halitsever/claudegrid) opens a grid of Claude Code agents in one window, with a prompt, model and git worktree per pane.
- **Editor**: the latest VS Code from Microsoft's apt repository, so `apt upgrade` keeps it current.
- **Plasma**: `HaltMono` colour scheme (shadcn zinc palette), JetBrains Mono everywhere, ASCII splash with a fake boot log, a translucent floating top bar with a dot start icon, flat Breeze titlebars.
- **Widgets**: `HaltMono` Kvantum theme with shadcn-style outline buttons, inputs, menus, tabs, checkboxes and thin auto-hiding scrollbars.
- **GTK**: Breeze GTK follows the colour scheme, and libadwaita apps get the same zinc tokens with a white primary.
- **Terminal**: Konsole profile, two-line bash prompt with git branch and exit code, fastfetch with the HALTOS banner.
- **Login and boot**: SDDM card login screen and a Plymouth splash with a blinking cursor.
- **SSH**: ASCII MOTD with uptime, load, memory, disk and pending updates, replacing Ubuntu's banners and ESM upsell.

<p align="center" >
<img src="https://halitsever-api.vercel.app/api/installation"/>
</p>

On a fresh Ubuntu 25.04+ server, as root. This installs [claude-code-vps](https://github.com/halitsever/claude-code-vps) first (Plasma over RDP, hardened SSH, Docker, Claude Code, claudegrid), then HaltOS on top:

```sh
curl -fsSL https://raw.githubusercontent.com/halitsever/haltos/main/bootstrap.sh | sudo bash
```

Options after `bash -s --` go to `claude-vps setup`, e.g. `| sudo bash -s -- --user dev --yes`. Connect over RDP afterwards and HaltOS finishes the panel and wallpaper on the first login. The bootstrap stops before installing anything on releases without Plasma 6 (Ubuntu 24.04 ships Plasma 5).

On a machine that already runs Plasma 6:

```sh
git clone https://github.com/halitsever/haltos ~/haltos
~/haltos/install.sh user          # theme the current account, no root needed
sudo ~/haltos/install.sh system   # OS identity, MOTD, login and boot themes, defaults for new users
```

Log out and back in once so running apps pick up the Kvantum style. The first `install.sh user` saves your KDE config to `~/.haltos-backup/kde-config-original.tar.gz`.

### With claude-code-vps

[claude-code-vps](https://github.com/halitsever/claude-code-vps) is a required part of HaltOS: it sets up and manages the Claude Code server, HaltOS owns the look. The two stay separate repos, and claude-code-vps works on its own without HaltOS.

HaltOS lists the theme files it owns in claude-vps's `~/.config/claude-vps/local-only`, so `claude-vps sync` never overwrites them and `claude-vps publish` never pushes them into your public dotfiles. Your own entries in that file are kept. A hook in `~/.config/claude-vps/post-apply.d/` also runs `haltos refresh` after a sync that changed files, which rewrites the settings without a new backup or a Plasma restart.

### Updates

Servers follow published releases. One command updates claude-code-vps and HaltOS, re-applies the system and user settings, and prints what changed:

```sh
sudo haltos update           # newest release
sudo haltos update --edge    # follow main instead, until --stable switches back
haltos version               # installed version, channel and whether a newer release exists
```

A daily timer checks GitHub for a newer release, and the SSH login banner says when one is available. Releasing a new version is described in [docs/releasing.md](docs/releasing.md).

To remove HaltOS, use the `haltos` command a bootstrapped server has (on a manual clone, `~/haltos/install.sh` takes the same arguments). VS Code stays installed.

```sh
haltos undo-user          # restore the pre-HaltOS KDE config
sudo haltos undo-system   # restore Ubuntu's identity files, MOTD and defaults
```

To check a release on a fresh server, follow [docs/testing.md](docs/testing.md).

### Security / Hardening

By default claudegrid starts every agent as your own account. That account can use sudo, is in the `docker` group (which is root in practice) and can read your SSH keys and GitHub token. `haltos harden` moves the agents into a separate, unprivileged account so that a malicious package an agent installs cannot reach any of that.

```sh
sudo haltos harden                 # asks before every layer
sudo haltos harden --confirm       # keep the new firewall rules (asked for within 5 minutes)
sudo haltos harden --status        # one OK/FAIL line per layer, exits non-zero on any FAIL
sudo haltos harden --with-docker   # also give the agent its own rootless Docker
sudo haltos undo-harden            # remove all of it
```

**Threat model.** An agent, or code it runs (an npm `postinstall` script, a typosquatted PyPI package, a prompt injection in a README), acts against you. The goal is that it cannot touch your secrets, cannot get root, and can only reach the network hosts it needs. The goal is *not* to make the agent's own output safe: that stays your job.

| Layer | What it does | Protects against |
| --- | --- | --- |
| `agent` user | System user with no sudo, not in `docker`, home `700`. Your home becomes `750` and `~/.ssh`, `~/.config/gh`, git credentials and `/opt/claude-vps` lose world access | reading keys and tokens, `sudo`, root through the Docker socket |
| `/srv/agents` | `root:agents 2770`, setgid, default ACLs for you and `agent` | nothing by itself: it lets you and the agent edit the same files without loosening anything else |
| `claude-agent` + sudoers | claudegrid's pane command becomes `claude-agent`, which runs `sudo -u agent /usr/local/lib/haltos/agent-launch`. `/etc/sudoers.d/haltos-agent` allows that one program and nothing else | agents running as you |
| Claude Code policy | `/etc/claude-code/managed-settings.json` (every user): sandbox on, fail if it cannot start, no unsandboxed retries, no `~/.ssh` or `.env*` reads. `/etc/haltos/agent-settings.json` (agent only, through `--settings`): denies `sudo`, `su`, `docker`, `curl \| sh`, bypass mode, and limits sandboxed commands to the allowlisted domains | the model doing something it should not, and the commands it runs leaving the worktree |
| AppArmor | Ubuntu's `bwrap-userns-restrict` lets bwrap start, but moves what it runs into `unpriv_bwrap`, which has no capabilities. Claude Code's seccomp helper then cannot open its nested user namespace and every sandboxed command fails. harden tests exactly that, and if it fails it disables Ubuntu's profile (link in `/etc/apparmor.d/disable/`) and loads `/etc/apparmor.d/haltos-bwrap`, which grants `userns` to `/usr/bin/bwrap` alone. `kernel.apparmor_restrict_unprivileged_userns` stays `1` | every other program still being blocked from user namespaces |
| Egress firewall | A `--uid-owner agent` block in `/etc/ufw/after.rules` and `after6.rules`. The agent can reach DNS and ports 80/443 of the IPs in `/etc/haltos/agent-allowlist` and nothing else. A timer re-resolves the list into ipsets every 15 minutes | exfiltration and payload downloads, for every process the agent runs, sandboxed or not |
| Package settings | `ignore-scripts=true` in the agent's `.npmrc`, pip `require-virtualenv`, pnpm `minimum-release-age` and uv `exclude-newer` when those tools are installed | install scripts running at all, and packages published minutes ago |

The firewall uses IP sets instead of a forced HTTP proxy. A proxy filters by host name, which is more exact, but every tool would have to honour `HTTPS_PROXY`, including Claude Code's own sandbox proxy, and plain `curl` in a script would just fail. IP sets are transparent and cover every process. The cost is that CDN addresses are shared: an allowlisted Cloudflare or Fastly IP also serves other sites. Claude Code's sandbox proxy adds the host-name check for the commands it runs, so the two layers cover each other.

The ufw change cannot lock you out. Before `ufw reload`, harden arms `systemd-run --on-active=300`, which restores the previous rule files. Open a new SSH session and an RDP connection, then type `keep` (or run `sudo haltos harden --confirm`). If you do nothing, or the session dies, the old rules come back after 5 minutes. The rules only match the `agent` user anyway, so your traffic, SSH and RDP do not go through them. With claude-code-vps's Tailscale mode, `tailscaled` runs as root and is not affected, and the agent cannot reach other machines on your tailnet either.

**Using it.** Projects the agents work on must live under `/srv/agents`, for example `git clone … /srv/agents/myapp` (claudegrid puts worktrees next to the repo, in `/srv/agents/myapp.claudegrid/`). Existing trees: `sudo haltos harden --adopt /srv/agents/myapp`. Log out and back in once so your session joins the `agents` group. The agent has its own Claude Code login: run `cd /srv/agents && claude-agent` once and use `/login`. To add a host, edit `/etc/haltos/agent-allowlist` and run `sudo haltos-agent-net refresh`.

**Known limits.**

- The code the agent writes can itself be malicious. Read the diff before you run, build or test it as yourself, and before you merge it.
- Everything under `/srv/agents` is shared: one agent can change another pane's worktree, and git hooks in `.git/hooks` run as whoever runs git. Check them before you commit or pull as yourself.
- DNS goes through your resolver, so a determined process can still leak small amounts of data through lookups.
- The managed settings also sandbox your own Claude Code sessions. Sandboxed commands cannot use `sudo`, because the sandbox sets `no_new_privs`. Add `"sandbox": {"excludedCommands": ["sudo *", "docker *"]}` to your own `~/.claude/settings.json` if you need them there.
- With `--with-docker` the agent can run containers as itself. That gives it no host privileges, but sandboxed commands can use Docker to leave the Claude Code sandbox, so only the firewall and the user boundary still hold.
- A project's own `.claudegrid.json` can set `"command"` and override the wrapper.

**Turning it off.** `sudo haltos harden --no-claudegrid` keeps every layer but starts panes as you again (`--claudegrid` switches back). `sudo haltos undo-harden` removes the user, group, sudoers rule, settings, AppArmor profile, firewall block and timers, and restores the original permissions. `/srv/agents` is kept and handed back to you, and backups of every changed system file stay in `/var/lib/haltos/harden-backup/`. `haltos update` re-applies the hardening files automatically. If a release changes the firewall rules, it tells you to run `sudo haltos harden` again.

### Known limits

- The SDDM theme is only shown when SDDM is the active display manager. Ubuntu flavours often ship GDM, and xrdp sessions skip the greeter entirely.
- The Plymouth theme needs `splash` on the kernel command line. Many cloud images boot without it.
- Kvantum has no notion of keyboard-only focus, so the focus frame is disabled to avoid boxes on every click. Inputs still show a ring when focused.
- Chromium-based browsers keep their own theme unless "Use GTK" is selected in their appearance settings.

### Regenerating assets

The logo, icons, wallpapers, splash and login wordmarks, Plymouth images, ASCII banners and the Kvantum SVG are generated, so edit the scripts and rebuild instead of editing outputs:

```sh
python3 tools/build-assets.py    # logo, icons, wallpapers, splash, login, plymouth, fastfetch banner
python3 tools/build-kvantum.py   # kvantum/HaltMono from the shadcn tokens
```

`tools/clean-shot.sh` takes screenshots on a temporary empty virtual desktop so other windows never leak into them. `tools/xshot.py` and `tools/xclick.py` capture and click through UIs over X11 when no screenshot tool is installed. KWin draws titlebars on the GPU, so X11 captures show windows without them.

<p align="center">
<a href="https://github.com/halitsever/haltos/issues"><img src="https://halitsever-api.vercel.app/api/issue"/></a>
</p>

<p align="center">
Found a bug or have an idea? Open an <a href="https://github.com/halitsever/haltos/issues">issue</a>.<br/>
Read the <a href=".github/CONTRIBUTING.md">contributing guide</a> before sending a pull request.
</p>

<p align="center">
<img src="https://halitsever-api.vercel.app/api/sponsor"/>
</p>

<p align="center">
<img src="https://halitsever-api.vercel.app/api/license"/>
</p>

<p align="center">
Released under the <a href="LICENSE">MIT License</a>.
</p>
