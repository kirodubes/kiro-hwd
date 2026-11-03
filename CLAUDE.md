# CLAUDE.md

kiro-hwd: Kiro's own NVIDIA driver picker (replaces CachyOS chwd in the installer). Package in nemesis_repo,
build dir `~/KIRO-PKG-BUILD-APPS/kiro-hwd`, flow `flow-kiro-hwd`. Design and decisions:
`~/Insync/Kiro/Kiro-HQ/STUDIES/KIRO-HWD-STUDY.md`.

## Rules

- **Independent of chwd.** Only `usr/share/kiro-hwd/ids/*.ids` come from upstream, via `tools/sync-chwd.sh`.
  Never copy chwd profiles or hooks; read them, decide, and write Kiro's own choice into `profiles.toml`.
- **Every upstream push is reviewed.** `tools/sync-chwd.sh` (review) → decide → `--apply` → tests → version bump
  + CHANGELOG entry naming the upstream commit → Erik runs `flow-kiro-hwd`.
- **Repo order:** Arch repos, then chaotic-aur, then cachyos (fallback). Never edit `/etc/pacman.conf`; cachyos is
  reached through a temporary copy. The `-Syu` always runs with the system's own config first.
- Python 3 standard library only; no new runtime dependencies.
- `profiles.toml` runs oldest driver to newest: `choose()` relies on that order when a machine has two NVIDIA cards.
- Output stays English: it lands in the Calamares log and in support posts.
- Before done: `ruff check .` and `python3 -m unittest discover -s tests`.

## Test without NVIDIA hardware

`KIRO_HWD_SYSFS=<fake /sys/bus/pci/devices tree> KIRO_HWD_CHASSIS=10 usr/bin/kiro-hwd install --dry-run`
resolves against the real repos of the box it runs on.
