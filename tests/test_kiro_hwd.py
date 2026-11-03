"""Unit tests: python3 -m unittest discover -s tests (from the repo root)."""

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "usr" / "lib" / "kiro-hwd"))

from kiro_hwd import apply, detect, profiles, repos  # noqa: E402

DATA = REPO / "usr" / "share" / "kiro-hwd"
INTEL = ("0000:00:02.0", "0x8086", "0x9bc5", "0x030000")
AMD = ("0000:05:00.0", "0x1002", "0x1638", "0x030000")


def fake_sysfs(root: Path, *devices: tuple[str, str, str, str]) -> Path:
    """A /sys/bus/pci/devices tree with the given (slot, vendor, device, class) entries plus a non-GPU."""
    for slot, vendor, device, pci_class in (*devices, ("0000:00:1f.3", "0x8086", "0x02c8", "0x040380")):
        dev = root / slot
        dev.mkdir(parents=True)
        (dev / "vendor").write_text(vendor + "\n")
        (dev / "device").write_text(device + "\n")
        (dev / "class").write_text(pci_class + "\n")
    return root


class ChooseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.profiles, self.prime = profiles.load_profiles(DATA / "profiles.toml")
        self.ids = profiles.load_ids(DATA / "ids")

    def tearDown(self):
        self.tmp.cleanup()

    def pick(self, chassis, *devices):
        gpus = detect.read_gpus(fake_sysfs(self.root, *devices))
        return profiles.choose(gpus, self.profiles, self.prime, self.ids, chassis)

    def test_turing_desktop_gets_open(self):
        c = self.pick(3, ("0000:01:00.0", "0x10de", "0x1f08", "0x030000"))
        self.assertEqual((c.profile.name, c.prime), ("nvidia-open", False))

    def test_ampere_desktop_with_igpu_is_not_prime(self):
        c = self.pick(3, INTEL, ("0000:01:00.0", "0x10de", "0x2504", "0x030000"))
        self.assertEqual((c.profile.name, c.prime), ("nvidia-open", False))

    def test_pascal_laptop_gets_580xx_prime(self):
        c = self.pick(10, INTEL, ("0000:01:00.0", "0x10de", "0x1c8c", "0x030200"))
        self.assertEqual((c.profile.name, c.prime), ("nvidia-580xx", True))

    def test_amd_igpu_laptop_is_prime(self):
        c = self.pick(10, AMD, ("0000:01:00.0", "0x10de", "0x2520", "0x030200"))
        self.assertEqual((c.profile.name, c.prime), ("nvidia-open", True))

    def test_fermi_laptop_stays_on_nouveau(self):
        c = self.pick(10, INTEL, ("0000:01:00.0", "0x10de", "0x1140", "0x030200"))
        self.assertEqual((c.profile.name, c.prime), ("nouveau", False))

    def test_vm_has_no_nvidia(self):
        c = self.pick(1, ("0000:00:02.0", "0x80ee", "0xbeef", "0x030000"))
        self.assertIsNone(c.profile)

    def test_newest_driver_wins_with_two_cards(self):
        c = self.pick(3, ("0000:01:00.0", "0x10de", "0x1c82", "0x030000"),
                      ("0000:02:00.0", "0x10de", "0x1f08", "0x030000"))
        self.assertEqual(c.profile.name, "nvidia-open")


class RepoTests(unittest.TestCase):
    CONF = ("[options]\nArchitecture = auto\n\n[extra]\nInclude = /etc/pacman.d/mirrorlist\n\n"
            "#[multilib]\n#Include = /etc/pacman.d/mirrorlist\n\n[chaotic-aur]\nInclude = /etc/pacman.d/chaotic\n\n"
            "#[cachyos]\n#Include = /etc/pacman.d/cachyos-mirrorlist\n")

    def test_enabled_repos_skips_commented(self):
        self.assertEqual(repos.enabled_repos(self.CONF), ["extra", "chaotic-aur"])

    def test_cachyos_turned_back_on_only(self):
        text = repos.with_repo_enabled(self.CONF, "cachyos")
        self.assertEqual(repos.enabled_repos(text), ["extra", "chaotic-aur", "cachyos"])
        self.assertIn("Include = /etc/pacman.d/cachyos-mirrorlist", text)
        self.assertIn("#[multilib]", text)

    def test_chaotic_before_cachyos_and_arch_first(self):
        contents = {"extra": {"nvidia-utils"}, "chaotic-aur": {"nvidia-580xx-dkms", "nvidia-utils"},
                    "cachyos": {"nvidia-580xx-dkms", "nvidia-470xx-dkms"}}
        found, missing = repos.resolve(["nvidia-utils", "nvidia-580xx-dkms", "nvidia-470xx-dkms", "nope"], contents)
        self.assertEqual(found, [("extra", "nvidia-utils"), ("chaotic-aur", "nvidia-580xx-dkms"),
                                 ("cachyos", "nvidia-470xx-dkms")])
        self.assertEqual(missing, ["nope"])


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        profile_list, self.prime = profiles.load_profiles(DATA / "profiles.toml")
        self.open = next(p for p in profile_list if p.name == "nvidia-open")
        self.gpu = detect.Gpu("0000:01:00.0", "10de", "1f08", "0300")

    def tearDown(self):
        self.tmp.cleanup()

    def test_package_list_headers_prime_no_lib32(self):
        choice = profiles.Choice(self.open, self.gpu, prime=True)
        pkgs = apply.package_list(choice, self.prime, headers=["linux-cachyos-headers"])
        self.assertNotIn("lib32-nvidia-utils", pkgs)
        self.assertIn("linux-cachyos-headers", pkgs)
        self.assertIn("switcheroo-control", pkgs)
        self.assertFalse([p for p in pkgs if p.startswith("lib32-")])

    def test_kernel_headers_from_pkgbase(self):
        for kver, base in (("6.17.1-1-cachyos", "linux-cachyos"), ("6.17.1-zen1", "linux-zen")):
            (self.root / kver).mkdir()
            (self.root / kver / "pkgbase").write_text(base + "\n")
        self.assertEqual(apply.kernel_headers(self.root), ["linux-cachyos-headers", "linux-zen-headers"])

    def test_other_branch_is_a_conflict(self):
        wanted = ["nvidia-580xx-dkms", "nvidia-580xx-utils", "nvidia-580xx-settings"]
        installed = {"nvidia-utils", "nvidia-prime", "nvidia-580xx-utils", "mesa"}
        self.assertEqual(apply.conflicting_drivers(installed, wanted), ["nvidia-utils"])

    def test_mkinitcpio_desktop_drops_kms_prime_keeps_it(self):
        desktop = apply.write_mkinitcpio(profiles.Choice(self.open, self.gpu), self.root)
        self.assertEqual([p.name for p in desktop], ["10-kiro-hwd.conf", "10-kiro-hwd-kms.conf"])
        prime = apply.write_mkinitcpio(profiles.Choice(self.open, self.gpu, prime=True), self.root)
        self.assertEqual([p.name for p in prime], ["10-kiro-hwd.conf"])
        self.assertFalse((self.root / "10-kiro-hwd-kms.conf").exists())

    def test_state_file(self):
        state = self.root / "state"
        apply.write_state(profiles.Choice(self.open, self.gpu), [("extra", "nvidia-utils")], "kiro-hwd 26.11-01", state)
        self.assertIn('"extra/nvidia-utils"', state.read_text())


if __name__ == "__main__":
    unittest.main()
