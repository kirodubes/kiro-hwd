"""Turn a Choice into a package list and the system changes that go with it."""

import json
import subprocess
from pathlib import Path

from .profiles import Choice, Prime

MKINITCPIO_DIR = Path("/etc/mkinitcpio.conf.d")
MODPROBE_DIR = Path("/etc/modprobe.d")
MODPROBE_FILE = "10-kiro-hwd-nvidia.conf"
# Fine-grained runtime D3: Turing laptops need it set; Ampere+ get it from the driver default, older cards
# and desktops don't support it.
TURING_POWER = "options nvidia NVreg_DynamicPowerManagement=0x02\n"
FLIP_FILE = "11-kiro-hwd-flip.conf"
# NVIDIA bug 7126445 (open-gpu-kernel-modules #1553): on 620.x a Wayland compositor gets "Flip event timeout" and a
# black screen at login with 2+ screens. This option cleared it on riker (RTX 2060, 2 screens, 17 tests). The file
# follows the installed nvidia-utils version: drop a branch here once NVIDIA ships a fixed driver in it.
FLIP_BRANCHES = ("620.",)
FLIP_FIX = (
    "# NVIDIA 620.x: black screen at the Wayland login with 2+ screens (NVIDIA bug 7126445).\n"
    "options nvidia_modeset opportunistic_flip_sync=0\n"
)
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


def needs_turing_power(choice: Choice, turing_ids: set[str]) -> bool:
    """True on a PRIME laptop whose NVIDIA GPU is Turing."""
    return bool(choice.prime and choice.gpu and choice.gpu.device in turing_ids)


def write_modprobe(choice: Choice, turing_ids: set[str], conf_dir: Path = MODPROBE_DIR) -> list[Path]:
    """Write the Turing laptop power option, or remove a stale one on any other machine."""
    conf = conf_dir / MODPROBE_FILE
    if not needs_turing_power(choice, turing_ids):
        conf.unlink(missing_ok=True)
        return []
    conf_dir.mkdir(parents=True, exist_ok=True)
    conf.write_text(HEADER + TURING_POWER)
    return [conf]


def nvidia_utils_version() -> str | None:
    """Installed nvidia-utils version, or None when it is not installed."""
    out = subprocess.run(["pacman", "-Q", "nvidia-utils"], capture_output=True, text=True, check=False)
    parts = out.stdout.split()
    return parts[1] if out.returncode == 0 and len(parts) == 2 else None


def needs_flip_fix(version: str | None) -> bool:
    """True for an nvidia-utils version on a branch with the flip-timeout bug."""
    return bool(version and version.startswith(FLIP_BRANCHES))


def write_flip_fix(version: str | None, conf_dir: Path = MODPROBE_DIR) -> tuple[Path | None, bool]:
    """Write or remove the flip-timeout option; return the file written (or None) and whether anything changed."""
    conf = conf_dir / FLIP_FILE
    if not needs_flip_fix(version):
        existed = conf.exists()
        conf.unlink(missing_ok=True)
        return None, existed
    text = HEADER + FLIP_FIX
    if conf.is_file() and conf.read_text() == text:
        return conf, False
    conf_dir.mkdir(parents=True, exist_ok=True)
    conf.write_text(text)
    return conf, True


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
