"""Command line: kiro-hwd detect | kiro-hwd install [--dry-run] | kiro-hwd power | kiro-hwd flip-fix."""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from . import apply, detect, profiles, repos

PROG = "kiro-hwd"


def _data_dir() -> Path:
    # /usr/bin/kiro-hwd -> /usr/share/kiro-hwd, and the same layout inside the repo
    return Path(__file__).resolve().parents[3] / "share" / PROG


def _version() -> str:
    exe = os.path.realpath(sys.argv[0])
    owner = subprocess.run(["pacman", "-Qqo", exe], capture_output=True, text=True, check=False)
    if owner.returncode == 0:
        return subprocess.run(["pacman", "-Q", owner.stdout.strip()], capture_output=True, text=True,
                              check=False).stdout.strip()
    return f"{PROG} (not installed via pacman)"


def _choice(data: Path) -> tuple[profiles.Choice, profiles.Prime, list[detect.Gpu]]:
    profile_list, prime = profiles.load_profiles(data / "profiles.toml")
    ids = profiles.load_ids(data / "ids")
    # Test hooks: a fake sysfs tree and chassis type let a dry run on any box act as another machine
    gpus = detect.read_gpus(Path(os.environ.get("KIRO_HWD_SYSFS", "/sys/bus/pci/devices")))
    chassis = os.environ.get("KIRO_HWD_CHASSIS")
    chassis_type = int(chassis) if chassis else detect.chassis_type()
    return profiles.choose(gpus, profile_list, prime, ids, chassis_type), prime, gpus


def _turing_ids() -> set[str]:
    return profiles.load_id_file(_data_dir() / "turing.ids")


def _modprobe_dir() -> Path:
    # Test hook, like KIRO_HWD_SYSFS: write the modprobe file somewhere harmless
    return Path(os.environ.get("KIRO_HWD_MODPROBE_DIR", str(apply.MODPROBE_DIR)))


def _print_choice(choice: profiles.Choice, gpus: list[detect.Gpu]) -> None:
    for gpu in gpus:
        print(f"GPU      {gpu.label()}")
    if choice.profile:
        print(f"Profile  {choice.profile.name}{' + prime' if choice.prime else ''}: {choice.profile.desc}")
    for reason in choice.reasons:
        print(f"Reason   {reason}")
    if apply.needs_turing_power(choice, _turing_ids()):
        print("Reason   Turing laptop: NVreg_DynamicPowerManagement=0x02")
    version = apply.nvidia_utils_version()
    if apply.needs_flip_fix(version):
        print(f"Reason   nvidia-utils {version}: opportunistic_flip_sync=0 (NVIDIA bug 7126445)")


def cmd_detect(_args: argparse.Namespace) -> int:
    """Show the GPUs and the profile kiro-hwd would pick."""
    choice, _prime, gpus = _choice(_data_dir())
    _print_choice(choice, gpus)
    return 0


def cmd_power(_args: argparse.Namespace) -> int:
    """Write or remove the Turing laptop power option only (offline; run on package upgrade)."""
    choice, _prime, _gpus = _choice(_data_dir())
    conf_dir = _modprobe_dir()
    written = apply.write_modprobe(choice, _turing_ids(), conf_dir)
    for path in written:
        print(f"Wrote    {path}")
    if not written:
        print(f"Removed  {conf_dir / apply.MODPROBE_FILE} (if present): not a Turing laptop")
    return 0


def cmd_flip_fix(_args: argparse.Namespace) -> int:
    """Write or remove the NVIDIA 620 flip-timeout option to match nvidia-utils (run by a pacman hook)."""
    conf_dir = _modprobe_dir()
    version = apply.nvidia_utils_version()
    written, changed = apply.write_flip_fix(version, conf_dir)
    if not changed:
        print(f"Nothing to do (nvidia-utils {version or 'not installed'})")
        return 0
    if written:
        print(f"Wrote    {written} (nvidia-utils {version})")
    else:
        print(f"Removed  {conf_dir / apply.FLIP_FILE} (nvidia-utils {version or 'not installed'})")
    # With nvidia in the initramfs (kiro-hwd's early KMS file) its modprobe options are baked in there too
    if (apply.MKINITCPIO_DIR / "10-kiro-hwd.conf").is_file() and conf_dir == apply.MODPROBE_DIR:
        subprocess.run(["mkinitcpio", "-P"], check=True)
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    """Install the driver for the chosen profile."""
    if not args.dry_run and os.geteuid() != 0:
        print(f"{PROG} install must run as root (or use --dry-run).", file=sys.stderr)
        return 1
    choice, prime, gpus = _choice(_data_dir())
    _print_choice(choice, gpus)
    if not choice.profile or not choice.profile.packages:
        print("Nothing to install.")
        return 0

    etc_conf = Path("/etc/pacman.conf")
    wanted = apply.package_list(choice, prime, apply.kernel_headers())

    conflicts = apply.conflicting_drivers(apply.installed_packages(), wanted)
    if conflicts:
        print("Stop     another NVIDIA driver is installed: " + " ".join(conflicts))
        print("         Remove it first (pacman -Rns), then run kiro-hwd install again.")
        if not args.dry_run:
            return 1

    with tempfile.TemporaryDirectory(prefix=f"{PROG}-") as tmp:
        conf = repos.pacman_conf_for_install(etc_conf, Path(tmp) / "pacman.conf")
        if not args.dry_run:
            # Full upgrade with the system's own config first, so new headers match the kernel and no
            # cachyos rebuild replaces a base package; the temp config then only refreshes and installs.
            subprocess.run(["pacman", "-Syu", "--noconfirm"], check=True)
            subprocess.run(["pacman", "--config", str(conf), "-Sy"], check=True)
        contents = repos.repo_contents(conf, repos.REPO_ORDER)
        found, missing = repos.resolve(wanted, contents)
        for repo, pkg in found:
            print(f"Package  {repo}/{pkg}")
        if missing:
            print("Stop     not in any repo: " + " ".join(missing), file=sys.stderr)
            return 1
        if args.dry_run:
            print("Dry run: nothing installed.")
            return 0
        subprocess.run(["pacman", "--config", str(conf), "-S", "--needed", "--noconfirm",
                        *[f"{repo}/{pkg}" for repo, pkg in found]], check=True)

    for path in apply.write_mkinitcpio(choice) + apply.write_modprobe(choice, _turing_ids(), _modprobe_dir()):
        print(f"Wrote    {path}")
    flip, _changed = apply.write_flip_fix(apply.nvidia_utils_version(), _modprobe_dir())
    if flip:
        print(f"Wrote    {flip}")
    if choice.prime:
        apply.enable_services(prime.services)
    apply.write_state(choice, found, _version())
    print("Done. The initramfs is rebuilt by the installer, or run: mkinitcpio -P")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(prog=PROG, description="Pick and install the NVIDIA driver for this machine.")
    parser.add_argument("--version", action="store_true", help="show the installed version")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("detect", help="show the GPUs and the profile that would be used").set_defaults(func=cmd_detect)
    install = sub.add_parser("install", help="install the driver for this machine")
    install.add_argument("--dry-run", action="store_true", help="show the packages and repos, install nothing")
    install.set_defaults(func=cmd_install)
    sub.add_parser("power", help="write or remove the Turing laptop power option only").set_defaults(func=cmd_power)
    sub.add_parser("flip-fix", help="write or remove the NVIDIA 620 flip-timeout option").set_defaults(
        func=cmd_flip_fix)
    args = parser.parse_args(argv)
    if args.version:
        print(_version())
        return 0
    if not args.command:
        parser.print_help()
        return 0
    try:
        return args.func(args)
    except subprocess.CalledProcessError as e:
        print(f"Stop     command failed ({e.returncode}): {' '.join(map(str, e.cmd))}", file=sys.stderr)
        return 1
