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

## Disk budget — current blocker

The MacNativeGames builder enforces at least **60 GiB free** at the beginning of an iOS build with an update, when source and output share a filesystem and the game data has not previously been extracted. This condition holds even for `--ios-game-data documents` on a fresh build.

The source NSPs together are approximately 17.68 GB (16.46 GiB). Our previous `xcode-27` BOTW preflight left ~55.6 GiB free BEFORE transfer. A conservative admission threshold for full MNG processing is 63 GiB plus the byte size of both NSPs, about 79.5 GiB. Consequently, a normal `xcode-27` runner **will be rejected before transferring private files**. This is intentional; it is not a failed port or an MNG incompatibility.

Do not patch out the upstream disk check without measuring realistic peak usage or obtaining a technically justified alternative. Options for a later change include a runner with more storage, verified alternate APFS volume arrangement, or a remote read-only source mount with suitable isolation. None has yet been implemented or validated.

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

Only if the preflight's capacity check passes, select `mode=build`. No actual MNG IPA has been produced yet.

## Diagnostics

- Private GitHub Actions logs show numeric source sizes, free disk capacity and per-NSP transfer counters.
- Full game tool output remains private in `~/portage-ipados/zelda-totk-mng/resultats/totk-mng-build.log`.
- Output IPA, if eventually built: `resultats/ZeldaTOTK-MacNativeGames.ipa`.
- Separate GameData when `package=slim`: `resultats/TOTK-v143-romfs.bin`.

No workflow is scheduled to auto-trigger. No actions in this project modify the user's system outside the project directory, nor can they install applications on the iPad without a separate device interaction.
