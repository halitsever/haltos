#!/usr/bin/env bash
# Runs `install.sh system` twice and then `undo-system` on a throwaway Ubuntu, checking each step.
# Only for a disposable container or VM: it rewrites the OS identity. CI runs it in ubuntu:26.04.
set -euo pipefail

# shellcheck source=tests/lib.sh
. "$(dirname "$(readlink -f "$0")")/lib.sh"
[ "$EUID" -eq 0 ] || {
    echo "run as root inside a throwaway container" >&2
    exit 1
}

release=$(cat "$REPO/VERSION")
codename=$(sed -n 's/^HALTOS_CODENAME="\(.*\)"$/\1/p' "$REPO/install.sh")
want="HaltOS ${release%.*} ($codename)"
skel_lines() { grep -c '^# HaltOS$' /etc/skel/.bashrc || true; }
diversions() { dpkg-divert --list | grep -cE '/usr/lib/os-release|/etc/lsb-release|/etc/issue' || true; }

echo "== dependencies"
apt-get update -qq
apt-get install -y -qq curl gpg lsb-release libkf6config-bin >/dev/null
# A container has no systemd, so the update timer is recorded instead of started.
shim=$(mktemp -d)
printf '#!/bin/sh\necho "$*" >>%s/systemctl.log\n' "$shim" >"$shim/systemctl"
chmod +x "$shim/systemctl"
export PATH="$shim:$PATH"

orig=$(mktemp -d)
cp -a /usr/lib/os-release /etc/lsb-release /etc/issue /etc/skel/.bashrc "$orig/"
ubuntu_id=$(. /usr/lib/os-release && echo "$VERSION_ID")
motd_exec=$(find /etc/update-motd.d -maxdepth 1 -type f -perm -u+x -printf '%f\n' | sort)

echo "== install.sh system"
"$REPO/install.sh" system

same "lsb_release says $want" "$(lsb_release -ds)" "$want"
same "PRETTY_NAME" "$(. /etc/os-release && echo "$PRETTY_NAME")" "$want"
same "ID stays ubuntu" "$(. /etc/os-release && echo "$ID")" ubuntu
same "VERSION_ID stays Ubuntu's" "$(. /etc/os-release && echo "$VERSION_ID")" "$ubuntu_id"
same "three diversions" "$(diversions)" 3
check "/etc/issue names HaltOS" grep -q "^$want" /etc/issue
check "originals kept beside the diversions" cmp "$orig/os-release" /usr/lib/os-release.ubuntu
check "login banner runs" sh /etc/update-motd.d/00-haltos
check "Ubuntu's banners are off" test ! -x /etc/update-motd.d/00-header
check "look and feel is the default" grep -q '^LookAndFeelPackage=org.haltos.mono$' /etc/xdg/kdeglobals
check "kvantum theme installed" test -f /usr/share/Kvantum/HaltMono/HaltMono.kvconfig
same "installed VERSION" "$(cat /usr/share/haltos/VERSION)" "$release"
check "fastfetch banner matches VERSION" grep -q "v${release%.*} // $codename" /usr/share/haltos/fastfetch/haltos.txt
check "update timer enabled" grep -q 'enable -q --now haltos-update-check.timer' "$shim/systemctl.log"
check "VS Code installed" command -v code
same "one VS Code source" "$(find /etc/apt/sources.list.d -name '*vscode*' | wc -l)" 1
check "apt sees no duplicate sources" bash -c '! apt-get update 2>&1 | grep -q "configured multiple times"'
same "new users get the prompt once" "$(skel_lines)" 1

echo "== install.sh system again"
"$REPO/install.sh" system >/dev/null
same "still three diversions" "$(diversions)" 3
check "originals untouched by the second run" cmp "$orig/os-release" /usr/lib/os-release.ubuntu
same "prompt still added once" "$(skel_lines)" 1

echo "== install.sh undo-system"
"$REPO/install.sh" undo-system
for f in os-release lsb-release issue; do
    case $f in os-release) live=/usr/lib/os-release ;; *) live=/etc/$f ;; esac
    check "$live restored" cmp "$orig/$f" "$live"
    check "${live}.ubuntu removed" test ! -e "$live.ubuntu"
done
check "/etc/skel/.bashrc restored" cmp "$orig/.bashrc" /etc/skel/.bashrc
same "no diversions left" "$(diversions)" 0
same "banners as before" "$(find /etc/update-motd.d -maxdepth 1 -type f -perm -u+x -printf '%f\n' | sort)" "$motd_exec"
check "login banner removed" test ! -e /etc/update-motd.d/00-haltos
check "/usr/share/haltos removed" test ! -e /usr/share/haltos
check "no HaltOS keys in /etc/xdg" bash -c '! grep -rqs "HaltMono\|org.haltos.mono\|HaltOS.profile" /etc/xdg'
check "/etc/haltos.conf removed" test ! -e /etc/haltos.conf

finish
