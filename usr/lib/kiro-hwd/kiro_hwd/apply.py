"""Turn a Choice into a package list and the system changes that go with it."""

import json
import subprocess
from pathlib import Path

from .profiles import Choice, Prime

MKINITCPIO_DIR = Path("/etc/mkinitcpio.conf.d")
STATE_FILE = Path("/var/lib/kiro-hwd/state")
NVIDIA_MODULES = "MODULES+=(nvidia nvidia_modeset nvidia_uvm nvidia_drm)\n"
DROP_KMS_HOOK = "HOOKS=(${HOOKS[@]/kms/})\n"
HEADER = "# Written by kiro-hwd. Removed or rewritten on the next kiro-hwd install.\n"
# Driver packages of another NVIDIA branch block an install; kiro-hwd never removes them itself.
DRIVER_PREFIXES = ("nvidia", "lib32-nvidia", "opencl-nvidia", "lib32-opencl-nvidia")


def kernel_headers(modules: Path = Path("/usr/lib/modules")) -> list[str]:
    """<pkgbase>-headers for every installed kernel."""
    names = {f.read_text().strip() for f in modules.glob("*/pkgbase") if f.is_file()}
    return [f"{name}-headers" for name in sorted(names)]


def package_list(choice: Choice, prime: Prime, headers: list[str]) -> list[str]:
    """Every package the choice needs, in a stable order without duplicates."""
    profile = choice.profile
    pkgs = list(profile.packages)
    if profile.headers:
        pkgs += headers
    if choice.prime:
        pkgs += prime.packages
    return list(dict.fromkeys(pkgs))


def conflicting_drivers(installed: set[str], wanted: list[str]) -> list[str]:
    """Installed NVIDIA driver packages that are not part of this install (another branch)."""
    return sorted(p for p in installed if p.startswith(DRIVER_PREFIXES) and p not in wanted and p != "nvidia-prime")


def installed_packages() -> set[str]:
    """Names of all installed packages."""
    out = subprocess.run(["pacman", "-Qq"], capture_output=True, text=True, check=False).stdout
    return set(out.split())


def write_mkinitcpio(choice: Choice, conf_dir: Path = MKINITCPIO_DIR) -> list[Path]:
    """Load the NVIDIA modules early; on a desktop also drop the kms hook so nouveau can't grab the card first."""
    conf_dir.mkdir(parents=True, exist_ok=True)
    modules = conf_dir / "10-kiro-hwd.conf"
    kms = conf_dir / "10-kiro-hwd-kms.conf"
    modules.write_text(HEADER + NVIDIA_MODULES)
    written = [modules]
    if choice.prime:
        kms.unlink(missing_ok=True)
    else:
        kms.write_text(HEADER + DROP_KMS_HOOK)
        written.append(kms)
    return written


def enable_services(services: list[str]) -> None:
    """Enable systemd units (works in a chroot: no running systemd needed)."""
    for unit in services:
        subprocess.run(["systemctl", "enable", unit], check=True)


def write_state(choice: Choice, packages: list[tuple[str, str]], version: str, path: Path = STATE_FILE) -> None:
    """Record what was installed, for kiro-audit and support."""
    path.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "version": version,
        "profile": choice.profile.name,
        "prime": choice.prime,
        "gpu": choice.gpu.label(),
        "packages": [f"{repo}/{pkg}" for repo, pkg in packages],
    }
    path.write_text(json.dumps(state, indent=2) + "\n")
