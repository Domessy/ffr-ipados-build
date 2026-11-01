# The Legend of Zelda: Echoes of Wisdom — nxnative iPadOS port

Status: manually dispatched pipeline and security tests prepared. **No private game files transferred and no IPA built at preparation stage.**

## Inputs and tested upstream

- Source directory on CachyOS: `/home/syssy/Documents/The Legend of Zelda Echoes of Wisdom/`
- **Base:** exactly one `.xci` game-card image; file's XCI game-card header must show `HEAD` at offset `0x100`.
- **Update:** exactly one `.nsp` with `PFS0` header.
- Keys: regular non-symlink `prod.keys` in the same original directory.
- Profile: base program ID `01008CF01BAAC000`, registered **1.1.0 / v196608**, update ID `01008CF01BAAC800`.
- Pinned nxnative: `seedds/nxnative@5ce955ada8b7b2a1369461aa1e2c89bbd093e52a`.
- Xcode 27.2 / Metal 32023.922 (both macOS and iPhoneOS SDKs), checked strictly before connecting to CachyOS.
- Upstream status at pinned commit: 9,858 built shader libraries; unsigned IPA packaged (~7.8 GB). Mac prologue/corridor playable; **no demonstrated iPadOS playability yet**.

Only the tested update profile is registered. Filenames containing an explicit wrong title ID or version are rejected locally; filenames without version metadata are accepted by extension, but the gateway **does not inspect encrypted XCI/NSP title/version internals**. The actual version is verified by nxnative while extracting, and a non-1.1.0 update may not use the tested profile. Never falsely present the gateway manifest's expected version as verified internal version.

## Local project layout

The setup does not rename, overwrite or remove the original XCI, NSP or `prod.keys`.

`~/portage-ipados/zelda-echoes-of-wisdom/`

- `source` -> fixed original Documents subfolder
- `private/prod.keys` -> owner-only copy (0600), never a symlink
- `shader-cache/`, `shader-cache-conflicts/` -> separate append-only DMSH_CAS storage
- `resultats/ZeldaEchoesOfWisdom-nxnative.ipa` -> expected output
- `resultats/eow-build.log` -> private bounded diagnostics

Restricted forced SSH uses only `eow-*` commands, avoiding arbitrary file names, remote shell or private asset exposure in public GitHub logs.

## Local setup and preflight

After merging the prepared PR into `main`, run this **from Bash** on CachyOS:

```bash
(
set -euo pipefail
cd "$HOME/portage-ipados/ff-resonance/github-build"
test "$(git branch --show-current)" = main
test -z "$(git status --porcelain)"
git pull --ff-only origin main
bash security/setup_eow.sh
python3 -m unittest -v security/test_cache_import.py security/test_eow_gateway.py security/test_eow_transfer.py
gh workflow run build-eow.yml --ref main -R Domessy/ffr-ipados-build -f mode=preflight
)
```

The preflight uses no source transfer. It verifies local source package structure through the fixed SSH gateway and verifies the macOS runner's Xcode, Metal toolchain, dependencies and free storage. Inspect workflow results before proceeding. If the input files' names lack version markers, double-check version via nxnative's actual extraction; do not fabricate it.

## Build after preflight success

```bash
gh workflow run build-eow.yml --ref main -R Domessy/ffr-ipados-build -f mode=build
```

The build repeats its own preflight before any private source transfer. The original XCI and update NSP are copied independently over Tailscale/SSH onto the temporary macOS runner and passed **together in one folder** to nxnative's `build_ipa_from_nsp.py`. The runner's copies may be removed only after it reaches the iOS shader stage; no originals are modified. Shader CAS is checkpointed at intervals to CachyOS, with a final checkpoint, preserving progress between runs.

No IPA is published as a GitHub artifact; it is streamed privately into `resultats/`. A successful job does not mean the IPA has been installed on the iPad.

## Tests and rollback

Synthetic CI tests sparse XCI with `HEAD` at 0x100 and sparse NSP with `PFS0`, wrong-role/wrong-version rejection, private-key symlink rejection, safe fixed diagnostics, atomic transfers and separate cache/output path scopes. No copyrighted assets or secrets are included in Git.

Remove `~/portage-ipados/zelda-echoes-of-wisdom/` only after preserving any desired IPA, private log and cache, to undo the game workspace. The Git gateway dispatch can be separately reverted after no job is active. Other game ports remain independent.
