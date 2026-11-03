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
#   - Fetch CachyOS chwd (github.com/CachyOS/chwd) into a local clone.
#   - Show every upstream commit since the one recorded in
#     usr/share/kiro-hwd/ids/UPSTREAM, with the diff of ids/ and
#     profiles/ (the profiles are read, never copied).
#   - With --apply: copy the four NVIDIA ID lists into kiro-hwd and
#     record the new upstream commit.
#
#   Why: kiro-hwd mirrors only chwd's PCI ID lists. Every upstream
#   push gets looked at; whatever Kiro takes becomes a new kiro-hwd
#   version (bump, CHANGELOG, flow-kiro-hwd).
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
IDS_DIR="$(dirname "$SCRIPT_DIR")/usr/share/kiro-hwd/ids"
RECORD="$IDS_DIR/UPSTREAM"
LISTS=(nvidia-580 nvidia-470 nvidia-390 nouveau)

fetch_upstream() {
    log_section "Fetching CachyOS chwd into $CLONE"
    if [[ -d "$CLONE/.git" ]]; then
        git -C "$CLONE" fetch --quiet origin
        git -C "$CLONE" checkout --quiet --detach origin/HEAD
    else
        git clone --quiet --filter=blob:none "$UPSTREAM_URL" "$CLONE"
    fi
}

show_changes() {
    local synced head
    synced="$(sed -n 's/^commit=//p' "$RECORD")"
    head="$(git -C "$CLONE" rev-parse HEAD)"
    if [[ "$synced" == "$head" ]]; then
        log_success "Up to date with upstream ${head:0:7}: nothing to review"
        return 1
    fi
    log_info "Upstream commits since ${CYAN}${synced:0:7}${RESET}"
    git -C "$CLONE" log --oneline "$synced..$head"
    log_info "ids/ and profiles/ diff (profiles are Kiro's own: read, decide, never copy)"
    git -C "$CLONE" --no-pager diff --stat "$synced..$head" -- ids profiles
    git -C "$CLONE" --no-pager diff "$synced..$head" -- profiles
    local list
    for list in "${LISTS[@]}"; do
        if ! cmp -s "$CLONE/ids/$list.ids" "$IDS_DIR/$list.ids"; then
            log_warn "$list.ids changed upstream"
            diff <(tr ' ' '\n' < "$IDS_DIR/$list.ids") <(tr ' ' '\n' < "$CLONE/ids/$list.ids") || true
        fi
    done
}

apply_ids() {
    local list head
    log_section "Copying the ID lists into kiro-hwd"
    for list in "${LISTS[@]}"; do
        cp "$CLONE/ids/$list.ids" "$IDS_DIR/$list.ids"
    done
    head="$(git -C "$CLONE" rev-parse HEAD)"
    sed -i "s/^commit=.*/commit=$head/; s/^date=.*/date=$(git -C "$CLONE" log -1 --format=%cs)/" "$RECORD"
    log_warn "Now: run the unit tests, bump the version, add a CHANGELOG entry naming ${head:0:7}, then flow-kiro-hwd"
}

#####################################################################
# Main
#####################################################################
main() {
    if [[ "${1:-}" != "" && "${1:-}" != "--apply" ]]; then
        log_error "Usage: $(basename "$0") [--apply]"
        exit 1
    fi
    fetch_upstream
    if show_changes && [[ "${1:-}" == "--apply" ]]; then
        apply_ids
    fi
    log_success "$(basename "$0") done"
}

main "$@"
