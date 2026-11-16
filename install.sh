#!/usr/bin/env bash
# HaltOS installer.
#   ./install.sh user          theme the current account (no root needed)
#   sudo ./install.sh system   brand the OS: os-release, MOTD, about page, defaults for new users
#   sudo ./install.sh undo-system
set -euo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
HALTOS_VER="1.0"
HALTOS_CODENAME="SIGKILL"
LNF=org.haltos.mono

log() { printf '\033[38;2;250;250;250m[haltos]\033[0m %s\n' "$*"; }
die() { printf '\033[38;2;239;68;68m[haltos]\033[0m %s\n' "$*" >&2; exit 1; }

copy_assets() {
    local share=$1
    install -d "$share/color-schemes" "$share/konsole" "$share/wallpapers" "$share/plasma/look-and-feel" "$share/icons" "$share/haltos/fastfetch"
    install -m644 "$HERE/plasma/color-schemes/HaltMono.colors" "$share/color-schemes/"
    install -m644 "$HERE/konsole/HaltOS.profile" "$HERE/konsole/HaltMono.colorscheme" "$share/konsole/"
    rm -rf "$share/wallpapers/HaltOS" "$share/plasma/look-and-feel/$LNF"
    cp -r "$HERE/branding/wallpapers/HaltOS" "$share/wallpapers/"
    cp -r "$HERE/plasma/look-and-feel/$LNF" "$share/plasma/look-and-feel/"
    cp -r "$HERE/branding/icons/hicolor" "$share/icons/"
    install -m644 "$HERE/system/fastfetch/haltos.txt" "$share/haltos/fastfetch/"
    install -m644 "$HERE/shell/haltos-prompt.sh" "$share/haltos/"
}

install_user() {
    [ "$EUID" -ne 0 ] || die "user mode runs as your normal account, not root"
    local share=${XDG_DATA_HOME:-$HOME/.local/share}
    local conf=${XDG_CONFIG_HOME:-$HOME/.config}
    local backup="$HOME/.haltos-backup"
    install -d "$backup"
    (cd "$conf" && tar czf "$backup/kde-config-$(date +%Y%m%d-%H%M%S).tar.gz" \
        --ignore-failed-read kdeglobals kwinrc plasmarc ksplashrc konsolerc \
        plasma-org.kde.plasma.desktop-appletsrc 2>/dev/null) || true
    log "backup written to $backup"

    copy_assets "$share"

    install -d "$conf/fastfetch"
    sed "s|/usr/share/haltos|$share/haltos|" "$HERE/system/fastfetch/config.jsonc" >"$conf/fastfetch/config.jsonc"

    if ! grep -q 'haltos-prompt.sh' "$HOME/.bashrc" 2>/dev/null; then
        printf '\n# HaltOS\n[ -f "%s/haltos/haltos-prompt.sh" ] && . "%s/haltos/haltos-prompt.sh"\n' "$share" "$share" >>"$HOME/.bashrc"
    fi

    local mono="JetBrains Mono"
    kwriteconfig6 --file kdeglobals --group General --key fixed "$mono,11,-1,5,400,0,0,0,0,0,0,0,0,0,0,1"
    kwriteconfig6 --file kdeglobals --group General --key font "$mono,10,-1,5,400,0,0,0,0,0,0,0,0,0,0,1"
    kwriteconfig6 --file kdeglobals --group General --key menuFont "$mono,10,-1,5,400,0,0,0,0,0,0,0,0,0,0,1"
    kwriteconfig6 --file kdeglobals --group General --key toolBarFont "$mono,9,-1,5,400,0,0,0,0,0,0,0,0,0,0,1"
    kwriteconfig6 --file kdeglobals --group General --key smallestReadableFont "$mono,8,-1,5,400,0,0,0,0,0,0,0,0,0,0,1"
    kwriteconfig6 --file kdeglobals --group WM --key activeFont "$mono,10,-1,5,700,0,0,0,0,0,0,0,0,0,0,1"
    kwriteconfig6 --file kdeglobals --group KDE --key LookAndFeelPackage "$LNF"
    [ -d /usr/share/icons/breeze-dark ] && kwriteconfig6 --file kdeglobals --group Icons --key Theme breeze-dark
    kwriteconfig6 --file ksplashrc --group KSplash --key Engine KSplashQML
    kwriteconfig6 --file ksplashrc --group KSplash --key Theme "$LNF"
    kwriteconfig6 --file konsolerc --group "Desktop Entry" --key DefaultProfile HaltOS.profile
    rm -rf "$conf/Kvantum/HaltMono"
    install -d "$conf/Kvantum"
    cp -r "$HERE/kvantum/HaltMono" "$conf/Kvantum/"
    kwriteconfig6 --file "$conf/Kvantum/kvantum.kvconfig" --group General --key theme HaltMono
    kwriteconfig6 --file kdeglobals --group KDE --key widgetStyle kvantum

    # Plasma keys images by path, so regenerated assets at the same path would otherwise stay stale.
    rm -f "$HOME/.cache/icon-cache.kcache"

    if [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
        plasma-apply-colorscheme HaltMono >/dev/null || true
        qdbus6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript '
            panels().forEach(function (p) {
                p.widgets("org.kde.plasma.kickoff").forEach(function (w) {
                    w.currentConfigGroup = ["General"];
                    w.writeConfig("icon", "haltos-start");
                });
            });' >/dev/null || true
        plasma-apply-wallpaperimage "$share/wallpapers/HaltOS" >/dev/null || true
        kquitapp6 plasmashell >/dev/null 2>&1 || true
        setsid -f kstart plasmashell >/dev/null 2>&1 || true
        log "applied to the running Plasma session"
    else
        log "no graphical session found, settings apply at next login"
    fi
    log "user theme installed. open a new terminal to see the prompt."
}

write_os_release() {
    local orig=/usr/lib/os-release.ubuntu
    (
        # shellcheck disable=SC1090
        . "$orig"
        cat <<EOF
PRETTY_NAME="HaltOS $HALTOS_VER ($HALTOS_CODENAME)"
NAME="HaltOS"
VERSION="$HALTOS_VER ($HALTOS_CODENAME)"
VERSION_ID="$VERSION_ID"
VERSION_CODENAME=$VERSION_CODENAME
ID=ubuntu
ID_LIKE=debian
VARIANT="$HALTOS_CODENAME"
VARIANT_ID=haltos
HALTOS_VERSION="$HALTOS_VER"
BASE_PRETTY_NAME="$PRETTY_NAME"
HOME_URL="https://github.com/halitsever/haltos"
SUPPORT_URL="$SUPPORT_URL"
BUG_REPORT_URL="$BUG_REPORT_URL"
UBUNTU_CODENAME=$UBUNTU_CODENAME
LOGO=haltos-logo
EOF
    ) >/usr/lib/os-release
}

# Copy then divert without rename, so the essential file is never missing even for a moment.
divert() {
    dpkg-divert --list "$1" | grep -q . && return 0
    cp -a "$1" "$2"
    dpkg-divert --local --no-rename --divert "$2" --add "$1" >/dev/null
}

install_system() {
    [ "$EUID" -eq 0 ] || die "system mode needs root: sudo $0 system"
    copy_assets /usr/share
    gtk-update-icon-cache -qf /usr/share/icons/hicolor 2>/dev/null || true

    # ID stays ubuntu so apt, PPAs and vendor install scripts keep working.
    divert /usr/lib/os-release /usr/lib/os-release.ubuntu
    write_os_release
    divert /etc/lsb-release /etc/lsb-release.ubuntu
    sed "s|^DISTRIB_DESCRIPTION=.*|DISTRIB_DESCRIPTION=\"HaltOS $HALTOS_VER ($HALTOS_CODENAME)\"|" /etc/lsb-release.ubuntu >/etc/lsb-release
    divert /etc/issue /etc/issue.ubuntu
    printf 'HaltOS %s (%s) \\n \\l\n\n' "$HALTOS_VER" "$HALTOS_CODENAME" >/etc/issue
    log "os identity: $(. /etc/os-release && echo "$PRETTY_NAME")"

    install -m755 "$HERE/system/motd/00-haltos" /etc/update-motd.d/00-haltos
    for f in 00-header 10-help-text 50-motd-news 50-landscape-sysinfo 91-contract-ua-esm-status; do
        [ -x "/etc/update-motd.d/$f" ] && chmod -x "/etc/update-motd.d/$f"
    done

    install -d /etc/xdg/fastfetch
    install -m644 "$HERE/system/xdg/kcm-about-distrc" /etc/xdg/
    install -m644 "$HERE/system/fastfetch/config.jsonc" /etc/xdg/fastfetch/
    kwriteconfig6 --file /etc/xdg/kdeglobals --group KDE --key LookAndFeelPackage "$LNF"
    kwriteconfig6 --file /etc/xdg/kdeglobals --group General --key ColorScheme HaltMono
    kwriteconfig6 --file /etc/xdg/ksplashrc --group KSplash --key Theme "$LNF"
    kwriteconfig6 --file /etc/xdg/konsolerc --group "Desktop Entry" --key DefaultProfile HaltOS.profile
    rm -rf /usr/share/Kvantum/HaltMono
    cp -r "$HERE/kvantum/HaltMono" /usr/share/Kvantum/
    kwriteconfig6 --file /etc/xdg/Kvantum/kvantum.kvconfig --group General --key theme HaltMono
    kwriteconfig6 --file /etc/xdg/kdeglobals --group KDE --key widgetStyle kvantum
    grep -q haltos-prompt.sh /etc/skel/.bashrc ||
        printf '\n# HaltOS\n[ -f /usr/share/haltos/haltos-prompt.sh ] && . /usr/share/haltos/haltos-prompt.sh\n' >>/etc/skel/.bashrc

    log "installing fastfetch and kvantum"
    apt-get install -y -qq fastfetch qt6-style-kvantum >/dev/null
    log "system branding installed. reconnect via SSH to see the new MOTD."
}

undivert() {
    local saved
    saved=$(dpkg-divert --truename "$1")
    [ "$saved" != "$1" ] || return 0
    cp -a "$saved" "$1"
    dpkg-divert --local --no-rename --remove "$1" >/dev/null
    rm -f "$saved"
}

undo_system() {
    [ "$EUID" -eq 0 ] || die "undo needs root: sudo $0 undo-system"
    undivert /usr/lib/os-release
    undivert /etc/lsb-release
    undivert /etc/issue
    rm -f /etc/update-motd.d/00-haltos /etc/xdg/kcm-about-distrc /etc/xdg/fastfetch/config.jsonc
    for f in 00-header 10-help-text 50-motd-news 50-landscape-sysinfo 91-contract-ua-esm-status; do
        [ -f "/etc/update-motd.d/$f" ] && chmod +x "/etc/update-motd.d/$f"
    done
    sed -i '/^# HaltOS$/,+1d' /etc/skel/.bashrc
    for f in kdeglobals ksplashrc konsolerc Kvantum/kvantum.kvconfig; do
        [ -f "/etc/xdg/$f" ] && sed -i '/HaltMono\|org.haltos.mono\|HaltOS.profile\|widgetStyle=kvantum/d' "/etc/xdg/$f"
    done
    rm -rf /usr/share/Kvantum/HaltMono
    log "system branding removed: $(. /etc/os-release && echo "$PRETTY_NAME")"
}

case "${1:-}" in
user) install_user ;;
system) install_system ;;
undo-system) undo_system ;;
*) sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
