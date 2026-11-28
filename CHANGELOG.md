# CHANGELOG

## 2026.11.28

### What Changed
- **NVIDIA 620: no more black screen at the Wayland login with two or more screens.** NVIDIA's 620.70.06 and
  620.73.04 drivers lose the first frame when a Wayland compositor (Hyprland, KWin, …) takes over the screens: the
  desktop runs, the screens stay black. NVIDIA tracks it as bug 7126445
  ([open-gpu-kernel-modules #1553](https://github.com/NVIDIA/open-gpu-kernel-modules/issues/1553)); no fixed driver
  yet. While `nvidia-utils` is a 620.x build, kiro-hwd now writes `/etc/modprobe.d/11-kiro-hwd-flip.conf` with
  `options nvidia_modeset opportunistic_flip_sync=0`, and removes it again with any other driver.
- Found on riker (RTX 2060, two screens) with a fresh KIROTUX Hyprland DMS v26.11.28 install: black at the first
  login. With the option: 4 of 4 boots + logins clean, 3 suspends clean, 10 screen sleep/wake cycles with the picture
  back every time. Promised to KiroTux buyers in kiro-discussions #137.

### Technical Details
- `apply.py`: `nvidia_utils_version()` (`pacman -Q nvidia-utils`), `needs_flip_fix()` (`FLIP_BRANCHES = ("620.",)`;
  drop the branch once NVIDIA ships a fix in it), `write_flip_fix()` returns the file and whether it changed.
- New command `kiro-hwd flip-fix`; when the file changed and nvidia is in the initramfs (`10-kiro-hwd.conf`), it runs
  `mkinitcpio -P`, because the modprobe options are baked into the initramfs then. `kiro-hwd install` writes the file
  too, and `detect`/`install` print the reason.
- New pacman hook `usr/share/libalpm/hooks/60-kiro-hwd-flip.hook` on install, upgrade and removal of `nvidia-utils`.
  Version-based on purpose: the installer's default `driver=nonfree` entry keeps the ISO's baked-in driver and never
  runs `kiro-hwd install`, so only a hook reaches that path (also the ISO build itself, hence the live session).
  It runs before `90-mkinitcpio-install.hook`.
- Build recipe `kiro-hwd.install`: `post_install` and `post_upgrade` run `flip-fix` too (safe in the ISO chroot).
- Test: `test_flip_fix_follows_nvidia_utils_version` (620 written, unchanged rerun, 615 / 625 / none removed).

### Files Modified
- `usr/lib/kiro-hwd/kiro_hwd/apply.py`, `usr/lib/kiro-hwd/kiro_hwd/cli.py`
- `usr/share/libalpm/hooks/60-kiro-hwd-flip.hook` (new)
- `tests/test_kiro_hwd.py`, `usr/share/man/man8/kiro-hwd.8`, `README.md`, `CHANGELOG.md`
- Outside this repo: `~/KIRO-PKG-BUILD-APPS/kiro-hwd/kiro-hwd.install`

## 2026.11.24

### What Changed
- Synced with CachyOS chwd `b5278a3..93a2117` (6 commits, CachyOS 2611 release). No ID list changed, so no card
  moves to a different profile; only the `ids/UPSTREAM` pin moved to `93a2117` (2026-11-22).
- All three upstream profile changes reviewed and left out (decided with Erik).
- **Turing laptops get fine-grained GPU power saving from kiro-hwd.** `NVreg_DynamicPowerManagement=0x02` is now
  written to `/etc/modprobe.d/10-kiro-hwd-nvidia.conf` only on a PRIME laptop with a Turing GPU (GTX 16xx, RTX 20xx,
  MX450/550). kiro-system-files used to set it on every NVIDIA machine, desktops and pre-Turing cards included,
  where it does nothing useful; Ampere and newer already get it from the driver default. Same split as CachyOS chwd
  `2305306`, and CachyOS's 2611 release dropped the global value too.
- New `kiro-hwd power`: writes or removes only that file, offline. The package runs it on upgrade, so a Turing laptop
  installed from v26.11.03 keeps the setting when kiro-system-files drops its global line.

### Technical Details
- `usr/share/kiro-hwd/turing.ids` is Kiro-owned, outside `ids/` (which stays upstream-only): 112 GPU device IDs
  whose pci.ids name starts with `TU1` (hwdata 0.412-1), without the TU10x/TU116 audio, USB and UCSI functions.
  Turing is a finished generation, so it is never synced. Read by `profiles.load_id_file()`, which skips `#` lines.
- `apply.write_modprobe()` sits beside `write_mkinitcpio()` and follows the same write-or-unlink pattern; the
  installer's initramfs rebuild picks it up through the `modconf` hook. On an upgraded system the option takes
  effect at the next initramfs rebuild (next kernel update or `mkinitcpio -P`), together with the removal in
  kiro-system-files, so there is no window with neither.
- PKGBUILD gets `kiro-hwd.install` with `post_upgrade` only: `post_install` also runs in the ISO build chroot, where
  sysfs would be the build host's hardware.
- Test hook `KIRO_HWD_MODPROBE_DIR`, like `KIRO_HWD_SYSFS`. Two new tests: the list holds GPUs only; the file is
  written on a Turing laptop and removed on a Turing desktop, a Pascal laptop and an Ampere laptop.
- No Turing laptop among the test boxes: the write path is covered by the tests and a fake-sysfs run on hq only.
- `6de7e5c` (580xx uses prebuilt `linux-cachyos-nvidia-580xx` on linux-cachyos kernels, DKMS as fallback): skipped.
  With kiro-hwd's repo order the kernel comes from chaotic-aur (7.3.6-1 at review time) while the prebuilt module in
  cachyos is built against cachyos's own kernel (7.3.5-2); mixing them gives a module that doesn't match the kernel
  or a forced downgrade. `nvidia-580xx-dkms` + `<kernel>-headers` builds against whatever kernel is installed.
  Revisit only if Kiro takes linux-cachyos from the cachyos repo.
  Second reason, independent of repo order: upstream installs prebuilt modules only for `linux-cachyos*` kernels and
  uses DKMS only when none is installed, so v26.12.01's backup kernel `linux-lts` would boot without the NVIDIA
  driver on Maxwell/Pascal/Volta. DKMS builds the module for every installed kernel.
- `03fb451` (fallback profile for every GPU vendor, installs mesa): skipped. kiro-hwd handles NVIDIA only; the ISO
  already ships mesa.
- `be77fd9` (Arrow Lake added to the intel-lpmd profile): skipped. kiro-hwd has no power-management profile;
  adding intel-lpmd would be a new feature, not a sync.
- `93a2117`, `151a128`, `200c16f`: translations only (Basque, French, Italian).
- `ruff check .` clean, 17 unit tests pass.

### Files Modified
- `usr/share/kiro-hwd/ids/UPSTREAM`
- `usr/share/kiro-hwd/turing.ids` (new)
- `usr/lib/kiro-hwd/kiro_hwd/apply.py`, `cli.py`, `profiles.py`
- `tests/test_kiro_hwd.py`
- `README.md`, `CHANGELOG.md`
- `~/KIRO-PKG-BUILD-APPS/kiro-hwd/PKGBUILD`, `kiro-hwd.install` (new)

## 2026.11.03

### What Changed
- **New: kiro-hwd v1**, Kiro's own NVIDIA driver picker, to replace CachyOS chwd in the installer. It takes only
  chwd's PCI ID lists; the profiles, packages and install steps are Kiro's choices.
- `kiro-hwd detect` shows the GPUs, the chosen profile and why; `kiro-hwd install [--dry-run]` installs it.
- Profiles: `nvidia-open` (Turing and newer, from Arch `extra`), `nvidia-580xx` (Maxwell/Pascal/Volta, chaotic-aur
  first, cachyos as fallback), `nouveau` (Kepler and older: nothing installed, like upstream's 470xx drop at
  b5278a3 and Kiro's newer-machines rule). Laptops with an iGPU add `nvidia-prime` + `switcheroo-control`.
- `tools/sync-chwd.sh` follows upstream: shows every chwd commit since the last sync, `--apply` copies the ID lists.
- New `tools/check-chwd.sh` + daily user timer (`tools/systemd/kiro-hwd-chwd-check.{service,timer}`): sends a
  desktop notification when CachyOS chwd has commits past `ids/UPSTREAM`, saying whether the ID lists, the
  profiles or only code changed, and points to the `/kiro-hwd-sync` Claude Code command that runs the whole
  review → apply → test → CHANGELOG → push flow. Not part of the package; it is a maintainer tool.
- **Tested on real hardware the same day** (KiroTux v26.11.03 test ISOs, installer boot entries):
  - Pascal laptop (Intel UHD 630 + GTX 1050 Ti), auto-detect entry: profile `nvidia-580xx + prime`, all four
    580xx packages from chaotic-aur, `nvidia-prime` + `switcheroo-control` added; the `nvidia` module loads,
    `prime-run` renders on the GTX 1050 Ti and `switcherooctl` lists both GPUs with Intel as default.
  - Turing desktop (RTX 2060), auto-detect entry: profile `nvidia-open`, the baked `nvidia-open-dkms` kept and only
    `nvidia-settings` + `opencl-nvidia` added; both mkinitcpio drop-ins written; `nvidia-smi` reports 615.78.08.
  - Same desktop, open-drivers entry (`driver=free`): kiro-hwd skipped, NVIDIA stack removed, nouveau + NVK
    renders. `kiro-hwd detect` and `install --dry-run` on that install still pick `nvidia-open` correctly.
  - Not yet tested: the `nouveau` profile on a Kepler-or-older card, and a run with no NVIDIA GPU (VM).
    _Both tested later the same day:_ `nouveau` on a Fermi GT 620M laptop (legacy BIOS, Kiro v26.11.03 line 3:
    stack removed, "Nothing to install.", nouveau + `DRI_PRIME=1` → NVC1, kiro-audit 131/0/0), and no NVIDIA GPU in
    VirtualBox (Kiro) and QEMU (KiroTux hyprland-dms): "no NVIDIA GPU found", "Nothing to install.".

### Technical Details
- Python 3, standard library only (`tomllib`); GPUs come from `/sys/bus/pci/devices`, so `lspci` output is not
  parsed. With several NVIDIA cards the newest driver wins (profiles.toml runs oldest to newest).
- Packages install as explicit `repo/package` names in the order core/extra/multilib → chaotic-aur → cachyos.
  When [cachyos] is commented out (installed Kiro), a temporary pacman.conf with it enabled is used; the full
  `-Syu` runs first with the system's own config, so no cachyos rebuild replaces a base package.
- No `lib32-*` packages: Kiro supports x86_64 only (chwd's profiles always asked for them, and Kiro ships
  [multilib] off, so chwd's install could not complete).
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
- `tools/check-chwd.sh`, `tools/systemd/kiro-hwd-chwd-check.{service,timer}`, `README.md`
- `README.md`, `CHANGELOG.md`, `CLAUDE.md`, `LICENSE`, `ruff.toml`, `setup.sh`, `up.sh`, `.gitignore`
