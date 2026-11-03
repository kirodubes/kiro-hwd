# CHANGELOG

## 2026.11.03

### What Changed
- **New: kiro-hwd v1**, Kiro's own NVIDIA driver picker, to replace CachyOS chwd in the installer. It takes only
  chwd's PCI ID lists; the profiles, packages and install steps are Kiro's choices.
- `kiro-hwd detect` shows the GPUs, the chosen profile and why; `kiro-hwd install [--dry-run]` installs it.
- Profiles: `nvidia-open` (Turing and newer, from Arch `extra`), `nvidia-580xx` (Maxwell/Pascal/Volta, chaotic-aur
  first, cachyos as fallback), `nouveau` (Kepler and older: nothing installed, like upstream's 470xx drop at
  b5278a3 and Kiro's newer-machines rule). Laptops with an iGPU add `nvidia-prime` + `switcheroo-control`.
- `tools/sync-chwd.sh` follows upstream: shows every chwd commit since the last sync, `--apply` copies the ID lists.

### Technical Details
- Python 3, standard library only (`tomllib`); GPUs come from `/sys/bus/pci/devices`, so `lspci` output is not
  parsed. With several NVIDIA cards the newest driver wins (profiles.toml runs oldest to newest).
- Packages install as explicit `repo/package` names in the order core/extra/multilib → chaotic-aur → cachyos.
  When [cachyos] is commented out (installed Kiro), a temporary pacman.conf with it enabled is used; the full
  `-Syu` runs first with the system's own config, so no cachyos rebuild replaces a base package.
- `lib32-*` only when [multilib] is enabled: chwd's profiles always asked for them, but Kiro ships [multilib] off.
- `<pkgbase>-headers` for every installed kernel. Early KMS through `/etc/mkinitcpio.conf.d/10-kiro-hwd.conf`; the
  kms hook is dropped on desktops only (as chwd 1.23); no `cachyos-drm-awaiter`, no RTD3 workaround (upstream
  removed it, #283). `nvidia-powerd` is left off in v1.
- Stops instead of removing another installed NVIDIA branch; `/var/lib/kiro-hwd/state` records the result.
- 15 unit tests with fake sysfs trees (RTX 2060, Ampere, GTX 1050 Ti laptop, AMD iGPU laptop, GT 620M, VM, two
  cards). `KIRO_HWD_SYSFS` / `KIRO_HWD_CHASSIS` let a dry run on any box act as another machine.

### Files Modified
- `usr/bin/kiro-hwd`, `usr/lib/kiro-hwd/kiro_hwd/{__init__,cli,detect,profiles,repos,apply}.py`
- `usr/share/kiro-hwd/profiles.toml`, `usr/share/kiro-hwd/ids/{nvidia-580,nvidia-470,nvidia-390,nouveau}.ids`,
  `usr/share/kiro-hwd/ids/UPSTREAM`
- `usr/share/man/man8/kiro-hwd.8`, `tools/sync-chwd.sh`, `tests/test_kiro_hwd.py`
- `README.md`, `CHANGELOG.md`, `CLAUDE.md`, `LICENSE`, `ruff.toml`, `setup.sh`, `up.sh`, `.gitignore`
