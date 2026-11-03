"""Decide which repo each package comes from: Arch first, then chaotic-aur, then cachyos."""

import re
import subprocess
from pathlib import Path

REPO_ORDER = ["core", "extra", "multilib", "chaotic-aur", "cachyos"]
FALLBACK_REPO = "cachyos"


def enabled_repos(conf_text: str) -> list[str]:
    """Repo sections that are not commented out, in file order."""
    return [m for m in re.findall(r"^\[([^\]]+)\]\s*$", conf_text, re.M) if m != "options"]


def with_repo_enabled(conf_text: str, repo: str) -> str:
    """The same pacman.conf with a commented-out [repo] section (as kiro_final leaves it) uncommented."""
    out = []
    in_section = False
    for line in conf_text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped == f"#[{repo}]":
            in_section = True
            out.append(line.replace("#", "", 1))
            continue
        if in_section:
            if stripped.startswith("#") and not stripped.startswith("#["):
                out.append(line.replace("#", "", 1))
                continue
            in_section = False
        out.append(line)
    return "".join(out)


def pacman_conf_for_install(conf: Path, tmp_conf: Path) -> Path:
    """The config to install with: /etc/pacman.conf, or a temp copy with cachyos turned on when it is off."""
    text = conf.read_text()
    if FALLBACK_REPO in enabled_repos(text):
        return conf
    patched = with_repo_enabled(text, FALLBACK_REPO)
    if FALLBACK_REPO not in enabled_repos(patched):
        return conf
    tmp_conf.write_text(patched)
    return tmp_conf


def repo_contents(conf: Path, repos: list[str]) -> dict[str, set[str]]:
    """Package names per repo from the local sync databases (pacman -Sl); a repo without a database is empty."""
    contents = {}
    for repo in repos:
        result = subprocess.run(["pacman", "--config", str(conf), "-Sl", repo],
                                capture_output=True, text=True, check=False)
        contents[repo] = {line.split()[1] for line in result.stdout.splitlines() if len(line.split()) > 1}
    return contents


def resolve(packages: list[str], contents: dict[str, set[str]]) -> tuple[list[tuple[str, str]], list[str]]:
    """(repo, package) for each package from the first repo in REPO_ORDER that has it, plus the missing ones."""
    found, missing = [], []
    for pkg in packages:
        repo = next((r for r in REPO_ORDER if pkg in contents.get(r, set())), None)
        if repo:
            found.append((repo, pkg))
        else:
            missing.append(pkg)
    return found, missing
