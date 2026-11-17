#!/usr/bin/env bash
# Isolates claudegrid's Claude Code agents: own user, shared worktree area, sandbox, egress allowlist.
#   sudo haltos harden [--yes] [--with-docker] [--no-claudegrid|--claudegrid]   asks before every layer
#   sudo haltos harden --status | --confirm | --adopt <dir> | --reapply
#   sudo haltos harden --auto    unattended (bootstrap): no questions, firewall kept only if its self-test passes
#   sudo haltos undo-harden
# Layers and checks are called by name through run() and check().
# shellcheck disable=SC2317
set -euo pipefail

HERE=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)
AGENT=agent
GROUP=agents
AREA=/srv/agents
LIB=/usr/local/lib/haltos
NET=/usr/local/sbin/haltos-agent-net
ETC=/etc/haltos
CONF=$ETC/harden.conf
ALLOW=$ETC/agent-allowlist
AGENT_SETTINGS=$ETC/agent-settings.json
MANAGED=/etc/claude-code/managed-settings.json
SUDOERS=/etc/sudoers.d/haltos-agent
APPARMOR=/etc/apparmor.d/haltos-bwrap
APPARMOR_RLK=/etc/apparmor.d/haltos-rootlesskit
UBUNTU_BWRAP=/etc/apparmor.d/bwrap-userns-restrict
APPARMOR_DISABLE=/etc/apparmor.d/disable/bwrap-userns-restrict
BACKUP=/var/lib/haltos/harden-backup
PENDING=$BACKUP/ufw-pending
GUARD=haltos-harden-rollback
GUARD_SECONDS=300
UNITS="haltos-agent-net.service haltos-agent-net-refresh.service haltos-agent-net-refresh.timer"
DOCKER_HOSTS="registry-1.docker.io auth.docker.io production.cloudflare.docker.com"
MARK_BEGIN="# >>> haltos-harden"
MARK_END="# <<< haltos-harden"

YES=0
AUTO=0
WITH_DOCKER=0
CLAUDEGRID=1

log() { printf '\033[38;2;250;250;250m[haltos]\033[0m %s\n' "$*"; }
warn() { printf '\033[38;2;234;179;8m[haltos]\033[0m %s\n' "$*" >&2; }
die() {
    printf '\033[38;2;239;68;68m[haltos]\033[0m %s\n' "$*" >&2
    exit 1
}

need_root() { [ "$EUID" -eq 0 ] || die "this needs root: sudo haltos ${1:-harden}"; }

# Prints the plan for a layer and waits for a yes, unless --yes was given.
ask() {
    printf '\n\033[1m== %s\033[0m\n' "$1"
    shift
    local line
    for line in "$@"; do printf '   %s\n' "$line"; done
    [ "$YES" = 1 ] && return 0
    local answer
    read -r -p "   apply this step? [y/N] " answer </dev/tty
    [[ $answer == [yY]* ]]
}

# The first copy is the pre-harden original, so later runs never overwrite it.
# A missing file is recorded too, or a rerun would save harden's own copy as the original.
backup() {
    local f=$1
    if [ -e "$BACKUP$f" ] || [ -e "$BACKUP$f.absent" ]; then return 0; fi
    install -d -m700 "$BACKUP$(dirname "$f")"
    if [ -e "$f" ]; then cp -a "$f" "$BACKUP$f"; else : >"$BACKUP$f.absent"; fi
}

# Original mode of a path, recorded once so undo can put it back.
remember_mode() {
    local p=$1
    [ -e "$p" ] || return 0
    install -d -m700 "$BACKUP"
    grep -q " $p\$" "$BACKUP/modes" 2>/dev/null || printf '%s %s\n' "$(stat -c %a "$p")" "$p" >>"$BACKUP/modes"
}

load_conf() {
    MAIN_USER=""
    # shellcheck disable=SC1090
    [ -r "$CONF" ] && . "$CONF"
    if [ -z "$MAIN_USER" ] && [ -r /etc/claude-vps.conf ]; then
        # shellcheck disable=SC1091
        MAIN_USER=$(. /etc/claude-vps.conf && echo "${TARGET_USER:-}")
    fi
    [ -n "$MAIN_USER" ] || MAIN_USER=${SUDO_USER:-}
    [ -n "$MAIN_USER" ] && [ "$MAIN_USER" != root ] || die "cannot tell who the main user is, run through sudo from that account"
    MAIN_HOME=$(getent passwd "$MAIN_USER" | cut -d: -f6)
    [ -d "$MAIN_HOME" ] || die "home of $MAIN_USER not found"
}

save_conf() {
    install -d -m755 "$ETC"
    printf 'MAIN_USER=%s\nWITH_DOCKER=%s\nCLAUDEGRID=%s\n' "$MAIN_USER" "$WITH_DOCKER" "$CLAUDEGRID" >"$CONF"
}

agent_uid() { id -u "$AGENT"; }
as_agent() { runuser -u "$AGENT" -- "$@"; }
as_main() { runuser -u "$MAIN_USER" -- "$@"; }

layer_packages() {
    local pkgs="bubblewrap socat ipset jq acl curl"
    [ "$WITH_DOCKER" = 1 ] && pkgs="$pkgs uidmap rootlesskit slirp4netns"
    # shellcheck disable=SC2086
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq $pkgs >/dev/null
}

layer_user() {
    getent group "$GROUP" >/dev/null || groupadd --system "$GROUP"
    if ! id "$AGENT" >/dev/null 2>&1; then
        useradd --system --create-home --home-dir "/home/$AGENT" --shell /bin/bash --gid "$GROUP" \
            --comment "Claude Code agents (haltos harden)" "$AGENT"
    fi
    chmod 700 "/home/$AGENT"
    local g
    for g in sudo admin adm docker lxd wheel; do
        gpasswd -d "$AGENT" "$g" >/dev/null 2>&1 || true
    done
    usermod -aG "$GROUP" "$MAIN_USER"
}

layer_secrets() {
    local p
    remember_mode "$MAIN_HOME"
    chmod o-rwx "$MAIN_HOME"
    for p in "$MAIN_HOME/.ssh" "$MAIN_HOME/.config/gh" "$MAIN_HOME/.git-credentials" "$MAIN_HOME/.config/git/credentials" \
        "$MAIN_HOME/.docker" /opt/claude-vps; do
        [ -e "$p" ] || continue
        remember_mode "$p"
        case $p in
        /opt/*) chmod o-rwx "$p" ;;
        *) chmod go-rwx "$p" ;;
        esac
    done
}

acl_spec() { printf 'u:%s:rwX,u:%s:rwX,g:%s:rwX' "$MAIN_USER" "$AGENT" "$GROUP"; }

# Gives an existing tree to the agents group, so both users can write every file in it.
adopt() {
    local dir=$1
    [ -d "$dir" ] || die "$dir is not a directory"
    case $(readlink -f "$dir")/ in "$AREA"/*) ;; *) die "$dir is outside $AREA" ;; esac
    chgrp -R "$GROUP" "$dir"
    chmod -R g+rwX,o-rwx "$dir"
    find "$dir" -type d -exec chmod g+s {} + -exec setfacl -d -m "$(acl_spec),o::-" {} +
    setfacl -P -R -m "$(acl_spec)" "$dir"
    log "adopted $dir"
}

layer_area() {
    install -d -o root -g "$GROUP" -m2770 "$AREA"
    setfacl -m "$(acl_spec)" "$AREA"
    # Default ACLs grant group write regardless of each program's umask, VS Code included.
    setfacl -d -m "$(acl_spec),o::-" "$AREA"
    local d
    for d in "$AREA"/*/; do
        [ -d "$d" ] || continue
        [ "$(stat -c %G "$d")" = "$GROUP" ] || adopt "$d"
    done
    backup /etc/gitconfig
    git config --system --get-all safe.directory 2>/dev/null | grep -qxF "$AREA/*" ||
        git config --system --add safe.directory "$AREA/*"
    local name email
    name=$(as_main git config --global user.name 2>/dev/null || true)
    email=$(as_main git config --global user.email 2>/dev/null || true)
    [ -z "$name" ] || as_agent git config --global user.name "$name"
    [ -z "$email" ] || as_agent git config --global user.email "$email"
}

layer_launcher() {
    install -d -m755 "$LIB"
    install -o root -g root -m755 "$HERE/agent-launch" "$LIB/agent-launch"
    install -o root -g root -m755 "$HERE/claude-agent" /usr/local/bin/claude-agent
    local tmp
    tmp=$(mktemp)
    printf '# Managed by haltos harden. %s may start Claude Code as %s through the launcher, nothing else.\n%s ALL=(%s) NOPASSWD: %s/agent-launch\n' \
        "$MAIN_USER" "$AGENT" "$MAIN_USER" "$AGENT" "$LIB" >"$tmp"
    if ! visudo -cqf "$tmp"; then
        rm -f "$tmp"
        die "generated sudoers rule failed visudo -c, nothing installed"
    fi
    install -o root -g root -m440 "$tmp" "$SUDOERS"
    rm -f "$tmp"
    visudo -cq || die "visudo -c fails after adding $SUDOERS, remove it by hand"
}

allowlist_json() {
    sed 's/#.*//; s/[[:space:]]//g; /^$/d' "$ALLOW" | jq -R . | jq -s 'unique'
}

seed_allowlist() {
    install -d -m755 "$ETC"
    [ -f "$ALLOW" ] || install -m644 "$HERE/allowlist" "$ALLOW"
    sed -i "/^$MARK_BEGIN docker\$/,/^$MARK_END docker\$/d" "$ALLOW"
    if [ "$WITH_DOCKER" = 1 ]; then
        {
            echo "$MARK_BEGIN docker"
            # shellcheck disable=SC2086
            printf '%s\n' $DOCKER_HOSTS
            echo "$MARK_END docker"
        } >>"$ALLOW"
    fi
}

# Merged onto the pre-harden file, so an existing policy survives and reruns give the same result.
managed_merge() {
    jq -nS --argjson old "$1" --slurpfile new "$HERE/managed-settings.json" '
        ($old * $new[0]) | .permissions.deny = ((($old.permissions.deny // []) + ($new[0].permissions.deny // [])) | unique)'
}

# Older releases could save harden's own output as the "original", which undo must not restore.
managed_is_ours() { [ "$(jq -S . "$1" 2>/dev/null)" = "$(managed_merge '{}')" ]; }

layer_claude() {
    install -d -m755 /etc/claude-code
    backup "$MANAGED"
    local old='{}' tmp
    [ -f "$BACKUP$MANAGED" ] && old=$(cat "$BACKUP$MANAGED")
    tmp=$(mktemp)
    managed_merge "$old" >"$tmp"
    install -o root -g root -m644 "$tmp" "$MANAGED"

    seed_allowlist
    local docker_sock=""
    [ "$WITH_DOCKER" = 1 ] && docker_sock="/run/user/$(agent_uid)/docker.sock"
    jq --argjson domains "$(allowlist_json)" --arg sock "$docker_sock" '
        .sandbox.network.allowedDomains = $domains
        | if $sock == "" then . else
            .permissions.deny -= ["Bash(docker *)"] | .sandbox.network.allowUnixSockets = [$sock]
          end' "$HERE/agent-settings.json" >"$tmp"
    install -o root -g root -m644 "$tmp" "$AGENT_SETTINGS"
    rm -f "$tmp"
}

# Claude Code's seccomp helper opens a second user namespace inside bwrap, so test exactly that.
bwrap_works() {
    runuser -u "${1:-$AGENT}" -- bwrap --ro-bind / / --dev /dev --proc /proc --unshare-user --unshare-pid --unshare-net \
        -- unshare --user --map-root-user true 2>/dev/null
}

layer_apparmor() {
    if bwrap_works && bwrap_works "$MAIN_USER"; then
        log "the Claude Code sandbox already runs for $AGENT and $MAIN_USER, no AppArmor change needed"
        return 0
    fi
    # Ubuntu's profile moves everything bwrap starts into unpriv_bwrap, which has no capabilities for the nested namespace.
    if [ -f "$UBUNTU_BWRAP" ] && [ ! -e "$APPARMOR_DISABLE" ]; then
        log "disabling Ubuntu's $UBUNTU_BWRAP, it blocks the nested namespace"
        ln -s "$UBUNTU_BWRAP" "$APPARMOR_DISABLE"
        apparmor_parser -R "$UBUNTU_BWRAP" 2>/dev/null || true
    fi
    log "writing $APPARMOR (userns for /usr/bin/bwrap only)"
    printf 'abi <abi/4.0>,\ninclude <tunables/global>\n\nprofile bwrap /usr/bin/bwrap flags=(unconfined) {\n  userns,\n  include if exists <local/bwrap>\n}\n' >"$APPARMOR"
    apparmor_parser -r "$APPARMOR"
    bwrap_works || die "the sandbox still fails for $AGENT, see 'runuser -u $AGENT -- bwrap --ro-bind / / -- unshare -Ur true'"
}

firewall_block() {
    local family=$1
    echo "$MARK_BEGIN"
    if [ "$family" = 4 ]; then
        cat <<EOF
-A ufw-after-output -m owner --uid-owner $AGENT -p udp --dport 53 -m set --match-set haltos-agent-dns4 dst -j ACCEPT
-A ufw-after-output -m owner --uid-owner $AGENT -p tcp --dport 53 -m set --match-set haltos-agent-dns4 dst -j ACCEPT
-A ufw-after-output -m owner --uid-owner $AGENT -p tcp -m multiport --dports 80,443 -m set --match-set haltos-agent4 dst -j ACCEPT
-A ufw-after-output -m owner --uid-owner $AGENT -j REJECT
EOF
    else
        cat <<EOF
-A ufw6-after-output -m owner --uid-owner $AGENT -p tcp -m multiport --dports 80,443 -m set --match-set haltos-agent6 dst -j ACCEPT
-A ufw6-after-output -m owner --uid-owner $AGENT -j REJECT
EOF
    fi
    echo "$MARK_END"
}

# Rewrites only the haltos block, placed right before the file's last COMMIT.
write_rules() {
    local file=$1 family=$2 block tmp
    block=$(firewall_block "$family")
    tmp=$(mktemp)
    sed "/^$MARK_BEGIN\$/,/^$MARK_END\$/d" "$file" | awk -v block="$block" '
        { line[NR] = $0 } /^COMMIT$/ { last = NR }
        END { for (i = 1; i <= NR; i++) { if (i == last) print block; print line[i] } }' >"$tmp"
    install -m640 "$tmp" "$file"
    rm -f "$tmp"
}

rules_current() {
    [ "$(sed -n "/^$MARK_BEGIN\$/,/^$MARK_END\$/p" /etc/ufw/after.rules)" = "$(firewall_block 4)" ] &&
        [ "$(sed -n "/^$MARK_BEGIN\$/,/^$MARK_END\$/p" /etc/ufw/after6.rules)" = "$(firewall_block 6)" ]
}

install_net_units() {
    install -o root -g root -m755 "$HERE/haltos-agent-net" "$NET"
    # ufw fails to load rules that name a missing ipset, so the sets exist before it starts.
    printf '[Unit]\nDescription=Create the HaltOS agent egress ipsets\nDefaultDependencies=no\nBefore=ufw.service network-pre.target\nAfter=local-fs.target\n\n[Service]\nType=oneshot\nRemainAfterExit=yes\nExecStart=%s ensure\n\n[Install]\nWantedBy=ufw.service multi-user.target\n' \
        "$NET" >/etc/systemd/system/haltos-agent-net.service
    printf '[Unit]\nDescription=Resolve the HaltOS agent allowlist into ipsets\nAfter=network-online.target haltos-agent-net.service\nWants=network-online.target\n\n[Service]\nType=oneshot\nExecStart=%s refresh\n' \
        "$NET" >/etc/systemd/system/haltos-agent-net-refresh.service
    printf '[Unit]\nDescription=Refresh the HaltOS agent allowlist every 15 minutes\n\n[Timer]\nOnBootSec=1min\nOnUnitActiveSec=15min\nPersistent=true\n\n[Install]\nWantedBy=timers.target\n' \
        >/etc/systemd/system/haltos-agent-net-refresh.timer
    systemctl daemon-reload
    systemctl enable -q --now haltos-agent-net.service haltos-agent-net-refresh.timer
    "$NET" refresh
}

guard_pending() { systemctl is-active -q "$GUARD.timer" 2>/dev/null; }

confirm_firewall() {
    if guard_pending; then
        systemctl stop "$GUARD.timer" 2>/dev/null || true
        rm -rf "$PENDING"
        log "firewall rules kept, rollback cancelled"
    else
        log "no firewall change is waiting for confirmation"
    fi
}

layer_firewall() {
    if ! ufw status 2>/dev/null | grep -q '^Status: active'; then
        [ "$AUTO" = 1 ] || die "ufw is not active, enable it before hardening egress"
        warn "ufw is not active, agent egress stays open. enable ufw, then run: sudo haltos harden"
        return 0
    fi
    install_net_units
    if guard_pending; then
        warn "a firewall change is waiting for confirmation: sudo haltos harden --confirm"
        return 0
    fi
    if rules_current; then
        log "ufw rules already in place"
        return 0
    fi
    backup /etc/ufw/after.rules
    backup /etc/ufw/after6.rules
    rm -rf "$PENDING"
    install -d -m700 "$PENDING"
    cp -a /etc/ufw/after.rules /etc/ufw/after6.rules "$PENDING/"
    # The guard is armed before ufw changes, so a lockout undoes itself even if this shell dies.
    systemctl reset-failed "$GUARD.service" "$GUARD.timer" 2>/dev/null || true
    systemd-run -q --unit="$GUARD" --on-active="$GUARD_SECONDS" --timer-property=AccuracySec=1s "$NET" rollback
    log "lockout guard armed: the old rules return in $((GUARD_SECONDS / 60)) minutes unless confirmed"
    write_rules /etc/ufw/after.rules 4
    write_rules /etc/ufw/after6.rules 6
    if ! ufw reload >/dev/null; then
        warn "ufw reload failed, rolling back now"
        systemctl stop "$GUARD.timer" 2>/dev/null || true
        "$NET" rollback
        die "firewall layer not applied"
    fi
    quick_egress_report
    if [ "$AUTO" = 1 ]; then
        auto_confirm
        return 0
    fi
    if [ "$YES" = 1 ]; then
        log "confirm within $((GUARD_SECONDS / 60)) minutes from a NEW ssh session: sudo haltos harden --confirm"
        return 0
    fi
    local answer="" deadline=$((SECONDS + GUARD_SECONDS - 30)) left
    printf '   Open a NEW ssh session and an RDP connection now. Leave this one open.\n'
    printf "   Or confirm from that new ssh session: sudo haltos harden --confirm\n"
    # A stray Enter must not count as an answer, only 'keep' or 'no' end the wait.
    while left=$((deadline - SECONDS)) && [ "$left" -gt 0 ] && guard_pending; do
        answer=""
        read -r -t "$left" -p "   type 'keep' when both work, 'no' to roll back now: " answer </dev/tty || break
        case $answer in keep | no) break ;; esac
    done
    if [ "$answer" = no ]; then
        systemctl stop "$GUARD.timer" 2>/dev/null || true
        "$NET" rollback
    elif ! guard_pending; then
        if rules_current; then log "confirmed from another session"; else warn "the guard fired, the old rules are back"; fi
    elif [ "$answer" = keep ]; then
        confirm_firewall
    else
        warn "not confirmed, the rules roll back when the guard fires (or run: sudo haltos-agent-net rollback)"
    fi
}

# Unattended installs have nobody to type keep, so the rules stay only if every check that matters passes.
auto_confirm() {
    if agent_blocked && agent_npm && main_open && port_allowed "$(ssh_port)|OpenSSH"; then
        confirm_firewall
    else
        warn "firewall self-test failed, rolling back. retry later with: sudo haltos harden"
        systemctl stop "$GUARD.timer" 2>/dev/null || true
        "$NET" rollback
    fi
}

quick_egress_report() {
    local r
    r=$(as_agent curl -sS -m 8 -o /dev/null https://example.com >/dev/null 2>&1 && echo open || echo blocked)
    log "agent -> example.com: $r"
    r=$(as_agent curl -sS -m 8 -o /dev/null https://registry.npmjs.org/ >/dev/null 2>&1 && echo open || echo blocked)
    log "agent -> registry.npmjs.org: $r"
    r=$(as_main curl -sS -m 8 -o /dev/null https://example.com >/dev/null 2>&1 && echo open || echo blocked)
    log "$MAIN_USER -> example.com: $r"
}

rootless_tool() {
    command -v dockerd-rootless-setuptool.sh 2>/dev/null ||
        ls /usr/share/docker.io/contrib/dockerd-rootless-setuptool.sh 2>/dev/null || true
}

as_agent_session() {
    local uid
    uid=$(agent_uid)
    runuser -u "$AGENT" -- env XDG_RUNTIME_DIR="/run/user/$uid" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" "$@"
}

layer_docker() {
    local tool uid
    tool=$(rootless_tool)
    [ -n "$tool" ] || die "dockerd-rootless-setuptool.sh not found, install docker-ce-rootless-extras or docker.io's contrib files"
    uid=$(agent_uid)
    local f start
    for f in /etc/subuid /etc/subgid; do
        backup "$f"
        grep -q "^$AGENT:" "$f" || {
            start=$(awk -F: '{e = $2 + $3; if (e > m) m = e} END {print (m > 100000 ? m : 100000)}' "$f")
            echo "$AGENT:$start:65536" >>"$f"
        }
    done
    # rootlesskit needs a user namespace too, and Ubuntu restricts those per program.
    if ! grep -qs rootlesskit /etc/apparmor.d/* && [ -x /usr/bin/rootlesskit ]; then
        printf 'abi <abi/4.0>,\ninclude <tunables/global>\n\n"/usr/bin/rootlesskit" flags=(unconfined) {\n  userns,\n  include if exists <local/usr.bin.rootlesskit>\n}\n' >"$APPARMOR_RLK"
        apparmor_parser -r "$APPARMOR_RLK"
    fi
    loginctl enable-linger "$AGENT"
    for _ in $(seq 20); do
        [ -S "/run/user/$uid/bus" ] && break
        sleep 0.5
    done
    as_agent_session "$tool" install --skip-iptables >/dev/null
    grep -q DOCKER_HOST "/home/$AGENT/.profile" 2>/dev/null ||
        printf '\n%s docker\nexport DOCKER_HOST=unix:///run/user/%s/docker.sock\n%s docker\n' "$MARK_BEGIN" "$uid" "$MARK_END" >>"/home/$AGENT/.profile"
}

layer_packages_safety() {
    local h="/home/$AGENT"
    as_agent touch "$h/.npmrc"
    grep -qx 'ignore-scripts=true' "$h/.npmrc" || as_agent sh -c "echo ignore-scripts=true >>'$h/.npmrc'"
    as_agent install -d "$h/.config/pip"
    as_agent sh -c "printf '[global]\nrequire-virtualenv = true\n' >'$h/.config/pip/pip.conf'"
    grep -q PIP_REQUIRE_VIRTUALENV "$h/.profile" 2>/dev/null ||
        as_agent sh -c "printf '\n$MARK_BEGIN pip\nexport PIP_REQUIRE_VIRTUALENV=1\n$MARK_END pip\n' >>'$h/.profile'"
    if command -v pnpm >/dev/null; then
        as_agent pnpm config set --global minimum-release-age 1440 >/dev/null || warn "pnpm rejected minimum-release-age, check its version"
    else
        log "pnpm not installed, minimumReleaseAge not set (see the README)"
    fi
    if command -v uv >/dev/null; then
        as_agent install -d "$h/.config/uv"
        as_agent sh -c "printf 'exclude-newer = \"7 days\"\n' >'$h/.config/uv/uv.toml'"
    else
        log "uv not installed, exclude-newer not set (see the README)"
    fi
}

local_only() {
    local list="$MAIN_HOME/.config/claude-vps/local-only"
    [ -d "$MAIN_HOME/.config/claude-vps" ] || return 0
    as_main touch "$list"
    as_main sed -i "/^$MARK_BEGIN\$/,/^$MARK_END\$/d" "$list"
    [ "${1:-add}" = add ] || return 0
    printf '%s\n.config/claudegrid/config.json\n%s\n' "$MARK_BEGIN" "$MARK_END" | as_main tee -a "$list" >/dev/null
}

layer_claudegrid() {
    local dir="$MAIN_HOME/.config/claudegrid" cfg tmp
    cfg="$dir/config.json"
    as_main install -d "$dir"
    [ -s "$cfg" ] || as_main sh -c "echo '{}' >'$cfg'"
    tmp=$(as_main mktemp "$cfg.XXXXXX")
    if [ "$CLAUDEGRID" = 1 ]; then
        as_main jq '.command = "claude-agent"' "$cfg" | as_main tee "$tmp" >/dev/null
    else
        as_main jq 'if .command == "claude-agent" then del(.command) else . end' "$cfg" | as_main tee "$tmp" >/dev/null
    fi
    as_main mv "$tmp" "$cfg"
    if [ "$CLAUDEGRID" = 1 ]; then local_only add; else local_only remove; fi
}

harden() {
    need_root harden
    load_conf
    WITH_DOCKER=${ARG_DOCKER:-$WITH_DOCKER}
    CLAUDEGRID=${ARG_CLAUDEGRID:-$CLAUDEGRID}
    # Saved first, so --status and undo-harden also work after a run that stopped halfway.
    save_conf
    log "main user: $MAIN_USER, agent user: $AGENT, worktrees: $AREA"
    local skipped=()
    run() {
        local name=$1
        shift
        if ask "$@"; then "layer_$name"; else skipped+=("$name"); fi
    }
    run packages "packages" "apt install bubblewrap socat ipset jq acl curl$([ "$WITH_DOCKER" = 1 ] && echo ' uidmap rootlesskit slirp4netns')"
    run user "agent user" "create system user '$AGENT' (group '$GROUP', home /home/$AGENT mode 700, shell bash)" \
        "remove it from sudo/adm/docker/lxd if present, add $MAIN_USER to '$GROUP' (log out and in once for the group)"
    run secrets "main user's secrets" "chmod o-rwx $MAIN_HOME and /opt/claude-vps, go-rwx on ~/.ssh ~/.config/gh ~/.docker and git credentials" \
        "original modes saved to $BACKUP/modes"
    run area "shared worktree area" "create $AREA root:$GROUP 2770 with default ACLs for $MAIN_USER, $AGENT and $GROUP" \
        "adopt existing projects in it, add safe.directory=$AREA/* to /etc/gitconfig, copy your git name/email to $AGENT"
    run launcher "sudoers and launcher [touches sudoers]" "install $LIB/agent-launch and /usr/local/bin/claude-agent" \
        "write $SUDOERS: $MAIN_USER ALL=($AGENT) NOPASSWD: $LIB/agent-launch, checked with visudo -c"
    run claude "Claude Code policy" "merge the baseline into $MANAGED (root, 644): sandbox on, no unsandboxed commands, no ~/.ssh or .env* reads" \
        "write $AGENT_SETTINGS (root, 644) with the agent deny rules and domain allowlist, seed $ALLOW"
    run apparmor "AppArmor [touches AppArmor only if needed]" "test the Claude Code sandbox (bwrap with a nested user namespace) as $AGENT and $MAIN_USER" \
        "only if it fails: disable Ubuntu's $UBUNTU_BWRAP (link in /etc/apparmor.d/disable) and load $APPARMOR," \
        "which grants userns to /usr/bin/bwrap alone. kernel.apparmor_restrict_unprivileged_userns stays 1"
    run firewall "egress firewall [touches ufw]" "install $NET and ipset units, resolve $ALLOW every 15 minutes" \
        "add a uid-owner $AGENT block to /etc/ufw/after.rules and after6.rules, then ufw reload" \
        "a systemd-run timer restores the old rules in $((GUARD_SECONDS / 60)) minutes unless you confirm"
    if [ "$WITH_DOCKER" = 1 ]; then
        run docker "rootless Docker" "subuid/subgid for $AGENT, enable-linger, dockerd-rootless-setuptool.sh install as $AGENT" \
            "the system socket /var/run/docker.sock stays off limits"
    fi
    run packages_safety "package safety" "~$AGENT/.npmrc ignore-scripts=true, pip require-virtualenv, pnpm/uv release delay if installed"
    run claudegrid "claudegrid" "$([ "$CLAUDEGRID" = 1 ] && echo set || echo remove) \"command\": \"claude-agent\" in $MAIN_HOME/.config/claudegrid/config.json" \
        "list that file in claude-vps local-only"
    save_conf
    [ ${#skipped[@]} -eq 0 ] || warn "skipped: ${skipped[*]}"
    log "done. check every layer with: sudo haltos harden --status"
}

# Non-interactive pass for haltos update: refreshes files, leaves ufw rules alone unless already current.
reapply() {
    need_root harden
    [ -r "$CONF" ] || return 0
    load_conf
    layer_launcher
    layer_claude
    if [ -f /etc/systemd/system/haltos-agent-net.service ]; then
        install_net_units
        rules_current || warn "the agent firewall rules changed in this release, apply them with: sudo haltos harden"
    fi
    layer_claudegrid
    log "agent hardening re-applied"
}

STATUS_FAIL=0
check() {
    local name=$1
    shift
    if "$@" >/dev/null 2>&1; then
        printf '  \033[38;2;34;197;94mOK\033[0m    %s\n' "$name"
    else
        printf '  \033[38;2;239;68;68mFAIL\033[0m  %s\n' "$name"
        STATUS_FAIL=1
    fi
}
fails() { ! "$@"; }

agent_groups_clean() { ! id -nG "$AGENT" | tr ' ' '\n' | grep -qxE 'sudo|admin|adm|docker|lxd|wheel'; }
home_closed() { [ $(($(stat -c %a "$MAIN_HOME") % 10)) -eq 0 ] && fails as_agent ls "$MAIN_HOME"; }
ssh_keys_hidden() { fails as_agent sh -c "cat $MAIN_HOME/.ssh/id_*"; }
area_mode() { [ "$(stat -c '%G %a' "$AREA")" = "$GROUP 2770" ]; }
# No pipe into grep -q: with pipefail an early grep exit can fail the whole check.
area_acl() {
    local acl
    acl=$(getfacl -p "$AREA" 2>/dev/null)
    [[ $acl == *"default:user:$AGENT:rwx"* && $acl == *"default:user:$MAIN_USER:rwx"* ]]
}
# A real write, since rust-coreutils' test -w ignores ACLs and supplementary groups.
area_writable() {
    local u f
    for u in "$AGENT" "$MAIN_USER"; do
        f=$(runuser -u "$u" -- mktemp -p "$AREA" .haltos-probe.XXXXXX) || return 1
        rm -f "$f"
    done
}
sudoers_ok() { [ "$(stat -c '%U %a' "$SUDOERS")" = "root 440" ] && visudo -cqf "$SUDOERS" && visudo -cq; }
launcher_ok() { [ -x "$LIB/agent-launch" ] && [ -x /usr/local/bin/claude-agent ] && sudo -l -U "$MAIN_USER" | grep -qF "($AGENT) NOPASSWD: $LIB/agent-launch"; }
owned_644() { [ "$(stat -c '%U %a' "$1")" = "root 644" ]; }
managed_ok() { owned_644 "$MANAGED" && jq -e '.sandbox.enabled == true and .sandbox.allowUnsandboxedCommands == false' "$MANAGED"; }
agent_settings_ok() {
    owned_644 "$AGENT_SETTINGS" && jq -e '.sandbox.enabled == true and .sandbox.allowUnsandboxedCommands == false
        and (.sandbox.network.allowedDomains | length > 0) and any(.permissions.deny[]; . == "Bash(sudo *)")' "$AGENT_SETTINGS"
}
pkgs_ok() { dpkg -s bubblewrap socat ipset >/dev/null; }
userns_sysctl_kept() { [ "$(sysctl -n kernel.apparmor_restrict_unprivileged_userns 2>/dev/null || echo 1)" = 1 ]; }
sets_filled() { [ "$(ipset list haltos-agent4 2>/dev/null | sed -n '/^Members:/,$p' | wc -l)" -gt 1 ]; }
rules_loaded() { iptables -S ufw-after-output | grep -q -- "--uid-owner $(agent_uid)" && ip6tables -S ufw6-after-output | grep -q -- "--uid-owner $(agent_uid)"; }
agent_blocked() { fails as_agent curl -sS -m 8 -o /dev/null https://example.com; }
agent_npm() { as_agent curl -sS -m 15 -o /dev/null https://registry.npmjs.org/; }
main_open() { as_main curl -sS -m 15 -o /dev/null https://example.com; }
no_guard() { fails guard_pending; }
# ufw lists a rule by port or app profile. With Tailscale, claude-vps opens everything on tailscale0 instead.
port_allowed() { ufw status | grep -qE "^(($1)(/tcp)?|Anywhere on tailscale0)[[:space:]]+(ALLOW|LIMIT)"; }
ssh_port() {
    local p
    p=$(sshd -T 2>/dev/null | awk '/^port /{print $2; exit}')
    echo "${p:-22}"
}
rdp_port() {
    local p=""
    # shellcheck disable=SC1091
    [ -r /etc/claude-vps.conf ] && p=$(. /etc/claude-vps.conf && echo "${RDP_PORT:-}")
    echo "${p:-3389}"
}
no_system_docker() { fails as_agent docker -H unix:///var/run/docker.sock ps; }
rootless_docker() { as_agent_session env DOCKER_HOST="unix:///run/user/$(agent_uid)/docker.sock" docker ps; }
npmrc_ok() { grep -qx 'ignore-scripts=true' "/home/$AGENT/.npmrc"; }
pip_ok() { grep -q 'require-virtualenv = true' "/home/$AGENT/.config/pip/pip.conf"; }
claudegrid_ok() {
    local cmd
    cmd=$(jq -r '.command // ""' "$MAIN_HOME/.config/claudegrid/config.json" 2>/dev/null)
    if [ "$CLAUDEGRID" = 1 ]; then [ "$cmd" = claude-agent ]; else [ "$cmd" != claude-agent ]; fi
}

status() {
    need_root "harden --status"
    [ -r "$CONF" ] || die "haltos harden has not run on this machine"
    load_conf
    echo "agent isolation for $MAIN_USER"
    check "user $AGENT exists" id "$AGENT"
    check "$AGENT is not in sudo/adm/docker/lxd" agent_groups_clean
    check "$AGENT cannot sudo (sudo -n true fails)" fails as_agent sudo -n true
    check "$AGENT cannot list $MAIN_HOME" home_closed
    check "$AGENT cannot read $MAIN_HOME/.ssh/id_*" ssh_keys_hidden
    check "$AREA is $GROUP 2770" area_mode
    check "$AREA has default ACLs for $AGENT and $MAIN_USER" area_acl
    check "$AREA is writable by $AGENT and $MAIN_USER" area_writable
    check "sudoers $SUDOERS is root 440 and passes visudo -c" sudoers_ok
    check "$MAIN_USER may run only the launcher as $AGENT" launcher_ok
    check "bubblewrap, socat and ipset installed" pkgs_ok
    check "$MANAGED is root 644 and enforces the sandbox" managed_ok
    check "$AGENT_SETTINGS is root 644 with deny rules and allowlist" agent_settings_ok
    check "Claude Code sandbox (bwrap + nested userns) runs as $AGENT" bwrap_works
    check "Claude Code sandbox runs as $MAIN_USER" bwrap_works "$MAIN_USER"
    check "userns restriction sysctl left on" userns_sysctl_kept
    check "allowlist ipset is filled" sets_filled
    check "allowlist refresh timer active" systemctl is-active -q haltos-agent-net-refresh.timer
    check "uid-owner rules loaded (IPv4 and IPv6)" rules_loaded
    check "no unconfirmed firewall change pending" no_guard
    check "$AGENT -> https://example.com blocked" agent_blocked
    check "$AGENT -> https://registry.npmjs.org/ works" agent_npm
    check "$MAIN_USER -> https://example.com works" main_open
    check "ufw allows ssh port $(ssh_port) (directly or on tailscale0)" port_allowed "$(ssh_port)|OpenSSH"
    check "ufw allows rdp port $(rdp_port) (directly or on tailscale0)" port_allowed "$(rdp_port)"
    check "$AGENT cannot use the system Docker socket" no_system_docker
    if [ "$WITH_DOCKER" = 1 ]; then
        check "rootless Docker answers for $AGENT" rootless_docker
    else
        check "$AGENT has no docker (docker ps fails)" fails as_agent docker ps
    fi
    check "npm ignore-scripts for $AGENT" npmrc_ok
    check "pip require-virtualenv for $AGENT" pip_ok
    check "claudegrid command $([ "$CLAUDEGRID" = 1 ] && echo is claude-agent || echo left alone)" claudegrid_ok
    return $STATUS_FAIL
}

restore_modes() {
    [ -f "$BACKUP/modes" ] || return 0
    local mode path
    while read -r mode path; do
        [ -e "$path" ] && chmod "$mode" "$path"
    done <"$BACKUP/modes"
    rm -f "$BACKUP/modes"
}

undo() {
    need_root undo-harden
    load_conf
    log "undoing agent hardening for $MAIN_USER"
    # claudegrid first, so no new pane starts as an agent that is about to vanish.
    if [ -f "$MAIN_HOME/.config/claudegrid/config.json" ]; then
        CLAUDEGRID=0
        layer_claudegrid
    fi
    local_only remove

    if grep -q "^$MARK_BEGIN\$" /etc/ufw/after.rules /etc/ufw/after6.rules 2>/dev/null; then
        sed -i "/^$MARK_BEGIN\$/,/^$MARK_END\$/d" /etc/ufw/after.rules /etc/ufw/after6.rules
        ufw reload >/dev/null || warn "ufw reload failed, check /etc/ufw/after*.rules"
    fi
    systemctl stop "$GUARD.timer" 2>/dev/null || true
    rm -rf "$PENDING"
    local u
    for u in $UNITS; do systemctl disable -q --now "$u" 2>/dev/null || true; done
    for u in $UNITS; do rm -f "/etc/systemd/system/$u"; done
    systemctl daemon-reload
    for s in haltos-agent4 haltos-agent6 haltos-agent-dns4; do ipset destroy "$s" 2>/dev/null || true; done

    rm -f "$SUDOERS" /usr/local/bin/claude-agent "$LIB/agent-launch" "$NET" "$AGENT_SETTINGS" "$ALLOW" "$CONF"
    rmdir "$LIB" 2>/dev/null || true
    if [ -f "$BACKUP$MANAGED" ] && ! managed_is_ours "$BACKUP$MANAGED"; then
        install -o root -g root -m644 "$BACKUP$MANAGED" "$MANAGED"
    else
        rm -f "$MANAGED" "$BACKUP$MANAGED" "$BACKUP$MANAGED.absent"
        rmdir /etc/claude-code 2>/dev/null || true
    fi
    local p
    for p in "$APPARMOR" "$APPARMOR_RLK"; do
        [ -f "$p" ] || continue
        apparmor_parser -R "$p" 2>/dev/null || true
        rm -f "$p"
    done
    if [ -L "$APPARMOR_DISABLE" ]; then
        rm -f "$APPARMOR_DISABLE"
        apparmor_parser -r "$UBUNTU_BWRAP" || warn "could not reload $UBUNTU_BWRAP"
    fi
    git config --system --fixed-value --unset-all safe.directory "$AREA/*" 2>/dev/null || true

    if id "$AGENT" >/dev/null 2>&1; then
        local uid
        uid=$(agent_uid)
        local tool
        tool=$(rootless_tool)
        if [ -n "$tool" ] && [ -S "/run/user/$uid/docker.sock" ]; then
            as_agent_session "$tool" uninstall -f >/dev/null 2>&1 || true
        fi
        loginctl disable-linger "$AGENT" 2>/dev/null || true
        pkill -u "$AGENT" 2>/dev/null || true
        sleep 1
        userdel -r "$AGENT" 2>/dev/null || userdel "$AGENT"
        sed -i "/^$AGENT:/d" /etc/subuid /etc/subgid
    fi
    # Project code is never deleted: it goes back to the main user with plain permissions.
    if [ -d "$AREA" ]; then
        setfacl -P -R -b "$AREA"
        chown -R "$MAIN_USER:$(id -gn "$MAIN_USER")" "$AREA"
        find "$AREA" -type d -exec chmod g-s {} +
        log "kept $AREA, now owned by $MAIN_USER"
    fi
    gpasswd -d "$MAIN_USER" "$GROUP" >/dev/null 2>&1 || true
    groupdel "$GROUP" 2>/dev/null || true
    restore_modes
    log "agent hardening removed. backups stay in $BACKUP. packages (bubblewrap, socat, ipset) stay installed."
}

ARG_DOCKER=""
ARG_CLAUDEGRID=""
action=harden
adopt_dir=""
while [ $# -gt 0 ]; do
    case $1 in
    --yes | -y) YES=1 ;;
    --auto)
        YES=1
        AUTO=1
        ;;
    --with-docker) ARG_DOCKER=1 ;;
    --no-claudegrid) ARG_CLAUDEGRID=0 ;;
    --claudegrid) ARG_CLAUDEGRID=1 ;;
    --status) action=status ;;
    --confirm) action=confirm ;;
    --reapply) action=reapply ;;
    --undo | undo) action=undo ;;
    --adopt)
        action=adopt
        adopt_dir=${2:?--adopt needs a directory}
        shift
        ;;
    *)
        sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'
        exit 1
        ;;
    esac
    shift
done

# Commands run as the agent fail inside a directory it cannot enter, such as the main user's home.
[ -z "$adopt_dir" ] || adopt_dir=$(readlink -f -- "$adopt_dir")
cd /

case $action in
harden) harden ;;
status) status ;;
confirm)
    need_root "harden --confirm"
    confirm_firewall
    ;;
reapply) reapply ;;
undo) undo ;;
adopt)
    need_root "harden --adopt"
    load_conf
    adopt "$adopt_dir"
    ;;
esac
