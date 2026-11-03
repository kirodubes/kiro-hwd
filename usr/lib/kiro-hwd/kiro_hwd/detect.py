"""Read the GPUs and the chassis type from sysfs."""

from dataclasses import dataclass
from pathlib import Path

NVIDIA = "10de"
IGPU_VENDORS = {"8086": "Intel", "1002": "AMD"}
# PCI display classes: VGA (0300), 3D controller (0302), other display (0380)
DISPLAY_CLASSES = {"0300", "0302", "0380"}


@dataclass(frozen=True)
class Gpu:
    """One display-class PCI device."""

    slot: str
    vendor: str
    device: str
    pci_class: str

    @property
    def is_nvidia(self) -> bool:
        return self.vendor == NVIDIA

    def label(self) -> str:
        """Short text like 'NVIDIA 10de:1f08 at 0000:01:00.0'."""
        name = "NVIDIA" if self.is_nvidia else IGPU_VENDORS.get(self.vendor, "other")
        return f"{name} {self.vendor}:{self.device} at {self.slot}"


def _hex(path: Path, width: int) -> str:
    return path.read_text().strip().removeprefix("0x").lower()[:width]


def read_gpus(sysfs: Path = Path("/sys/bus/pci/devices")) -> list[Gpu]:
    """All display-class PCI devices, sorted by slot."""
    gpus = []
    for dev in sorted(sysfs.iterdir()) if sysfs.is_dir() else []:
        try:
            pci_class = _hex(dev / "class", 4)
            if pci_class not in DISPLAY_CLASSES:
                continue
            gpus.append(Gpu(dev.name, _hex(dev / "vendor", 4), _hex(dev / "device", 4), pci_class))
        except OSError:
            continue
    return gpus


def chassis_type(path: Path = Path("/sys/class/dmi/id/chassis_type")) -> int | None:
    """SMBIOS chassis type (10 = notebook), or None when unknown."""
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None
