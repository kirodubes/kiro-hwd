#!/bin/bash
set -euo pipefail
#####################################################################
# Author    : Erik Dubois
# Website   : https://kiroproject.be
#####################################################################
#
#   DO NOT JUST RUN THIS. EXAMINE AND JUDGE. RUN AT YOUR OWN RISK.
#
#   Purpose:
#   - Fetch CachyOS chwd into the local review clone and compare its
#     HEAD with the commit in usr/share/kiro-hwd/ids/UPSTREAM.
#   - When upstream moved: send a desktop notification saying how many
#     commits and whether ids/, profiles/ or only code changed.
#   - Changes nothing in kiro-hwd; the review stays tools/sync-chwd.sh.
#
#   Why: every upstream chwd push gets reviewed, so the push has to be
#   noticed. Run daily by tools/systemd/kiro-hwd-chwd-check.timer.
#
#####################################################################

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

#####################################################################
# Colors
#####################################################################
if command -v tput >/dev/null 2>&1 && [[ -t 1 ]]; then
    RED="$(tput setaf 1)"
    GREEN="$(tput setaf 2)"
    YELLOW="$(tput setaf 3)"
    BLUE="$(tput setaf 4)"
    CYAN="$(tput setaf 6)"
    RESET="$(tput sgr0)"
else
    RED="" GREEN="" YELLOW="" BLUE="" CYAN="" RESET=""
fi

#####################################################################
# Logging
#####################################################################
log_section() {
    echo
    echo "${GREEN}############################################################################${RESET}"
    echo "$1"
    echo "${GREEN}############################################################################${RESET}"
    echo
}

log_info() {
    echo
    echo "${BLUE}############################################################################${RESET}"
    echo "$1"
    echo "${BLUE}############################################################################${RESET}"
    echo
}

log_warn() {
    echo
    echo "${YELLOW}############################################################################${RESET}"
    echo "$1"
    echo "${YELLOW}############################################################################${RESET}"
    echo
}

log_error() {
    echo
    echo "${RED}############################################################################${RESET}"
    echo "$1"
    echo "${RED}############################################################################${RESET}"
    echo
}

log_success() {
    echo
    echo "${GREEN}############################################################################${RESET}"
    echo "$1"
    echo "${GREEN}############################################################################${RESET}"
    echo
}

#####################################################################
# Error handling
#####################################################################
on_error() {
    echo "${RED}ERROR on line $1: $2${RESET}"
    sleep 10
}
trap 'on_error "$LINENO" "$BASH_COMMAND"' ERR

#####################################################################
# Functions
#####################################################################
UPSTREAM_URL="https://github.com/CachyOS/chwd.git"
CLONE="${CHWD_CLONE:-$HOME/Public/chwd-check}"
RECORD="$(dirname "$SCRIPT_DIR")/usr/share/kiro-hwd/ids/UPSTREAM"

fetch_upstream() {
    log_section "Fetching CachyOS chwd into $CLONE"
    if [[ -d "$CLONE/.git" ]]; then
        git -C "$CLONE" fetch --quiet origin
    else
        git clone --quiet --filter=blob:none "$UPSTREAM_URL" "$CLONE"
    fi
}

# Prints which areas changed between two commits: "ID lists", "profiles", or "code only".
changed_areas() {
    local areas=()
    git -C "$CLONE" diff --quiet "$1..$2" -- ids || areas+=("ID lists")
    git -C "$CLONE" diff --quiet "$1..$2" -- profiles || areas+=("profiles")
    if (( ${#areas[@]} == 0 )); then
        echo "code only"
    else
        printf '%s\n' "${areas[@]}" | paste -sd, - | sed 's/,/, /g'
    fi
}

notify() {
    if command -v notify-send >/dev/null 2>&1; then
        notify-send --app-name=kiro-hwd --icon=dialog-information "$1" "$2" || true
    fi
}

#####################################################################
# Main
#####################################################################
main() {
    local synced head count areas
    fetch_upstream
    synced="$(sed -n 's/^commit=//p' "$RECORD")"
    head="$(git -C "$CLONE" rev-parse origin/HEAD)"
    if [[ "$synced" == "$head" ]]; then
        log_success "chwd unchanged since ${synced:0:7}"
        exit 0
    fi
    count="$(git -C "$CLONE" rev-list --count "$synced..$head")"
    areas="$(changed_areas "$synced" "$head")"
    log_warn "chwd moved: $count commit(s) since ${CYAN}${synced:0:7}${RESET} -> ${head:0:7} ($areas)"
    git -C "$CLONE" log --oneline "$synced..$head"
    notify "CachyOS chwd moved: $count new commit(s)" \
        "${synced:0:7} -> ${head:0:7}, changed: $areas. Review with kiro-hwd/tools/sync-chwd.sh"
    log_success "$(basename "$0") done"
}

main "$@"
