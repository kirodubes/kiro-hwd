"""Load Kiro's profiles and the mirrored ID lists, and pick the profile for this machine."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .detect import IGPU_VENDORS, Gpu


@dataclass
class Profile:
    """One driver profile from profiles.toml."""

    name: str
    desc: str
    ids: list[str]
    packages: list[str]
    headers: bool
    fallback: bool = False


@dataclass
class Prime:
    """Extra packages and services for NVIDIA laptops with an iGPU."""

    chassis_types: list[int]
    packages: list[str]
    services: list[str]


@dataclass
class Choice:
    """The outcome of choose(): a profile, or None when there is no NVIDIA GPU."""

    profile: Profile | None
    gpu: Gpu | None
    prime: bool = False
    reasons: list[str] = field(default_factory=list)


def load_profiles(path: Path) -> tuple[list[Profile], Prime]:
    """Profiles in file order, plus the prime settings."""
    data = tomllib.loads(path.read_text())
    profiles = [
        Profile(name=name, desc=p["desc"], ids=p.get("ids", []), packages=p["packages"],
                headers=p.get("headers", False), fallback=p.get("fallback", False))
        for name, p in data["profile"].items()
    ]
    p = data["prime"]
    return profiles, Prime(p["chassis_types"], p["packages"], p["services"])


def load_ids(ids_dir: Path) -> dict[str, set[str]]:
    """Every <name>.ids file as a set of lowercase 4-digit device IDs."""
    return {f.stem: set(f.read_text().lower().split()) for f in sorted(ids_dir.glob("*.ids"))}


def _profile_for(gpu: Gpu, profiles: list[Profile], ids: dict[str, set[str]]) -> tuple[Profile, str]:
    for profile in profiles:
        for list_name in profile.ids:
            if gpu.device in ids.get(list_name, set()):
                return profile, f"{gpu.device} is on the {list_name} list"
    fallback = next(p for p in profiles if p.fallback)
    return fallback, f"{gpu.device} is on no legacy list"


def choose(gpus: list[Gpu], profiles: list[Profile], prime: Prime, ids: dict[str, set[str]],
           chassis: int | None) -> Choice:
    """Pick one profile for the machine; with several NVIDIA GPUs the newest driver wins."""
    nvidia = [g for g in gpus if g.is_nvidia]
    if not nvidia:
        return Choice(None, None, reasons=["no NVIDIA GPU found"])
    picks = [(_profile_for(g, profiles, ids), g) for g in nvidia]
    # profiles.toml order runs oldest to newest, so the last profile index is the newest driver
    order = {p.name: i for i, p in enumerate(profiles)}
    (profile, why), gpu = max(picks, key=lambda pick: order[pick[0][0].name])
    choice = Choice(profile, gpu, reasons=[why])
    igpu = [g for g in gpus if g.vendor in IGPU_VENDORS]
    if profile.packages and igpu and chassis in prime.chassis_types:
        choice.prime = True
        choice.reasons.append(f"laptop chassis {chassis} with an {IGPU_VENDORS[igpu[0].vendor]} iGPU: PRIME offload")
    return choice
