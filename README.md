# kiro-hwd

Kiro's own NVIDIA driver picker. It detects the NVIDIA card, picks a driver profile and installs it:

| Card | Profile | Driver |
|---|---|---|
| Turing and newer (RTX, GTX 16xx) | `nvidia-open` | `nvidia-open-dkms` from Arch `extra` |
| Maxwell, Pascal, Volta (GTX 9xx/10xx) | `nvidia-580xx` | `nvidia-580xx-dkms` from chaotic-aur, else cachyos |
| Kepler and older | `nouveau` | nothing: the open nouveau driver stays |

Laptops with an Intel or AMD iGPU also get `nvidia-prime` and `switcheroo-control` (render offload; no GPU
switching).

```
kiro-hwd detect               # what is in this machine, which profile, why
kiro-hwd install --dry-run    # which packages from which repo
sudo kiro-hwd install         # install it
sudo kiro-hwd power           # only the Turing laptop power option (runs on package upgrade)
sudo kiro-hwd flip-fix        # only the NVIDIA 620 flip-timeout option (pacman hook on nvidia-utils)
```

On a laptop with a Turing GPU (`usr/share/kiro-hwd/turing.ids`, Kiro's own list) kiro-hwd writes
`/etc/modprobe.d/10-kiro-hwd-nvidia.conf` with `NVreg_DynamicPowerManagement=0x02`; on every other machine it
removes that file.

While `nvidia-utils` is a 620.x build, kiro-hwd writes `/etc/modprobe.d/11-kiro-hwd-flip.conf` with
`options nvidia_modeset opportunistic_flip_sync=0`: NVIDIA bug 7126445
([open-gpu-kernel-modules #1553](https://github.com/NVIDIA/open-gpu-kernel-modules/issues/1553)) gives a black
screen at the Wayland login with two or more screens. The pacman hook `60-kiro-hwd-flip.hook` runs
`kiro-hwd flip-fix` whenever nvidia-utils is installed, upgraded or removed, so the file follows the driver on every
install path (also the ISO's baked-in driver, where `kiro-hwd install` doesn't run) and goes away with a fixed driver.
When nvidia is in the initramfs (`10-kiro-hwd.conf`), `flip-fix` rebuilds it.

The Kiro installer runs `kiro-hwd install` on the boot entry "NVIDIA proprietary, auto-detect"
(`driver=nonfreechwd`).

## Credits

The PCI ID lists in `usr/share/kiro-hwd/ids/` come from [CachyOS chwd](https://github.com/CachyOS/chwd)
(GPL-3.0-or-later); `ids/UPSTREAM` names the commit they were taken from. The profiles, package choices and
install logic are Kiro's own. `tools/sync-chwd.sh` shows every upstream change since the last sync.
`tools/check-chwd.sh`, run daily by the user timer in `tools/systemd/`, sends a desktop notification when
upstream has moved past that commit:

```
ln -s "$PWD"/tools/systemd/kiro-hwd-chwd-check.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now kiro-hwd-chwd-check.timer
```

## Tests

```
python3 -m unittest discover -s tests
```

## License

GPL-3.0-or-later.
