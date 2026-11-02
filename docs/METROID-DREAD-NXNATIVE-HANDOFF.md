# Metroid Dread — nxnative Switch → iPadOS

## Status (2026-11-02)

The per-game, private native build workflow is prepared and synthetic CI is passing. The actual NSP source identity, update version, full IPA compilation and iPad Pro M5 gameplay **have not been validated** yet. No copyrighted game files or Nintendo keys are committed to GitHub or uploaded as public workflow artifacts.

The pinned upstream `seedds/nxnative@e5620b1a05a5b7374e0135d6312d3e90994eab81` contains a **curated** Metroid Dread profile at `dm/games/010093801237C000/`:

- Base title `010093801237C000`; patch title `010093801237C800`.
- Registered patch: **2.1.0 / v327680** on base `v0`. Upstream build registers the merged build ID for this update and may not support other versions. Explicitly **reject** a different real patch version after encrypted CNMT inspection; do not silently use another version or bypass the profile.
- Engine: MercurySteam, NVN, Nintendo SDK 11.4.3, modules main/subsdk0/sdk. Shaders: 478 `system/shd/*.bshdat` files, 1,342 stages / 1,010 unique shader keys (359 vertex and 651 pixel).
- Upstream README documents gameplay on an iPhone, gameplay target 60 FPS and cutscene target 30 FPS, but also notes that **iOS runtime validation for some movie synchronization and later rendering changes is outstanding**. Real iPad M5 device behavior cannot be assumed.

## Isolation and transport

Original source folder: `/home/syssy/Documents/Metroid Dread/`, with exactly **two NSPs (base and update)** and a local `prod.keys`.

`bash security/setup_dread.sh` uses a unique direct Documents folder matching the game name (case-insensitive only if unambiguous), preserves the existing NSPs without rename/move, and makes these private resources:

- `~/portage-ipados/metroid-dread/source` — symlink to the original folder.
- `~/portage-ipados/metroid-dread/private/prod.keys` — chmod 0600 local copy, never overwrite a mismatching prior copy.
- `~/portage-ipados/metroid-dread/shader-cache/` and `shader-cache-conflicts/` — independent content-addressed shader cache.
- `~/portage-ipados/metroid-dread/resultats/MetroidDread-nxnative.ipa` — expected private artifact **only after full compilation**.
- `~/portage-ipados/metroid-dread/resultats/dread-build.log` — private nxnative diagnostic.
- `~/portage-ipados/metroid-dread/resultats/dread-inspection.log` — bounded private encrypted CNMT / .NET inspector diagnostic.

The fixed-command `dread-*` SSH gateway is title-scoped and separate from previous projects. The local admission phase checks two regular `.nsp` files with `PFS0` headers, filenames/role hints, bounded file sizes and the private key copy. It can resolve ambiguous *filenames* using the clearly larger NSP as base only when the second is less than half as big; this heuristic is **never the final title verification**.

On the ephemeral GitHub Xcode runner, `security/dread_identify_update.py` builds the pinned `nx_extract` and runs its managed `nx_extract.dll` through the installed `dotnet` CLI (avoids macOS Homebrew apphost exit 131). It reads encrypted CNMT for the base Application and the Patch, verifies both expected title IDs and **exactly v327680**, then renames **only the runner's update copy** to `[v327680].nsp`. A different patch stops before shader compilation; private diagnostics return by fixed `dread-write-inspection` route.

The build selects Xcode 27.2 and requires **Apple metal 32023.922** for macOS and iPhoneOS, as required by the pinned nxnative shader lock. It does not override a mismatch. The shader CAS is checkpointed periodically and the IPA is returned only over the private Tailscale/SSH channel. No system-level CachyOS packages, permanent services or original NSPs are modified.

## Start the first real build

After merging the GitHub PR into main:

```bash
(
set -euo pipefail
cd "$HOME/portage-ipados/ff-resonance/github-build"
test "$(git branch --show-current)" = main
test -z "$(git status --porcelain)"
git pull --ff-only origin main

bash security/setup_dread.sh
python3 -m unittest -v \
  security/test_cache_import.py \
  security/test_dread_gateway.py \
  security/test_dread_transfer.py \
  security/test_dread_identify_update.py \
  security/test_dread_setup.py

gh workflow run build-dread.yml \
  -R Domessy/ffr-ipados-build \
  --ref main \
  -f mode=build
gh run list -R Domessy/ffr-ipados-build --workflow build-dread.yml --limit 3
)
```

The command intentionally stops on a modified/non-main local checkout rather than overwriting user edits. All workflow modes are dispatched manually: `preflight` (no game file transfer), `keys-check` (keys only), `build` (full run). The code and secrets remain separate. The script's first successful build is not proof of iPad playability.

## Diagnostics and rollback

If a source check fails, use the fixed `DREAD_DIAG_V2` reason code plus *names and sizes only* of the two NSPs. Do not publish keys or raw file content. If encrypted CNMT inspection fails, inspect `dread-inspection.log` privately. For nxnative compile/runtime failure, inspect `dread-build.log` or return it as a private attachment after removing secrets.

On a successful IPA, test actual launch, title/menu, in-game movement/shooting, input and audio, movie transitions, saves, thermal throttling and memory use on the iPad. The upstream Mac gameplay report does not replace this test.

Rollback is restricted to the new per-title project folder, preserving any IPA/log/cache the user wants. Revert the `dread-` SSH gateway dispatch only through a separate Git commit when no run is in progress. The original Documents folder and existing game projects are left untouched.
