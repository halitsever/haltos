#!/usr/bin/env bash
# Screenshots an app on a temporary empty virtual desktop, so windows on the real desktop never leak.
# Usage: [SHOT_WINDOW=1] [SHOT_DELAY=s] clean-shot.sh OUT.png [command...]   (no command: just the desktop)
set -euo pipefail
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
out=$1
shift

vdm() { qdbus6 org.kde.KWin /VirtualDesktopManager "$@"; }
prop() { vdm org.freedesktop.DBus.Properties."$1" org.kde.KWin.VirtualDesktopManager "${@:2}"; }
pause() { python3 -c "import time, sys; time.sleep(float(sys.argv[1]))" "$1"; }

home=$(prop Get current)
count=$(prop Get count)
vdm org.kde.KWin.VirtualDesktopManager.createDesktop "$count" haltos-shot
pause 0.5
shot=$(qdbus6 --literal org.kde.KWin /VirtualDesktopManager org.freedesktop.DBus.Properties.Get \
    org.kde.KWin.VirtualDesktopManager desktops | grep -oE '[0-9a-f-]{36}", "haltos-shot' | cut -d'"' -f1)

pid=""
cleanup() {
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
    prop Set current "$home" >/dev/null
    pause 0.3
    vdm org.kde.KWin.VirtualDesktopManager.removeDesktop "$shot"
}
trap cleanup EXIT

prop Set current "$shot" >/dev/null
pause 1
if [ $# -gt 0 ]; then
    "$@" >/dev/null 2>&1 &
    pid=$!
    pause "${SHOT_DELAY:-5}"
fi

# SHOT_WINDOW=1 crops to the launched app's own window, matched by PID so same-class windows elsewhere never match.
target=overlay
if [ -n "${SHOT_WINDOW:-}" ] && [ -n "$pid" ]; then
    for w in $(xwininfo -root -tree | awk '$1 ~ /^0x/ && !/ 1x1\+/ && !/ 3x3\+/ {print $1}'); do
        if [ "$(xprop -id "$w" _NET_WM_PID 2>/dev/null | awk '{print $3}')" = "$pid" ]; then
            target=$w
            break
        fi
    done
fi
python3 -I "$here/xshot.py" "$out" "$target"
