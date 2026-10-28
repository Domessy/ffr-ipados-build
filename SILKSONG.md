# Hollow Knight: Silksong → iPadOS (isolated nxnative workflow)

Game profile: `010013C00E930000`, tested with Switch update **1.0.30000 (v655360)**. The pinned nxnative commit `78cb26d91373d6731984a9692607b796a6b23162` already ships this profile and records successful gameplay on Apple hardware. A different update may require a derived profile and may not work. No NSP or console key is stored in GitHub.

## What remains separate

| Component | Silksong | Final Fantasy Resonance |
|---|---|---|
| Local NSP folder | `~/Documents/Hollow Knight Silksong/` | `~/Documents/FF Resonance/` |
| Cached shaders | `~/portage-ipados/hollow-knight-silksong/shader-cache/` | `~/portage-ipados/ff-resonance/shader-cache/` |
| Result IPA | `~/portage-ipados/hollow-knight-silksong/resultats/Silksong-iPadOS.ipa` | Existing FFR result |
| Private build log | `~/portage-ipados/hollow-knight-silksong/resultats/silksong-build.log` | Existing FFR log |
| Workflow | `.github/workflows/build-silksong.yml` | `.github/workflows/build-ffr.yml` |

Existing Tailscale, host SSH key and GitHub Secrets are **reused**, not copied into the public repo. The only new SSH commands have the `silksong-` prefix; they run through the existing forced-command gateway. The existing FFR commands and cache are unchanged.

The Silksong gateway expects **exactly two regular, non-symlink `.nsp` files** at the top level of `~/Documents/Hollow Knight Silksong/`, using the larger file as the base game and the smaller file as the update. Check this ordering and update version before building. If the folder has more or fewer NSPs, it refuses to transfer anything. `prod.keys` is reused from the FFR restricted `read-keys` command.

## Local preflight (CachyOS)

```bash
cd "$HOME/portage-ipados/ff-resonance/github-build"
git pull --ff-only origin main
python3 -m unittest -v security/test_cache_import.py security/test_silksong_gateway.py
find "$HOME/Documents/Hollow Knight Silksong" -maxdepth 1 -type f -iname '*.nsp' -printf '%f\t%s bytes\n'
env SSH_ORIGINAL_COMMAND=silksong-probe-v1 python3 security/ffr_ssh_gate.py
```

Only if the tests and probe succeed and the two files are the expected base/update:

```bash
gh workflow run build-silksong.yml -R Domessy/ffr-ipados-build
gh run list -R Domessy/ffr-ipados-build --workflow build-silksong.yml --limit 3
```

**Do not invoke `security/harden-cachyos.sh` again.** The existing authorized forced-command path is unchanged. No system packages or Tailscale settings are modified on CachyOS. The build uses a fresh `xcode-27` hosted Mac with Xcode 27.1, verifies the nxnative commit and Metal toolchain, then restores Silksong-only CAS. It streams your files over SSH, compiles them without publishing private logs, atomically appends derived shaders to your isolated CAS (SHA-256 checks and conflict isolation), and transfers the finished IPA and log to Silksong-specific local paths.

If the build stops after 240 minutes, subsequent runs can resume from the Silksong CAS; the old FFR CAS is never consulted. Insufficient disk space stops the runner before transfer. This workflow preserves the same `Increased Memory Limit` signing requirements as other large LiveContainer ports; its iOS launch still needs validation.

## Checks after build

```bash
IPA="$HOME/portage-ipados/hollow-knight-silksong/resultats/Silksong-iPadOS.ipa"
LOG="$HOME/portage-ipados/hollow-knight-silksong/resultats/silksong-build.log"
ls -lh "$IPA"
tail -n 25 "$LOG"
```

Compare `sha256sum "$IPA"` to the public GitHub job's SHA-256 before transferring to iPad. Install with your current working version of LiveContainer+SideStore, and validate startup, inputs, sound, graphics and save persistence. Do **not** downgrade LiveContainer to the version that failed to sign the very large FFR IPA.

## Reversibility

Remove this new workflow/helper and its Silksong cache/results if you want to discontinue it, leaving the FFR workflow, keys and shader cache alone. Keep the existing authorized SSH gateway and GitHub Secrets if FFR is still needed. No one-time system installation is introduced by this workflow.
