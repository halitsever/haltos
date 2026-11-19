#!/usr/bin/env bash
# HaltOS installer.
#   ./install.sh user            theme the current account (no root needed)
#   ./install.sh refresh         re-apply user settings without a backup or restart (sync hook)
#   ./install.sh undo-user       restore the KDE config saved before the first user install
#   sudo ./install.sh system     OS identity, MOTD, login and boot themes, defaults for new users
#   sudo ./install.sh update     newest release (--edge: follow main), claude-code-vps too, then system and refresh
#   ./install.sh version         installed version, channel and whether a newer release exists
#   sudo ./install.sh undo-system
set -euo pipefail

HERE=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)
HALTOS_RELEASE=$(cat "$HERE/VERSION" 2>/dev/null || echo 1.0.0)
HALTOS_VER=${HALTOS_RELEASE%.*}
HALTOS_CODENAME="SIGKILL"
LNF=org.haltos.mono
MOTD_OFF="00-header 10-help-text 50-motd-news 50-landscape-sysinfo 90-updates-available 91-contract-ua-esm-status"
# Theme files HaltOS owns on claude-code-vps machines: sync must not undo them, capture must not publish them.
HALTOS_OWNED=".config/kdeglobals .config/kdedefaults/ .config/kwinrc .config/ksplashrc .config/konsolerc
    .config/plasma-org.kde.plasma.desktop-appletsrc .config/gtk-3.0/settings.ini .config/gtk-4.0/settings.ini
    .config/gtkrc .config/gtkrc-2.0 .local/share/color-schemes/HaltMono.colors .local/share/konsole/HaltOS.profile
    .local/share/konsole/HaltMono.colorscheme .local/share/plasma/look-and-feel/org.haltos.mono/
    .config/plasmarc .config/plasmashellrc .local/share/plasma/desktoptheme/haltos/"
USER_CONFIGS="kdeglobals kwinrc breezerc plasmarc plasmashellrc ksplashrc konsolerc plasma-org.kde.plasma.desktop-appletsrc
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
    install -d "$share/color-schemes" "$share/konsole" "$share/wallpapers" "$share/plasma/look-and-feel" "$share/plasma/desktoptheme" \
        "$share/icons" "$share/haltos/fastfetch"
    install -m644 "$HERE/plasma/color-schemes/HaltMono.colors" "$share/color-schemes/"
    install -m644 "$HERE/konsole/HaltOS.profile" "$HERE/konsole/HaltMono.colorscheme" "$share/konsole/"
    rm -rf "$share/wallpapers/HaltOS" "$share/plasma/look-and-feel/$LNF" "$share/plasma/desktoptheme/haltos"
    cp -r "$HERE/plasma/desktoptheme/haltos" "$share/plasma/desktoptheme/"
    cp -r "$HERE/branding/wallpapers/HaltOS" "$share/wallpapers/"
    cp -r "$HERE/plasma/look-and-feel/$LNF" "$share/plasma/look-and-feel/"
    cp -r "$HERE/branding/icons/hicolor" "$share/icons/"
    install -m644 "$HERE/system/fastfetch/haltos.txt" "$share/haltos/fastfetch/"
    install -m644 "$HERE/shell/haltos-prompt.sh" "$HERE/gtk/haltos-adw.css" "$HERE/VERSION" "$share/haltos/"
}

gtk_import() {
    local dir=$1
    install -d "$dir"
    install -m644 "$HERE/gtk/haltos-adw.css" "$dir/"
    [ -f "$dir/gtk.css" ] || : >"$dir/gtk.css"
    grep -q haltos-adw.css "$dir/gtk.css" || printf "\n@import 'haltos-adw.css';\n" >>"$dir/gtk.css"
}

# Writes every per-user HaltOS setting. Shared by install, refresh and the claude-code-vps sync hook.
# The agents app is per user: its menu entry and tray autostart point into this account's share dir.
install_agents() {
    local share=$1 conf=$2 dir="$1/haltos/agents"
    rm -rf "$dir"
    install -d "$share/haltos" "$share/applications" "$conf/autostart"
    cp -r "$HERE/agents" "$dir"
    rm -rf "$dir/tests"
    find "$dir" -name __pycache__ -prune -exec rm -rf {} +
    local entry='[Desktop Entry]\nType=Application\nName=HaltOS Agents\nGenericName=Claude Code agents\nComment=Manage your Claude Code agents\nExec=%s\nIcon=haltos-agents\nTerminal=false\nCategories=Development;Utility;\nKeywords=claude;ai;agent;\n'
    # shellcheck disable=SC2059
    printf "$entry" "$dir/haltos-agents" >"$share/applications/haltos-agents.desktop"
    # shellcheck disable=SC2059
    printf "${entry}X-KDE-autostart-phase=2\n" "$dir/haltos-agents --tray" >"$conf/autostart/haltos-agents.desktop"
}

apply_user_config() {
    local share=$1 conf=$2
    copy_assets "$share"
    install_agents "$share" "$conf"

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
    kwriteconfig6 --file plasmarc --group Theme --key name haltos
    # Translucent rather than adaptive, so the panel stays see-through with maximized windows too.
    local panel
    grep -oE '^\[PlasmaViews\]\[Panel [0-9]+\]$' "$conf/plasmashellrc" 2>/dev/null | grep -oE '[0-9]+' | while read -r panel; do
        kwriteconfig6 --file plasmashellrc --group PlasmaViews --group "Panel $panel" --key panelOpacity 2
    done || true
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
    claim_local_only
}

# Rewrites only the HaltOS block of claude-vps's local-only list, leaving the user's own entries alone.
claim_local_only() {
    local list="$conf/claude-vps/local-only" p
    drop_local_only
    {
        echo "# >>> haltos"
        for p in $HALTOS_OWNED; do echo "$p"; done
        echo "# <<< haltos"
    } >>"$list"
}

drop_local_only() {
    local list="$conf/claude-vps/local-only"
    [ -f "$list" ] && sed -i '/^# >>> haltos$/,/^# <<< haltos$/d' "$list"
    return 0
}

# Takes the blank line written before the hook too, so undo leaves .bashrc as it was.
drop_prompt_hook() {
    [ -f "$1" ] && sed -i -z 's/\n\n# HaltOS\n[^\n]*//; s/# HaltOS\n[^\n]*\n\?//' "$1"
    return 0
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
    install_sync_hook
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
        "$share/wallpapers/HaltOS" "$share/plasma/look-and-feel/$LNF" "$share/plasma/desktoptheme/haltos" "$share/haltos" "$conf/Kvantum/HaltMono" \
        "$conf/gtk-3.0/haltos-adw.css" "$conf/gtk-4.0/haltos-adw.css"
    rm -f "$conf/claude-vps/post-apply.d/50-haltos" "$conf/autostart/haltos-firstrun.desktop" \
        "$conf/autostart/haltos-agents.desktop" "$share/applications/haltos-agents.desktop"
    drop_local_only
    find "$share/icons/hicolor" -name 'haltos-*' -delete 2>/dev/null || true
    drop_prompt_hook "$HOME/.bashrc"
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

# Microsoft's own repository, so apt upgrade keeps VS Code on the latest release.
install_vscode() {
    command -v code >/dev/null && return 0
    log "installing VS Code"
    [ -f /usr/share/keyrings/microsoft.gpg ] ||
        # packages.microsoft.com answers bursts with 429, which curl retries on its own.
        curl -fsSL --retry 5 --retry-delay 10 https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor --yes -o /usr/share/keyrings/microsoft.gpg
    printf 'Types: deb\nURIs: https://packages.microsoft.com/repos/code\nSuites: stable\nComponents: main\nArchitectures: amd64,arm64,armhf\nSigned-By: /usr/share/keyrings/microsoft.gpg\n' \
        >/etc/apt/sources.list.d/vscode.sources
    # The package would otherwise add a second copy of the same repository.
    echo "code code/add-microsoft-repo boolean false" | debconf-set-selections
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq code >/dev/null
}

install_system() {
    [ "$EUID" -eq 0 ] || die "system mode needs root: sudo $0 system"
    need dpkg-divert apt-get kwriteconfig6 curl gpg

    log "installing fastfetch, kvantum and the agents app's Qt modules"
    apt-get install -y -qq fastfetch qt6-style-kvantum python3-pyside6.qtqml python3-pyside6.qtquick \
        python3-pyside6.qtwidgets python3-pyte qml6-module-org-kde-kirigami qml6-module-qtquick-dialogs libglib2.0-bin >/dev/null
    install_vscode

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
    kwriteconfig6 --file /etc/xdg/plasmarc --group Theme --key name haltos
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
    install_update_check
    log "system branding installed. reconnect via SSH to see the new MOTD."
}

CONF=/etc/haltos.conf
STATE=/var/lib/haltos

channel() {
    local c=stable
    # shellcheck disable=SC1090  # written at runtime on the server, not part of the repo
    [ -r "$CONF" ] && c=$(. "$CONF" && echo "${CHANNEL:-stable}")
    echo "$c"
}

# Newest vX.Y.Z on GitHub, read without fetching the repository.
latest_release() {
    git -C "$HERE" ls-remote --tags --refs origin 'v*' 2>/dev/null | sed 's|.*refs/tags/v||' | sort -V | tail -1
}

newer() { [ -n "$2" ] && [ "$1" != "$2" ] && [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | tail -1)" = "$2" ]; }

show_version() {
    local latest
    latest=$(latest_release)
    echo "HaltOS $HALTOS_RELEASE ($HALTOS_CODENAME), $(channel) channel"
    if newer "$HALTOS_RELEASE" "$latest"; then
        echo "HaltOS $latest is available: sudo haltos update"
    else
        echo "up to date"
    fi
}

# Run daily by haltos-update-check.timer; the login banner reads the result.
check_update() {
    install -d "$STATE"
    latest_release >"$STATE/latest.tmp" && mv "$STATE/latest.tmp" "$STATE/latest"
}

update_all() {
    [ "$EUID" -eq 0 ] || die "update needs root: sudo haltos update"
    local ch old target
    ch=$(channel)
    case "${1:-}" in
    --edge) ch=edge ;;
    --stable) ch=stable ;;
    esac
    old=$HALTOS_RELEASE
    [ -z "$(git -C "$HERE" status --porcelain --untracked-files=no)" ] || die "$HERE has local changes, commit or stash them first"
    git -C "$HERE" fetch -q --tags origin
    if [ "$ch" = edge ]; then
        git -C "$HERE" checkout -q main
        git -C "$HERE" pull -q --ff-only
    else
        target=$(git -C "$HERE" tag -l 'v*' | sed 's/^v//' | sort -V | tail -1)
        [ -n "$target" ] || die "no HaltOS releases found"
        git -C "$HERE" checkout -q "v$target"
    fi
    printf 'CHANNEL=%s\n' "$ch" >"$CONF"
    # The checkout rewrote this script while bash may still be reading it, so the rest runs in the new copy.
    exec "$HERE/install.sh" finish-update "$old"
}

finish_update() {
    [ "$EUID" -eq 0 ] || die "update needs root: sudo haltos update"
    local old=${1:-unknown} user=""
    if command -v claude-vps >/dev/null; then
        log "updating claude-code-vps"
        claude-vps update
    fi
    "$HERE/install.sh" system
    [ -r /etc/claude-vps.conf ] && user=$(. /etc/claude-vps.conf && echo "${TARGET_USER:-}")
    if [ -n "$user" ]; then
        runuser -l "$user" -c "dbus-run-session -- '$HERE/install.sh' refresh"
    else
        log "no claude-vps user recorded, run 'haltos refresh' as your desktop user"
    fi
    check_update || true
    if [ "$old" = "$HALTOS_RELEASE" ]; then
        log "HaltOS $HALTOS_RELEASE is up to date"
    else
        log "HaltOS $old -> $HALTOS_RELEASE"
        awk -v v="$HALTOS_RELEASE" '$0 ~ "^## "v {on=1; next} /^## / {on=0} on' "$HERE/CHANGELOG.md"
    fi
}

install_update_check() {
    printf '[Unit]\nDescription=Check for a newer HaltOS release\nAfter=network-online.target\nWants=network-online.target\n\n[Service]\nType=oneshot\nExecStart=%s/install.sh check-update\n' \
        "$HERE" >/etc/systemd/system/haltos-update-check.service
    printf '[Unit]\nDescription=Check for a newer HaltOS release every day\n\n[Timer]\nOnBootSec=5min\nOnUnitActiveSec=1d\nRandomizedDelaySec=1h\nPersistent=true\n\n[Install]\nWantedBy=timers.target\n' \
        >/etc/systemd/system/haltos-update-check.timer
    systemctl daemon-reload
    systemctl enable -q --now haltos-update-check.timer
    [ -f "$CONF" ] || printf 'CHANNEL=stable\n' >"$CONF"
    check_update || true
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
    drop_prompt_hook /etc/skel/.bashrc
    for f in kdeglobals ksplashrc konsolerc plasmarc Kvantum/kvantum.kvconfig; do
        if [ -f "/etc/xdg/$f" ]; then
            sed -i '/HaltMono\|org.haltos.mono\|HaltOS.profile\|widgetStyle=kvantum\|^name=haltos$/d' "/etc/xdg/$f"
        fi
    done
    rm -f /etc/xdg/breezerc
    rm -rf /usr/share/Kvantum/HaltMono /usr/share/sddm/themes/haltos /usr/share/haltos
    systemctl disable -q --now haltos-update-check.timer 2>/dev/null || true
    rm -rf /etc/systemd/system/haltos-update-check.service /etc/systemd/system/haltos-update-check.timer "$CONF" "$STATE"
    systemctl daemon-reload
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
update) update_all "${2:-}" ;;
finish-update) finish_update "${2:-}" ;;
check-update) check_update ;;
version | --version | -v) show_version ;;
undo-system) undo_system ;;
*)
    sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
