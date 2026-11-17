# Releasing

1. In a PR, bump `VERSION` (for example `1.1.0`) and add a `## 1.1.0` section at the top of `CHANGELOG.md`. A codename goes in brackets: `## 2.0.0 (SIGTERM)`.
   Then run `python3 tools/build-assets.py` and commit what it changes: the readme, site, login and splash screens, fastfetch banner and wallpapers all show the version. A new codename goes in `HALTOS_CODENAME` in `install.sh` first. CI fails if the readme, site or theme files still show the old one. The video and GIF need a re-render too, see "Regenerating assets" in the readme.
2. Merge it, then on an up to date `main`:

   ```sh
   tools/release.sh 1.1.0
   ```

   The script checks that `VERSION` and the changelog agree, tags `v1.1.0` and pushes the tag.
3. The `release` workflow builds the theme archives, takes the notes from `CHANGELOG.md` and publishes the GitHub Release with the video and GIF attached.
4. Within a day, servers show `haltos 1.1.0 available: sudo haltos update` in their SSH banner. `sudo haltos update` installs it.

Before tagging, run the checks in [testing.md](testing.md) on a fresh server.
