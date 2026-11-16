#!/usr/bin/env bash
# HaltOS installer.
#   ./install.sh user            theme the current account (no root needed)
#   ./install.sh refresh         re-apply user settings without a backup or restart (sync hook)
#   ./install.sh undo-user       restore the KDE config saved before the first user install
#   sudo ./install.sh system     OS identity, MOTD, login and boot themes, defaults for new users
#   sudo ./install.sh update     pull HaltOS, re-run system, refresh the claude-vps user
#   sudo ./install.sh undo-system
set -euo pipefail

HERE=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)
HALTOS_VER="1.0"
HALTOS_CODENAME="SIGKILL"
LNF=org.haltos.mono
MOTD_OFF="00-header 10-help-text 50-motd-news 50-landscape-sysinfo 90-updates-available 91-contract-ua-esm-status"
USER_CONFIGS="kdeglobals kwinrc breezerc plasmarc ksplashrc konsolerc plasma-org.kde.plasma.desktop-appletsrc
    Kvantum/kvantum.kvconfig gtk-3.0/gtk.css gtk-4.0/gtk.css fastfetch/config.jsonc"

log() { printf '\033[38;2;250;250;250m[haltos]\033[0m %s\n' "$*"; }
die() {
    printf '\033[38;2;239;68;68m[haltos]\033[0m %s\n' "$*" >&2
    exit 1
}

need() {
    local missing=()
    for c in "$@"; do command -v "$c" >/dev/null || missing+=("$c"); done
    [ ${#missing[@]} -eq 0 ] || die "missing: ${missing[*]}. HaltOS needs Ubuntu with KDE Plasma 6."
}

copy_assets() {
    local share=$1
    install -d "$share/color-schemes" "$share/konsole" "$share/wallpapers" "$share/plasma/look-and-feel" \
        "$share/icons" "$share/haltos/fastfetch"
    install -m644 "$HERE/plasma/color-schemes/HaltMono.colors" "$share/color-schemes/"
    install -m644 "$HERE/konsole/HaltOS.profile" "$HERE/konsole/HaltMono.colorscheme" "$share/konsole/"
    rm -rf "$share/wallpapers/HaltOS" "$share/plasma/look-and-feel/$LNF"
    cp -r "$HERE/branding/wallpapers/HaltOS" "$share/wallpapers/"
    cp -r "$HERE/plasma/look-and-feel/$LNF" "$share/plasma/look-and-feel/"
    cp -r "$HERE/branding/icons/hicolor" "$share/icons/"
    install -m644 "$HERE/system/fastfetch/haltos.txt" "$share/haltos/fastfetch/"
    install -m644 "$HERE/shell/haltos-prompt.sh" "$HERE/gtk/haltos-adw.css" "$share/haltos/"
}

gtk_import() {
    local dir=$1
    install -d "$dir"
    install -m644 "$HERE/gtk/haltos-adw.css" "$dir/"
    [ -f "$dir/gtk.css" ] || : >"$dir/gtk.css"
    grep -q haltos-adw.css "$dir/gtk.css" || printf "\n@import 'haltos-adw.css';\n" >>"$dir/gtk.css"
}

# Writes every per-user HaltOS setting. Shared by install, refresh and the claude-code-vps sync hook.
apply_user_config() {
    local share=$1 conf=$2
    copy_assets "$share"

    install -d "$conf/fastfetch"
    sed "s|/usr/share/haltos|$share/haltos|" "$HERE/system/fastfetch/config.jsonc" >"$conf/fastfetch/config.jsonc"
    grep -q 'haltos-prompt.sh' "$HOME/.bashrc" 2>/dev/null ||
        printf '\n# HaltOS\n[ -f "%s/haltos/haltos-prompt.sh" ] && . "%s/haltos/haltos-prompt.sh"\n' \
            "$share" "$share" >>"$HOME/.bashrc"

    local mono="JetBrains Mono" tail=",-1,5,400,0,0,0,0,0,0,0,0,0,0,1"
    kwriteconfig6 --file kdeglobals --group General --key fixed "$mono,11$tail"
    kwriteconfig6 --file kdeglobals --group General --key font "$mono,10$tail"
    kwriteconfig6 --file kdeglobals --group General --key menuFont "$mono,10$tail"
    kwriteconfig6 --file kdeglobals --group General --key toolBarFont "$mono,9$tail"
    kwriteconfig6 --file kdeglobals --group General --key smallestReadableFont "$mono,8$tail"
    kwriteconfig6 --file kdeglobals --group WM --key activeFont "$mono,10,-1,5,700,0,0,0,0,0,0,0,0,0,0,1"
    kwriteconfig6 --file kdeglobals --group KDE --key LookAndFeelPackage "$LNF"
    kwriteconfig6 --file kdeglobals --group KDE --key widgetStyle kvantum
    if [ -d /usr/share/icons/breeze-dark ]; then
        kwriteconfig6 --file kdeglobals --group Icons --key Theme breeze-dark
    fi
    kwriteconfig6 --file ksplashrc --group KSplash --key Engine KSplashQML
    kwriteconfig6 --file ksplashrc --group KSplash --key Theme "$LNF"
    kwriteconfig6 --file konsolerc --group "Desktop Entry" --key DefaultProfile HaltOS.profile
    "$HERE/plasma/scripts/windeco.sh"

    rm -rf "$conf/Kvantum/HaltMono"
    install -d "$conf/Kvantum"
    cp -r "$HERE/kvantum/HaltMono" "$conf/Kvantum/"
    kwriteconfig6 --file "$conf/Kvantum/kvantum.kvconfig" --group General --key theme HaltMono

    gtk_import "$conf/gtk-3.0"
    gtk_import "$conf/gtk-4.0"
    if command -v gsettings >/dev/null; then
        gsettings set org.gnome.desktop.interface color-scheme prefer-dark || true
        gsettings set org.gnome.desktop.interface font-name "$mono 10" || true
        gsettings set org.gnome.desktop.interface monospace-font-name "$mono 11" || true
    fi

    # Plasma keys images by path, so regenerated assets at the same path would otherwise stay stale.
    rm -f "$HOME/.cache/icon-cache.kcache"
}

user_dirs() {
    share=${XDG_DATA_HOME:-$HOME/.local/share}
    conf=${XDG_CONFIG_HOME:-$HOME/.config}
}

# claude-code-vps runs these after a sync, so its dotfiles never wash the theme out.
install_sync_hook() {
    [ -d /opt/claude-vps ] || command -v claude-vps >/dev/null || return 0
    install -d "$conf/claude-vps/post-apply.d"
    printf '#!/bin/sh
exec "%s/install.sh" refresh
' "$HERE" >"$conf/claude-vps/post-apply.d/50-haltos"
    chmod +x "$conf/claude-vps/post-apply.d/50-haltos"
}

install_user() {
    [ "$EUID" -ne 0 ] || die "user mode runs as your normal account, not root"
    need kwriteconfig6 qdbus6 plasma-apply-colorscheme plasma-apply-wallpaperimage
    local share conf
    user_dirs
    local backup="$HOME/.haltos-backup"
    install -d "$backup"
    # The first backup is the pre-HaltOS state that undo-user restores, so it is never overwritten.
    local snap="$backup/kde-config-original.tar.gz"
    [ ! -f "$snap" ] || snap="$backup/kde-config-$(date +%Y%m%d-%H%M%S).tar.gz"
    # shellcheck disable=SC2086
    (cd "$conf" && tar czf "$snap" --ignore-failed-read $USER_CONFIGS 2>/dev/null) || true
    log "config backup: $snap"

    apply_user_config "$share" "$conf"
    install_sync_hook

    if [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
        plasma-apply-colorscheme HaltMono >/dev/null || true
        qdbus6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript \
            "$(cat "$HERE/plasma/scripts/panel.js")" >/dev/null || true
        plasma-apply-wallpaperimage "$share/wallpapers/HaltOS" >/dev/null || true
        qdbus6 org.kde.KWin /KWin reconfigure >/dev/null || true
        kquitapp6 plasmashell >/dev/null 2>&1 || true
        setsid -f kstart plasmashell >/dev/null 2>&1 || true
        log "applied to the running session. log out once so every app picks up the new style."
    else
        # Without a session Qt has no display, but the colour scheme still has to land in kdeglobals.
        QT_QPA_PLATFORM=offscreen plasma-apply-colorscheme HaltMono >/dev/null 2>&1 || true
        queue_firstrun
        log "no graphical session found, panel and wallpaper apply at first desktop login"
    fi
}

# Panel and wallpaper live inside plasmashell, so without one they wait for the next desktop login.
queue_firstrun() {
    install -d "$conf/autostart"
    printf '[Desktop Entry]\nType=Application\nName=HaltOS first run\nExec=%s/install.sh firstrun\nNoDisplay=true\nX-KDE-autostart-phase=2\n' \
        "$HERE" >"$conf/autostart/haltos-firstrun.desktop"
}

refresh_user() {
    [ "$EUID" -ne 0 ] || die "refresh runs as your normal account, not root"
    need kwriteconfig6 plasma-apply-colorscheme
    local share conf
    user_dirs
    apply_user_config "$share" "$conf"
    QT_QPA_PLATFORM=offscreen plasma-apply-colorscheme HaltMono >/dev/null 2>&1 || true
    # A synced panel file drops the wallpaper and start icon. A live shell takes them now, else next login does.
    if qdbus6 org.kde.plasmashell /PlasmaShell >/dev/null 2>&1; then
        qdbus6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript \
            "$(cat "$HERE/plasma/scripts/panel.js")" >/dev/null || true
        plasma-apply-wallpaperimage "$share/wallpapers/HaltOS" >/dev/null || true
    else
        queue_firstrun
    fi
    log "settings re-applied. log out and back in to see them."
}

firstrun_user() {
    local share conf
    user_dirs
    for _ in $(seq 30); do
        qdbus6 org.kde.plasmashell /PlasmaShell >/dev/null 2>&1 && break
        sleep 1
    done
    qdbus6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript \
        "$(cat "$HERE/plasma/scripts/panel.js")" >/dev/null || true
    plasma-apply-wallpaperimage "$share/wallpapers/HaltOS" >/dev/null || true
    plasma-apply-colorscheme HaltMono >/dev/null || true
    rm -f "$conf/autostart/haltos-firstrun.desktop"
}

undo_user() {
    [ "$EUID" -ne 0 ] || die "undo-user runs as your normal account, not root"
    local share=${XDG_DATA_HOME:-$HOME/.local/share}
    local conf=${XDG_CONFIG_HOME:-$HOME/.config}
    local snap="$HOME/.haltos-backup/kde-config-original.tar.gz"
    [ -f "$snap" ] || die "no pre-HaltOS backup at $snap"
    local saved
    saved=$(tar tzf "$snap")
    (cd "$conf" && tar xzf "$snap")
    # Files absent from the backup did not exist before HaltOS, except the GTK css KDE writes itself.
    for f in $USER_CONFIGS; do
        grep -qx "$f" <<<"$saved" && continue
        case $f in
        gtk-*/gtk.css) [ -f "$conf/$f" ] && sed -i "/haltos-adw.css/d" "$conf/$f" ;;
        *) rm -f "${conf:?}/$f" ;;
        esac
    done
    rm -rf "$share/color-schemes/HaltMono.colors" "$share/konsole/HaltOS.profile" "$share/konsole/HaltMono.colorscheme" \
        "$share/wallpapers/HaltOS" "$share/plasma/look-and-feel/$LNF" "$share/haltos" "$conf/Kvantum/HaltMono" \
        "$conf/gtk-3.0/haltos-adw.css" "$conf/gtk-4.0/haltos-adw.css"
    rm -f "$conf/claude-vps/post-apply.d/50-haltos" "$conf/autostart/haltos-firstrun.desktop"
    find "$share/icons/hicolor" -name 'haltos-*' -delete 2>/dev/null || true
    sed -i '/^# HaltOS$/,+1d' "$HOME/.bashrc"
    rm -f "$HOME/.cache/icon-cache.kcache"
    log "restored $snap. log out and back in to finish."
}

write_os_release() {
    (
        # shellcheck disable=SC1091
        . /usr/lib/os-release.ubuntu
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

diverted() { [ "$(dpkg-divert --truename "$1")" != "$1" ]; }

# Copy then divert without rename, so the essential file is never missing even for a moment.
divert() {
    diverted "$1" && return 0
    cp -a "$1" "$2"
    dpkg-divert --local --no-rename --divert "$2" --add "$1" >/dev/null
}

undivert() {
    diverted "$1" || return 0
    local saved
    saved=$(dpkg-divert --truename "$1")
    cp -a "$saved" "$1"
    dpkg-divert --local --no-rename --remove "$1" >/dev/null
    rm -f "$saved"
}

install_system() {
    [ "$EUID" -eq 0 ] || die "system mode needs root: sudo $0 system"
    need dpkg-divert apt-get kwriteconfig6

    log "installing fastfetch and kvantum"
    apt-get install -y -qq fastfetch qt6-style-kvantum >/dev/null

    copy_assets /usr/share
    gtk-update-icon-cache -qf /usr/share/icons/hicolor 2>/dev/null || true

    # ID stays ubuntu so apt, PPAs and vendor install scripts keep working.
    divert /usr/lib/os-release /usr/lib/os-release.ubuntu
    write_os_release
    divert /etc/lsb-release /etc/lsb-release.ubuntu
    sed "s|^DISTRIB_DESCRIPTION=.*|DISTRIB_DESCRIPTION=\"HaltOS $HALTOS_VER ($HALTOS_CODENAME)\"|" \
        /etc/lsb-release.ubuntu >/etc/lsb-release
    divert /etc/issue /etc/issue.ubuntu
    printf 'HaltOS %s (%s) \\n \\l\n\n' "$HALTOS_VER" "$HALTOS_CODENAME" >/etc/issue
    log "os identity: $(. /etc/os-release && echo "$PRETTY_NAME")"

    install -m755 "$HERE/system/motd/00-haltos" /etc/update-motd.d/00-haltos
    for f in $MOTD_OFF; do
        if [ -x "/etc/update-motd.d/$f" ]; then chmod -x "/etc/update-motd.d/$f"; fi
    done

    install -d /etc/xdg/fastfetch
    install -m644 "$HERE/system/xdg/kcm-about-distrc" /etc/xdg/
    install -m644 "$HERE/system/fastfetch/config.jsonc" /etc/xdg/fastfetch/
    kwriteconfig6 --file /etc/xdg/kdeglobals --group KDE --key LookAndFeelPackage "$LNF"
    kwriteconfig6 --file /etc/xdg/kdeglobals --group KDE --key widgetStyle kvantum
    kwriteconfig6 --file /etc/xdg/kdeglobals --group General --key ColorScheme HaltMono
    kwriteconfig6 --file /etc/xdg/ksplashrc --group KSplash --key Theme "$LNF"
    kwriteconfig6 --file /etc/xdg/konsolerc --group "Desktop Entry" --key DefaultProfile HaltOS.profile
    "$HERE/plasma/scripts/windeco.sh" /etc/xdg/
    rm -rf /usr/share/Kvantum/HaltMono
    cp -r "$HERE/kvantum/HaltMono" /usr/share/Kvantum/
    kwriteconfig6 --file /etc/xdg/Kvantum/kvantum.kvconfig --group General --key theme HaltMono
    gtk_import /etc/skel/.config/gtk-3.0
    gtk_import /etc/skel/.config/gtk-4.0
    grep -q haltos-prompt.sh /etc/skel/.bashrc ||
        printf '\n# HaltOS\n[ -f /usr/share/haltos/haltos-prompt.sh ] && . /usr/share/haltos/haltos-prompt.sh\n' \
            >>/etc/skel/.bashrc

    if [ -d /usr/share/sddm/themes ]; then
        rm -rf /usr/share/sddm/themes/haltos
        cp -r "$HERE/sddm/haltos" /usr/share/sddm/themes/
        install -d /etc/sddm.conf.d
        printf '[Theme]\nCurrent=haltos\n' >/etc/sddm.conf.d/90-haltos.conf
        log "sddm theme installed (used when sddm is the active display manager)"
    fi

    if command -v plymouth-set-default-theme >/dev/null; then
        rm -rf /usr/share/plymouth/themes/haltos
        cp -r "$HERE/plymouth/haltos" /usr/share/plymouth/themes/
        # Rebuilding the initramfs only matters when the kernel actually shows a splash.
        if grep -qw splash /proc/cmdline; then
            plymouth-set-default-theme -R haltos
        else
            plymouth-set-default-theme haltos
            log "plymouth theme set; add 'splash' to the kernel command line to see it"
        fi
    fi
    log "system branding installed. reconnect via SSH to see the new MOTD."
}

# Bootstrapped servers: newest HaltOS from git, system layer, then the workstation user's settings.
update_all() {
    [ "$EUID" -eq 0 ] || die "update needs root: sudo haltos update"
    git -C "$HERE" pull -q --ff-only
    "$HERE/install.sh" system
    local user=""
    [ -r /etc/claude-vps.conf ] && user=$(. /etc/claude-vps.conf && echo "${TARGET_USER:-}")
    if [ -n "$user" ]; then
        runuser -l "$user" -c "dbus-run-session -- '$HERE/install.sh' refresh"
    else
        log "no claude-vps user recorded, run 'haltos refresh' as your desktop user"
    fi
}

undo_system() {
    [ "$EUID" -eq 0 ] || die "undo needs root: sudo $0 undo-system"
    undivert /usr/lib/os-release
    undivert /etc/lsb-release
    undivert /etc/issue
    rm -f /etc/update-motd.d/00-haltos /etc/xdg/kcm-about-distrc /etc/xdg/fastfetch/config.jsonc \
        /etc/sddm.conf.d/90-haltos.conf
    for f in $MOTD_OFF; do
        if [ -f "/etc/update-motd.d/$f" ]; then chmod +x "/etc/update-motd.d/$f"; fi
    done
    sed -i '/^# HaltOS$/,+1d' /etc/skel/.bashrc
    for f in kdeglobals ksplashrc konsolerc Kvantum/kvantum.kvconfig; do
        if [ -f "/etc/xdg/$f" ]; then
            sed -i '/HaltMono\|org.haltos.mono\|HaltOS.profile\|widgetStyle=kvantum/d' "/etc/xdg/$f"
        fi
    done
    rm -f /etc/xdg/breezerc
    rm -rf /usr/share/Kvantum/HaltMono /usr/share/sddm/themes/haltos /usr/share/haltos
    if command -v plymouth-set-default-theme >/dev/null && [ -d /usr/share/plymouth/themes/haltos ]; then
        plymouth-set-default-theme --reset
        rm -rf /usr/share/plymouth/themes/haltos
    fi
    log "system branding removed: $(. /etc/os-release && echo "$PRETTY_NAME")"
}

case "${1:-}" in
user) install_user ;;
refresh) refresh_user ;;
firstrun) firstrun_user ;;
undo-user) undo_user ;;
system) install_system ;;
update) update_all ;;
undo-system) undo_system ;;
*)
    sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
