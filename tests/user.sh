#!/usr/bin/env bash
# Runs `install.sh user`, a second install, `refresh` and `undo-user` for a fresh account on a throwaway Ubuntu.
# Started as root it installs Plasma's tools and a `dev` user, then runs the checks as that user.
set -euo pipefail

# shellcheck source=tests/lib.sh
. "$(dirname "$(readlink -f "$0")")/lib.sh"

if [ "$EUID" -eq 0 ]; then
    echo "== dependencies"
    apt-get update -qq
    apt-get install -y -qq --no-install-recommends plasma-workspace qdbus-qt6 libkf6config-bin >/dev/null
    id dev >/dev/null 2>&1 || useradd -m -s /bin/bash dev
    # The sync hook and local-only list are only written on claude-code-vps machines.
    install -d /opt/claude-vps
    rm -rf /opt/haltos
    cp -r "$REPO" /opt/haltos
    chmod -R a+rX /opt/haltos
    exec runuser -u dev -- env HOME=/home/dev /opt/haltos/tests/user.sh
fi

conf=$HOME/.config
share=$HOME/.local/share
haltos=$REPO/install.sh
read_kde() { kreadconfig6 --file "$conf/$1" --group "$2" --key "$3"; }
hooks() { grep -c '^# HaltOS$' "$HOME/.bashrc" || true; }
blocks() { grep -c '^# >>> haltos$' "$conf/claude-vps/local-only" || true; }

# An account that already has some KDE settings and its own claude-vps entries.
install -d "$conf/claude-vps"
printf '[General]\nfixed=Hack,10,-1,5,400,0,0,0,0,0,0,0,0,0,0,1\n\n[Mine]\nkeep=yes\n' >"$conf/kdeglobals"
printf '.config/mine\n' >"$conf/claude-vps/local-only"
orig=$(mktemp -d)
cp -a "$HOME/.bashrc" "$conf/kdeglobals" "$conf/claude-vps/local-only" "$orig/"
# An extension of their own, and a HaltMono left behind by an older HaltOS.
vsext=$HOME/.vscode/extensions
install -d "$vsext/someone.theirs-1.0.0" "$vsext/haltos.haltmono-0.0.1"
haltmono=$vsext/haltos.haltmono-$(sed -n 's/^ *"version": "\(.*\)",$/\1/p' "$REPO/vscode/haltmono/package.json")
vsthemes() { find "$vsext" -maxdepth 1 -name 'haltos.haltmono-*' | wc -l; }

# Leftovers of the HaltOS Agents app an older HaltOS installed.
install -d "$share/haltos/agents" "$conf/systemd/user/graphical-session.target.wants" "$conf/autostart"
touch "$share/haltos/agents/haltos-agents" "$conf/systemd/user/haltos-agents.service" "$conf/autostart/haltos-agents.desktop"
ln -sf ../haltos-agents.service "$conf/systemd/user/graphical-session.target.wants/haltos-agents.service"

echo "== install.sh user"
"$haltos" user
backup=$HOME/.haltos-backup/kde-config-original.tar.gz
check "pre-HaltOS backup saved" test -f "$backup"
backup_sum=$(sha256sum "$backup")
same "look and feel" "$(read_kde kdeglobals KDE LookAndFeelPackage)" org.haltos.mono
same "widget style" "$(read_kde kdeglobals KDE widgetStyle)" kvantum
same "colour scheme" "$(read_kde kdeglobals General ColorScheme)" HaltMono
same "fixed font" "$(read_kde kdeglobals General fixed | cut -d, -f1)" "JetBrains Mono"
same "own settings kept" "$(read_kde kdeglobals Mine keep)" yes
same "kvantum theme" "$(read_kde Kvantum/kvantum.kvconfig General theme)" HaltMono
same "konsole profile" "$(read_kde konsolerc 'Desktop Entry' DefaultProfile)" HaltOS.profile
same "splash theme" "$(read_kde ksplashrc KSplash Theme)" org.haltos.mono
same "plasma theme" "$(read_kde plasmarc Theme name)" haltos
check "global theme installed" test -f "$share/plasma/look-and-feel/org.haltos.mono/metadata.json"
check "wallpaper installed" test -d "$share/wallpapers/HaltOS/contents/images"
check "fastfetch reads the user's banner" grep -q "$share/haltos" "$conf/fastfetch/config.jsonc"
check "libadwaita palette imported" grep -q haltos-adw.css "$conf/gtk-4.0/gtk.css"
same "prompt hooked once" "$(hooks)" 1
check "panel queued for the first login" test -f "$conf/autostart/haltos-firstrun.desktop"
check "sync hook installed" test -x "$conf/claude-vps/post-apply.d/50-haltos"
same "one local-only block" "$(blocks)" 1
check "own local-only entry kept" grep -qx '.config/mine' "$conf/claude-vps/local-only"
check "grid launcher in app menu" grep -qx "Exec=claudegrid" "$share/applications/haltos-agents.desktop"
check "grid launcher keeps the HaltOS icon" grep -qx "Icon=haltos-agents" "$share/applications/haltos-agents.desktop"
check "grid launcher icon" test -f "$share/icons/hicolor/scalable/apps/haltos-agents.svg"
check "old agents app removed" test ! -e "$share/haltos/agents"
check "old agents service removed" test ! -e "$conf/systemd/user/haltos-agents.service"
check "old agents service link removed" test ! -L "$conf/systemd/user/graphical-session.target.wants/haltos-agents.service"
check "old agents autostart removed" test ! -e "$conf/autostart/haltos-agents.desktop"
check "vscode theme installed" test -f "$haltmono/themes/haltmono-color-theme.json"
check "vscode opens with HaltMono" grep -q '"workbench.colorTheme": "HaltMono"' "$haltmono/package.json"
same "one vscode theme" "$(vsthemes)" 1
check "older vscode theme removed" test ! -e "$vsext/haltos.haltmono-0.0.1"

echo "== install.sh user again"
"$haltos" user >/dev/null
same "first backup untouched" "$(sha256sum "$backup")" "$backup_sum"
same "prompt still hooked once" "$(hooks)" 1
same "still one local-only block" "$(blocks)" 1
same "still one vscode theme" "$(vsthemes)" 1

echo "== install.sh refresh"
"$haltos" refresh >/dev/null
same "prompt hooked once after refresh" "$(hooks)" 1
same "one local-only block after refresh" "$(blocks)" 1
same "look and feel after refresh" "$(read_kde kdeglobals KDE LookAndFeelPackage)" org.haltos.mono
check "grid launcher kept after refresh" grep -qx "Exec=claudegrid" "$share/applications/haltos-agents.desktop"

echo "== install.sh undo-user"
"$haltos" undo-user
check ".bashrc restored" cmp "$orig/.bashrc" "$HOME/.bashrc"
check "kdeglobals restored" cmp "$orig/kdeglobals" "$conf/kdeglobals"
check "local-only restored" cmp "$orig/local-only" "$conf/claude-vps/local-only"
for f in kwinrc ksplashrc plasmarc konsolerc breezerc Kvantum/kvantum.kvconfig fastfetch/config.jsonc; do
    check "$f removed, it did not exist before" test ! -e "$conf/$f"
done
check "no HaltOS import left in gtk.css" bash -c "! grep -qs haltos-adw.css '$conf/gtk-3.0/gtk.css' '$conf/gtk-4.0/gtk.css'"
check "HaltOS data removed" test ! -e "$share/haltos"
check "global theme removed" test ! -e "$share/plasma/look-and-feel/org.haltos.mono"
check "kvantum theme removed" test ! -e "$conf/Kvantum/HaltMono"
check "first-run entry removed" test ! -e "$conf/autostart/haltos-firstrun.desktop"
check "sync hook removed" test ! -e "$conf/claude-vps/post-apply.d/50-haltos"
check "grid launcher removed" test ! -e "$share/applications/haltos-agents.desktop"
same "no HaltOS icons left" "$(find "$share/icons/hicolor" -name 'haltos-*' 2>/dev/null | wc -l)" 0
same "vscode theme removed" "$(vsthemes)" 0
check "own vscode extension kept" test -d "$vsext/someone.theirs-1.0.0"

finish
