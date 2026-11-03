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
```

The Kiro installer runs `kiro-hwd install` on the boot entry "NVIDIA proprietary, auto-detect"
(`driver=nonfreechwd`).

## Credits

The PCI ID lists in `usr/share/kiro-hwd/ids/` come from [CachyOS chwd](https://github.com/CachyOS/chwd)
(GPL-3.0-or-later); `ids/UPSTREAM` names the commit they were taken from. The profiles, package choices and
install logic are Kiro's own. `tools/sync-chwd.sh` shows every upstream change since the last sync.

## Tests

```
python3 -m unittest discover -s tests
```

## License

GPL-3.0-or-later.
