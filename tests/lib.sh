# shellcheck shell=bash
# Shared by the tests in this directory. They change the machine they run on, so they insist on a container.

export REPO
REPO=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)
export DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8

[ -f /.dockerenv ] || [ -n "${CI:-}" ] || [ "${HALTOS_TEST_FORCE:-}" = 1 ] || {
    echo "refusing to run outside a container, set HALTOS_TEST_FORCE=1 on a throwaway VM" >&2
    exit 1
}

fails=0
ok() { printf '  ok    %s\n' "$1"; }
bad() {
    printf '  FAIL  %s\n' "$1"
    fails=$((fails + 1))
}
check() {
    local name=$1
    shift
    if "$@" >/dev/null 2>&1; then ok "$name"; else bad "$name"; fi
}
same() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1: expected '$3', got '$2'"; fi; }

finish() {
    echo
    if [ "$fails" -eq 0 ]; then
        echo "all checks passed"
    else
        echo "$fails check(s) failed"
        exit 1
    fi
}
