# Tears of the Kingdom 1.4.3 — MacNativeGames port

Status: **successful first full-IPA build, user-confirmed functional on iPad Pro M5** (2026-10-31). Performance and long-session stability remain unmeasured.

## First successful iPadOS build (verified)

- GitHub Actions: [run #3 — 41181701484](https://github.com/Domessy/ffr-ipados-build/actions/runs/41181701484); all required steps completed successfully; workflow code commit `68bddaf9793571575e63105e6991b680c680968e`.
- Started 2026-10-31 07:43:09 UTC; workflow completed 11:03:26 UTC.
- MacNativeGames run reached stages 1/4 through 4/4, finishing compilation after **84 minutes** of reported builder time.
- Produced **18,752,345,605-byte full IPA** (`ZeldaTOTK-MacNativeGames.ipa`). Runner reports successful upload to CachyOS (`FFR_UPLOAD_OK`).
- Disk reached **16.8 GiB free** during IPA assembly in the public heartbeat; the 7 GiB safety guard was not triggered.
- The first launch is **confirmed functional by the user**, but no measured framerate, runtime stability, shader/pipeline warm-up time, or save-file restoration test was provided.
- **No GPU-specific pipeline archive** was compiled in this run (`GPU-specific archive=no`). A first-launch pipeline preparation may still occur.
- **Checkpointing was absent** from the successful workflow: raw NSPs, native build intermediates, translated shader seed, and Xcode DerivedData on the ephemeral runner are not preserved on CachyOS. Only the final IPA and build log were transferred. Future builds may repeat expensive stages.

Do not confuse a successful workflow with evidence that intermediate compilation checkpoints exist or that an installed iPadOS app has passed extended gameplay tests.

## Goals and isolation

- Source: two TOTK NSPs on CachyOS in a user-selected direct subdirectory of `~/Documents`.
- Runtime: `ly05010419/MacNativeGames`, pinned at `933b6a0d1438de160208a0a13eb5e8d7a2cb8094`.
- Separate GH Actions workflow: `.github/workflows/build-totk-mng.yml`.
- Existing `security/ffr_ssh_gate.py` only adds a fixed `totk-mng-` command namespace; FFR, Tales, Silksong and BOTW branches are unchanged.
- All game files, extracted files, system fonts, and Switch keys remain outside public GitHub.
- SSH returns two original NSP contents by role, six named font files (if available), and later receives private diagnostics, IPA and optional RomFS.
- Numeric progress for both NSP streams every ten seconds. The receiver verifies full byte counts and atomically publishes the temporary file.
- Dedicated CachyOS path: `~/portage-ipados/zelda-totk-mng/`. Link `source` to the actual Documents folder, keeping originals in place.

## Inputs

| Input | Meaning |
| --- | --- |
| `mode=preflight` | Check gateway, six font files, runner storage; no NSP transfer |
| `mode=build` | Attempt MNG build only if the same admission checks pass |
| `package=full` | IPA containing the game data |
| `package=slim` | Smaller IPA, external `TOTK-v143-romfs.bin` transferred separately |
| `device_gpu` | Optional verified Metal GPU architecture; leave unset until M5 identified |

Private folder for six files:
`~/portage-ipados/zelda-totk-mng/private/shared-fonts/`

Required names: `0-standard.bfttf`, `1-chinese-simplified.bfttf`,
`2-chinese-simplified-extension.bfttf`, `3-chinese-traditional.bfttf`,
`4-korean.bfttf`, `5-nintendo-extension.bfttf`.

The six genuine files must come from the owner's Switch firmware or an existing properly extracted font set. A guessed replacement or iOS system font is not accepted. The pinned MNG parser validates these before any app construction.

The existing FFR private `prod.keys` is reused behind the forced SSH key; its bytes are never committed or printed.

## Disk budget — staged build validated for first full IPA

Stock MacNativeGames requires at least **60 GiB free** when an iOS base+update build starts on a fresh shared work/output volume. The source NSPs require another ~16.46 GiB; with our earlier runner's ~55.6 GiB initially free, the stock workflow cannot start.

A pinned, fail-closed ephemeral-runner adapter (`security/totk_mng_compact.py`) **succeeded in the first full-IPA build**, without disabling the code/IVFC/hash checks:

1. After verifying the base RomFS and producing its overlays, delete the *redundant decrypted base RomFS copy* from the runner. The update merge reads the original base NSP directly, not that RomFS copy.
2. After the 1.4.3 update is merged and verified, extract the optional game icon, then delete only the *two staged NSP copies* in `$RUNNER_TEMP/totk-mng-nsp/`. They remain untouched on CachyOS.
3. Build the shaders and the **full IPA**, retaining the verified v143 RomFS image and sufficient free working space.
4. Only for this one environment, set the builder's initial disk admission to **34 GiB after source transfer**; leave its original requirement for all other builds. The workflow demands **37 GiB plus the exact input bytes before transfer**, **35 GiB after transfer**, and monitors a **7 GiB** free-space floor during the build. A failure aborts cleanly and sends private diagnostics.

In the successful run, the 56 GiB free after cleanup satisfied the ~53.5 GiB admission threshold. The observed minimum free space during final IPA assembly was 16.8 GiB. This validates the approach for this version and package mode on the reported runner, **not** for all runner images, device GPUs, upstream revisions, or higher disk demands. Preserve the safeguards.

## Build command on CachyOS

First install the newly committed GitHub scripts in the local project clone (the SSH forced command runs local code):

```bash
cd "$HOME/portage-ipados/ff-resonance/github-build"
git pull --ff-only origin main
python3 -m unittest -v security/test_totk_mng_gateway.py security/test_totk_mng_transfer.py
```

Then set `~/portage-ipados/zelda-totk-mng/source` to the game source folder and provide all six fonts in the private directory. Start:

```bash
gh workflow run build-totk-mng.yml --ref main -f mode=preflight -R Domessy/ffr-ipados-build
```

Only if the preflight capacity check passes, select `mode=build` and `package=full`. A full IPA build is the initial target; `slim` remains available as fallback. The compact build was successful once on the hosted runner; subsequent builds should retain all safety controls.

## Diagnostics

- Private GitHub Actions logs show numeric source sizes, free disk capacity and per-NSP transfer counters.
- Full game tool output remains private in `~/portage-ipados/zelda-totk-mng/resultats/totk-mng-build.log`.
- Successfully uploaded full IPA: `resultats/ZeldaTOTK-MacNativeGames.ipa` (18,752,345,605 bytes in build log; local hash not independently verified here).
- Separate GameData when `package=slim`: `resultats/TOTK-v143-romfs.bin`.

No workflow is scheduled to auto-trigger. No actions in this project modify the user's system outside the project directory, nor can they install applications on the iPad without a separate device interaction.

## Parallel comparison: nxnative TOTK 1.4.3 (planned, NOT built)

This remains a separate requested workstream. **Do not overwrite the known
functional MacNativeGames IPA.** The initial priority was MacNativeGames; the
nxnative TOTK route is retained for a side-by-side test on iPad Pro M5.

- Upstream nxnative already has a TOTK title profile at
  `dm/games/0100F2C0115B6000/` for **base v0 + update 1.4.3 (v720896)**,
  matching the user's original source files in
  `~/Documents/The Legend of Zelda Tears of the Kingdom/`.
- Upstream reports native iPhone operation with a 60 FPS frame-step path.
  This is not an iPad M5 performance measurement; recent upstream notes still
  flag transient high memory use and some rendering cases needing validation.
- Separate GitHub Actions workflow, separate local cache and output filename
  are required. Retain `ZeldaTOTK-MacNativeGames.ipa` unchanged.
- Reuse private, controlled reading of the two original NSP files already
  validated for the MNG build, but **do not depend on any deleted legacy
  FFR private-key path**. The user's TOTK source folder also contains its own
  `prod.keys`; keep key bytes private and use an isolated owned copy
  (no public upload, no symbolic reference to deleted game projects).
- Use checkpointed nxnative `DMSH_CAS` shader storage on CachyOS with
  periodic incremental snapshots and private diagnostic logs, ideally
  reusing proven BOTW/MPR helper behavior without mixing shader caches.
- Preflight disk capacity with real original NSP sizes: base
  17,150,647,554 bytes and update 526,970,136 bytes; account for large
  extracted RomFS and compilation/packaging overhead. Do not infer success
  from the MNG disk footprint, as the nxnative toolchain differs.
- Compare launch, visuals, FPS, thermals, memory, startup pipeline warm-up,
  save/reload, control mapping and longer gameplay on the **same** iPad M5.

As of 2026-10-31, **only the MacNativeGames TOTK build exists in our workflow**.
The nxnative comparison workflow has not yet been added or run. Do not launch
a second long build while the user's Metroid Prime Remastered runner is active,
unless the user explicitly prioritizes that scheduling.

## Next reliability work (NOT IMPLEMENTED)

The user correctly flagged the missing checkpoint mechanism before the initial run completed. The current workflow cannot resume its stage 4/4 from a canceled runner. Address this before substantial follow-on work:

1. Store private incremental checkpoints on CachyOS, inside `~/portage-ipados/zelda-totk-mng/checkpoints/`, with strict fixed SSH routes, atomic publishing, size limits, hashes, and a manifest binding the game/version/upstream SHA/Xcode/toolchain.
2. Make stage 3 shader seed and stage 4 iOS metallibs/Xcode outputs genuinely reusable after restoration; simply copying intermediate files is insufficient if the upstream build scripts unconditionally regenerate them.
3. Capture bounded private diagnostics during the job, not just on termination, without leaking keys/paths/game data in public GitHub logs.
4. Avoid redundant 17+ GB RomFS uploads; recomputing its verified extraction can be faster than transmitting it. Check actual checkpoint sizes/benefits before adding automatic uploads.
5. Add synthetic tests and a dry-run restoration test before enabling checkpointing by default. Preserve this successfully tested full-IPA workflow as a reference.

None of these reliability improvements should be described as completed until they are tested. No changes to the already installed TOTK IPA are required for documentation changes.
