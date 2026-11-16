#!/usr/bin/env bash
# Fresh Ubuntu server to HaltOS in one go: claude-code-vps builds the workstation, HaltOS dresses it.
#   curl -fsSL https://raw.githubusercontent.com/halitsever/haltos/main/bootstrap.sh | sudo bash
# Options after `bash -s --` go to `claude-vps setup`, e.g. `| sudo bash -s -- --user dev --yes`.
set -Eeuo pipefail

HALTOS_REPO=${HALTOS_REPO:-https://github.com/halitsever/haltos.git}
HALTOS_DIR=${HALTOS_DIR:-/opt/haltos}
CLAUDE_VPS_REPO=${CLAUDE_VPS_REPO:-https://github.com/halitsever/claude-code-vps.git}
CLAUDE_VPS_DIR=${CLAUDE_VPS_DIR:-/opt/claude-vps}

log() { printf '\033[38;2;250;250;250m[haltos]\033[0m %s\n' "$*"; }
die() {
    printf '\033[38;2;239;68;68m[haltos]\033[0m %s\n' "$*" >&2
    exit 1
}

clone() {
    if [ -d "$2/.git" ]; then
        git -C "$2" pull -q --ff-only
    else
        git clone -q "$1" "$2"
    fi
}

[ "$EUID" -eq 0 ] || die "run as root: curl -fsSL <url> | sudo bash"
for arg in "$@"; do
    case $arg in
    -n | --dry-run) die "dry runs are not supported here, use 'claude-vps setup --dry-run' directly" ;;
    --no-desktop) die "HaltOS is a desktop layer, it cannot run with --no-desktop" ;;
    esac
done

# Checked before anything is installed, so an older release is never left half set up.
. /etc/os-release
[ "${ID:-}" = ubuntu ] || [ "${ID_LIKE:-}" = debian ] || die "HaltOS needs Ubuntu"
command -v git >/dev/null || { apt-get update -q && DEBIAN_FRONTEND=noninteractive apt-get install -y -q git ca-certificates curl; }
apt-get update -q >/dev/null
plasma=$(apt-cache policy plasma-workspace | awk '/Candidate:/ {sub(/^[0-9]+:/, "", $2); print $2}')
[ "${plasma%%.*}" -ge 6 ] 2>/dev/null || die "HaltOS needs Plasma 6, this release offers plasma-workspace ${plasma:-none} (use Ubuntu 25.04 or newer)"

log "installing claude-code-vps"
clone "$CLAUDE_VPS_REPO" "$CLAUDE_VPS_DIR"
"$CLAUDE_VPS_DIR/bin/claude-vps" setup "$@"

TARGET_USER=$(. /etc/claude-vps.conf && echo "$TARGET_USER")
[ -n "$TARGET_USER" ] || die "claude-code-vps did not record a user in /etc/claude-vps.conf"

log "installing HaltOS for $TARGET_USER"
clone "$HALTOS_REPO" "$HALTOS_DIR"
git config --system --add safe.directory "$HALTOS_DIR"
ln -sf "$HALTOS_DIR/install.sh" /usr/local/bin/haltos
"$HALTOS_DIR/install.sh" system
# A private D-Bus session lets gsettings and kwriteconfig6 run before the user ever logs in.
runuser -l "$TARGET_USER" -c "dbus-run-session -- '$HALTOS_DIR/install.sh' user"

log "done. connect over RDP and HaltOS finishes the panel on first login."
log "update later with: sudo claude-vps update && sudo haltos update"
