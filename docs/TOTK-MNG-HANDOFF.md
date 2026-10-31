# Tears of the Kingdom 1.4.3 — MacNativeGames port

Status: implementation committed, not built or validated on the user's iPad.

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

## Disk budget — isolated staged-build candidate (not yet validated)

Stock MacNativeGames requires at least **60 GiB free** when an iOS base+update build starts on a fresh shared work/output volume. The source NSPs require another ~16.46 GiB; with our earlier runner's ~55.6 GiB initially free, the stock workflow cannot start.

A pinned, fail-closed ephemeral-runner adapter (`security/totk_mng_compact.py`) now attempts to reduce peak disk use **without bypassing the code/IVFC/hash checks**:

1. After verifying the base RomFS and producing its overlays, delete the *redundant decrypted base RomFS copy* from the runner. The update merge reads the original base NSP directly, not that RomFS copy.
2. After the 1.4.3 update is merged and verified, extract the optional game icon, then delete only the *two staged NSP copies* in `$RUNNER_TEMP/totk-mng-nsp/`. They remain untouched on CachyOS.
3. Build the shaders and the **full IPA**, retaining the verified v143 RomFS image and sufficient free working space.
4. Only for this one environment, set the builder's initial disk admission to **34 GiB after source transfer**; leave its original requirement for all other builds. The workflow demands **37 GiB plus the exact input bytes before transfer**, **35 GiB after transfer**, and monitors a **7 GiB** free-space floor during the build. A failure aborts cleanly and sends private diagnostics.

Given previous runner measurements, the new initial threshold is around **53.5 GiB**, potentially feasible. It is a reasoned experiment, not proof of peak consumption or gameplay stability. If the disk floor is breached, stop and collect the build log rather than disabling safeguards. No MNG IPA has yet been built through this compact path.

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

Only if the preflight capacity check passes, select `mode=build` and `package=full`. A full IPA build is the initial target; `slim` remains available as fallback. The compact stage has not yet been tested on a hosted runner.

## Diagnostics

- Private GitHub Actions logs show numeric source sizes, free disk capacity and per-NSP transfer counters.
- Full game tool output remains private in `~/portage-ipados/zelda-totk-mng/resultats/totk-mng-build.log`.
- Output IPA, if eventually built: `resultats/ZeldaTOTK-MacNativeGames.ipa`.
- Separate GameData when `package=slim`: `resultats/TOTK-v143-romfs.bin`.

No workflow is scheduled to auto-trigger. No actions in this project modify the user's system outside the project directory, nor can they install applications on the iPad without a separate device interaction.
