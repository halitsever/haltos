# AGENTS.md

HaltOS is a theme and OS identity layer that turns an Ubuntu VPS into a monochrome KDE Plasma desktop for Claude Code over RDP. Server owners install it with `bootstrap.sh`.

## Verify a change

CI (`.github/workflows/ci.yml`) runs these, in this order:

- `shellcheck -S warning install.sh bootstrap.sh shell/haltos-prompt.sh plasma/scripts/windeco.sh tools/clean-shot.sh tools/release.sh`
- `shellcheck -S warning -s sh system/motd/00-haltos` (POSIX sh, not bash)
- With Pillow and `fonts-jetbrains-mono` installed: `python tools/build-assets.py`, `python tools/build-kvantum.py`, `python tools/build-plasma-theme.py`
- `git diff --exit-code -- kvantum/ plasma/desktoptheme/ site/index.html`: the generated files must be committed exactly as the generators write them
- The look-and-feel and wallpaper `metadata.json` files must parse as JSON, and the Kvantum and logo SVGs as XML
- `python3 -m unittest discover -s agents/tests -t agents`: unit tests for the agents app's Qt-free core

Locally, `QT_QPA_PLATFORM=offscreen agents/haltos-agents --smoke` loads the agents window once and must print nothing.

The install itself is tested only by hand, on a fresh Ubuntu 25.04+ server, following `docs/testing.md`.

## Gotchas

- Logo, icons, wallpapers, splash, login and Plymouth images, ASCII banners, the Kvantum theme and the HALTOS wordmark inside `site/index.html` are generated. Edit `tools/build-*.py`, rerun the generators and commit their output together with the change.
- A new shell script goes into the shellcheck list in `ci.yml`, or CI never checks it.
- `bootstrap.sh` installs claude-code-vps (cloned into `/opt/claude-vps`) before HaltOS. HaltOS writes its theme paths into claude-vps's `~/.config/claude-vps/local-only` and adds a `post-apply.d/50-haltos` hook that runs `install.sh refresh`. A change to that contract needs a matching change in claude-code-vps.
- `/etc/os-release` keeps `ID=ubuntu`, and Ubuntu's files are replaced through `dpkg-divert`, so apt and vendor scripts keep working. Keep both when touching identity files.
- Plasma 6 is required. `bootstrap.sh` stops before installing anything on releases without it (Ubuntu 24.04).
- Servers follow published releases, not `main`. Only `haltos update --edge` follows `main`.
- Pushing a `v*` tag publishes a GitHub Release. The workflow fails when the tag does not match `VERSION`, and it takes the notes from the matching `CHANGELOG.md` section.
- The site has no build step. The Pages workflow copies `docs/screenshots/*.png` into `site/assets/screens/` at deploy time, so that folder is absent in the repo.
- `marketing/motion/out/` is ignored. It holds recordings saved by `marketing/motion/serve.py`.
- `agents/` is the HaltOS Agents app: a Kirigami front end (PySide6 from apt, never pip) to Claude Code's background sessions (`claude --bg`, `claude agents --json`, `claude attach`). Only `app.py` and `qml/` import Qt, so the rest stays testable without it. Every `claude` it starts gets `clean_env()`, because inherited session variables turn transcript saving off. `install.sh user` copies it per account with a menu entry and a tray autostart.

## Conventions

- Commit subjects use conventional-commit style, in English, with no body or trailer.
- Work on a branch and open a PR. The owner merges.
- Don't add emoji to new text. Code comments are short, one line where possible, and explain why.
- The README follows the owner's template. Leave every image from `halitsever-api.vercel.app` byte-for-byte as it is. Only the `title=` value of `api/repo-title` and the issue wrapper link may be corrected.
- The owner bumps `VERSION`, updates `CHANGELOG.md` and tags releases with `tools/release.sh` (see `docs/releasing.md`).

## Site

- The plain HTML site lives in `site/`, with blog posts in `site/blog/`. `.github/workflows/pages.yml` deploys it to https://halitsever.github.io/haltos/ on pushes to `main` that touch `site/`, `docs/screenshots/` or that workflow.
- When you add a page, also add it to `site/sitemap.xml` and `site/llms.txt`.
