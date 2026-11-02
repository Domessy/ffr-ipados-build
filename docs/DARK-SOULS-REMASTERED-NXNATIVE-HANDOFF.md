# Dark Souls Remastered — Switch NSP 1.0.3 → iPadOS native (nxnative)

## State (2026-11-02)

The **isolated GitHub Actions porting workflow** is prepared and its synthetic CI tests are run on GitHub. No real Dark Souls NSP or prod.keys is uploaded to GitHub source control, and the actual game compilation/IPA installation have not been tested by this setup stage.

- Local source: `/home/syssy/Documents/Dark Souls Remastered/`, two NSPs (base and update) plus `prod.keys`.
- Main title ID `01004AB00A260000`; update title ID `01004AB00A260800`.
- Tested nxnative profile: **update 1.0.3 / v196608**, base v0. The script uses these *expected* values to validate filename hints; only nxnative's extractor verifies the encrypted package's actual version. An update of another version may not use the registered profile.
- Pinned upstream commit: `seedds/nxnative@9e8f292b24d9a45e46ebced926c87e7d99af9bcc` (upstream shader lock expects Metal 32023.922).
- Host runner: GitHub Actions `xcode-27`, select Xcode 27.2; **verify** macosx and iphoneos Metal 32023.922 before touching any private source.
- Expected private output: `DarkSoulsRemastered-nxnative.ipa`. Not a public GitHub artifact.

## Game status and risks

The upstream game profile documents 3,099 shaders (391 vertex, 2,708 fragment/pixel), engine dantelion2 with Havok and FMOD, SDK 4.5.0, and 60 FPS on iPhone using two linked rewriter fixes (limiter at 60 and simulation step 1/60). Mac playtests reached the Undead Asylum. iOS playability and stable performance are **not guaranteed on the user's iPad Pro M5** by those tests.

Known issues in the upstream README include:
- Image-store/ambient-occlusion artifacts in some dark environments, not fully revalidated in-game.
- Some vegetation alpha effects require further validation.
- Ladders can behave incorrectly at 60 FPS.
- One reported intermittent iPhone saved-game loading stall.

Review `dm/games/01004AB00A260000/README.md` in the pinned nxnative revision. The project workflow does **not** modify these upstream game fixes.

## Per-title isolation and rollback

Project root `~/portage-ipados/dark-souls-remastered/`:
- `source` — symlink only to the existing direct child of `~/Documents`, exact title, ignoring case only if unique.
- `private/prod.keys` — existing local keys copied once as a regular 0600 file; a differing existing copy is never overwritten.
- `shader-cache/` and `shader-cache-conflicts/` — isolated cache and immutable collision archive.
- `resultats/DarkSoulsRemastered-nxnative.ipa` and `resultats/dsr-build.log` — returned private IPA and bounded diagnostic.

No system packages, PC service or original game paths are modified. Existing TOTK, Metroid, Link's Awakening, Mario Odyssey and Echoes projects are unaffected. All data transfers go over Tailscale through fixed `dsr-*` SSH commands; original NSP and keys are never added to public Git history or published as Actions artifacts.

## One-time local setup and action

From Bash on CachyOS, after the commit has been merged to `main`:

```bash
(
set -euo pipefail
cd "$HOME/portage-ipados/ff-resonance/github-build"
test "$(git branch --show-current)" = main
test -z "$(git status --porcelain)"
git pull --ff-only origin main

bash security/setup_dsr.sh
python3 -m unittest -v security/test_cache_import.py security/test_dsr_gateway.py security/test_dsr_transfer.py security/test_dsr_setup.py

gh workflow run build-dsr.yml -R Domessy/ffr-ipados-build --ref main -f mode=build
gh run list -R Domessy/ffr-ipados-build --workflow build-dsr.yml --limit 3
)
```

This stops on a locally dirty or non-main checkout (it never overwrites local edits). Setup refuses any unexpected source symlink/extra NSP, nonempty malformed headers, unrecognized role, and key copy mismatch. A capitalization difference is resolved only for a unique direct child of Documents.

The workflow's `mode=build` runs source+runner checks before private transfer; a separate `mode=preflight` or `mode=keys-check` can be dispatched for diagnosis. It transfers two NSPs separately with numeric progress, compiles the IPA using offline Metal shaders, checkpoints the per-title shader CAS about every 12 min, and streams IPA and diagnostics privately to CachyOS. It can be restarted when its 265-minute build-process limit pauses with a safe cache checkpoint.

If setup reports unrecognized package role, inspect **filenames only** locally with `find "$HOME/Documents/Dark Souls Remastered" -maxdepth 1 -type f -iname '*.nsp' -printf '%f\n'`; do not rename/alter game assets as a first response. A filename without a version marker cannot attest to the encrypted update version.

For rollback, remove the per-title project root only after copying any IPA and logs you want retained, then revert the `dsr-` gateway dispatch in a separate commit when no build is running. The original Documents files remain untouched.
