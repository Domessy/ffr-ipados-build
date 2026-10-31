# Metroid Prime Remastered 1.0.0 — native iPadOS port

Status: prepared, not yet built; iPad Pro M5 game runtime not tested.

## Approach and compatibility

Use seedds/nxnative pinned to `2716f78f01e90a9f9bbf0d09e7a798903525962f`.
The existing profile `dm/games/010012101468C000/` covers:
- Game: Metroid Prime Remastered, title ID `010012101468C000`
- Version: 1.0.0 (v0), Switch SDK 12.3.1
- RomFS ~6.7 GB, ~40,483 shaders and ~20,233 vertex/pixel pairs
- Mac tested: menus, cutscenes and one minute of play on Frigate Orpheon,
  near 60 fps; iPhone/iPad have not yet been tested by the upstream author.
- Mac memory ~4.3 GB resident plus ~2.6 GB Metal allocations after loading
  the first area (not an iPad memory consumption measurement).
- Shader prewarm list is currently empty; slow first-launch pipeline
  preparation and shader stutters are possible.

Upstream per-game notes:
https://github.com/seedds/nxnative/blob/2716f78f01e90a9f9bbf0d09e7a798903525962f/dm/games/010012101468C000/README.md

The gateway detects optional update NSPs but does not transfer or apply them:
the validated profile is for base v0. Do not silently install an untested
update. MacNativeGames has no specific MPR implementation.

## Data isolation

User-selected source:
`~/Documents/Metroid Prime Remastered/`
Project-local folder:
`~/portage-ipados/metroid-prime-remastered/`

The source is exposed to the existing restricted SSH key only through the
owner-managed `source` symlink, which must point to an immediate child of
`~/Documents`. Only one unique base game NSP is routed. An exact title-ID
tag is expected if more than one NSP exists in the source folder.
The upstream extractor additionally checks internal game identity.

Private gateway commands:
`mpr-probe-v1`, `mpr-manifest-v1`, `mpr-read-base`, `mpr-read-keys`,
`mpr-read-cache`, `mpr-write-cache`, `mpr-write-ipa`, `mpr-write-log`.

The original NSP and private keys are never committed or included in GitHub
artifacts. The workflow only uploads the resulting IPA to CachyOS privately.
No system packages are added or changed on CachyOS.

## Setup and preflight

Run on CachyOS using the existing GitHub project clone:

```bash
cd "$HOME/portage-ipados/ff-resonance/github-build"
git pull --ff-only origin main
python3 -m unittest -v security/test_cache_import.py security/test_mpr_gateway.py security/test_mpr_transfer.py
mkdir -p "$HOME/portage-ipados/metroid-prime-remastered"
ln -s "$HOME/Documents/Metroid Prime Remastered" \
  "$HOME/portage-ipados/metroid-prime-remastered/source"
env SSH_ORIGINAL_COMMAND=mpr-probe-v1 python3 security/ffr_ssh_gate.py
env SSH_ORIGINAL_COMMAND=mpr-manifest-v1 python3 security/ffr_ssh_gate.py
```

Expected probe: `MPR_GATEWAY_V1`. Manifest prints
`010012101468C000 0 <actual base bytes> <optional update NSP count>`;
never invent package sizes. The symlink step must not overwrite an existing
`source` selection.

Start a preflight with no game transfer:

```bash
gh workflow run build-mpr.yml --ref main -f mode=preflight -R Domessy/ffr-ipados-build
```

If preflight succeeds, build the unsigned IPA:

```bash
gh workflow run build-mpr.yml --ref main -f mode=build -R Domessy/ffr-ipados-build
```

## First build attempt and key-transfer correction (2026-10-31)

- MPR preflight #1 passed.
- MPR build #2, run [41200169838](https://github.com/Domessy/ffr-ipados-build/actions/runs/41200169838), failed AFTER the entire 7,262,924,560-byte v0 NSP was transferred and verified, while reading private keys via `mpr-read-keys`.
- GitHub's only remote diagnostic was `FFR gateway failed: ValueError`. The underlying ValueError source was suppressed by the forced-command gateway, so the precise underlying exception has NOT been proven. No game compilation started; no shaders were compiled.
- Fix: use the existing shared and previously tested read-only `read-keys` command rather than the new MPR alias; transfer and sanity-check private keys BEFORE any large NSP upload. No private key values appear in public CI output.
- Introduce `mode=keys-check` to verify the keys and SSH route on a new ephemeral runner WITHOUT downloading game files or attempting a build.
- Require the keys-check run to pass before restarting `mode=build`. Never infer that the new route works until the keys-check returns success.

```bash
gh workflow run build-mpr.yml --ref main -f mode=keys-check -R Domessy/ffr-ipados-build
```

## Checkpointing is enabled from the first build

The MPR pipeline uses the existing append-only CAS backend with its own
cache separate from BOTW, FFR and TOTK.

- Restore `~/portage-ipados/metroid-prime-remastered/shader-cache/`
  via restricted SSH before sending the game source.
- Every 12 min, export completed CAS files and stream them back to CachyOS.
  Checkpoint at the end or upon orderly termination too.
- Send bounded private logs at the same intervals.
- SHA-based content-addressed files with conflicting versions are kept
  separately; do not silently replace existing shader objects.
- On restart, newly running nxnative uses the stored CAS. This recovers
  completed shaders under a compatible game/profile/toolchain revision.

Limits: source NSP is sent again in a new job; the extracted game directory,
entire build worktree, Xcode DerivedData and incomplete IPA are NOT backed up.
A sudden runner kill can lose shader work since the last interval, but prior
checkpointed shader objects remain on CachyOS.

No in-progress job is interrupted or changed by later GitHub commits.
The wrapper checks free disk (>7 GiB) and caps compile at 265 min in a
345-min hosted job so there is time to transmit results and checkpoints.

## Outputs

- IPA: `~/portage-ipados/metroid-prime-remastered/resultats/MetroidPrimeRemastered-iPadOS.ipa`
- Private log: `~/portage-ipados/metroid-prime-remastered/resultats/mpr-build.log`
- Shader CAS: `~/portage-ipados/metroid-prime-remastered/shader-cache/`

## Test plan

Validate on the iPad Pro M5 with LiveContainer + SideStore:
1. Launch and pipeline preparation.
2. Menus, controller/touch inputs, audio, opening movies.
3. Frigate Orpheon graphics (including volumetric fog), FPS, memory.
4. Save and reload, then longer gameplay with visor changes and room loading.

Upstream Mac testing cannot be extrapolated to iPad stability. No iPad IPA
or performance claim should be made until the user tests the result.
