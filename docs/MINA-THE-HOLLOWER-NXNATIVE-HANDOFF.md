# Mina the Hollower — native iPadOS exploration through nxnative

## Status and limits (2 November 2026)

The game is available on Nintendo Switch, but as of the pinned upstream revision there is **no curated nxnative profile** for base title ID `0100DCD01F306000`. The upstream `scripts/build_ipa_from_nsp.py` supports *unknown titles*: it surveys the extracted game, writes a proposed `game.tsv`, and attempts a best-effort iOS IPA. This is an experimental port; a successful job or generated IPA does **not** establish that the game boots or plays correctly.

Public title identification: `0100DCD01F306000`, update title `0100DCD01F306800`, to be checked against the user's source NSP by the native extractor. **No update version is assumed**. The setup/gateway never claim that the update version has been verified from an encrypted NSP.

- Original game folder: `/home/syssy/Documents/Mina the Hollower/` with **exactly two NSP files** (base and update) and `prod.keys`.
- Pinned nxnative upstream: `seedds/nxnative@54ab7b1059eae8524ff60a320ea66f6ebac16506`.
- Toolchain: Xcode 27.2 + Metal `32023.922`, verified for both macOS and iPhoneOS before contacting the local computer; no unsupported compiler bypass.
- Workflow: `.github/workflows/build-mina.yml`, modes `preflight`, `keys-check`, `build`. Build repeats preflight admission before accessing source files.
- **Unknown update version is handled without guessing.** Immediately after the two private NSP copies arrive on the runner, `security/mina_identify_update.py` builds the pinned `nx_extract` reader and checks encrypted base/patch CNMT records. It refuses an unexpected title, malformed metadata or nonpositive update version, then renames **only the runner's update copy** to `[v<N>].nsp` with its verified integer. This matters because the upstream script otherwise ignores a versionless update for a title without a registered profile.
- Mac build runner is temporary and has no persistent access to Nintendo content. No source NSP or keys are committed to GitHub; no public IPA artifact is produced.

## Data isolation

The one-time `bash security/setup_mina.sh` creates, under `~/portage-ipados/mina-the-hollower/`:

- `source` — read-only access via symlink to the existing original Documents folder; the script checks the exact name, allowing a unique capitalization variant.
- `private/prod.keys` — local regular 0600 copy only; no symlink and never overwrite mismatching existing keys.
- `shader-cache/` and `shader-cache-conflicts/` — separate append-only CAS and conflicts, saved about every 12 minutes in long runs.
- `resultats/MinaTheHollower-nxnative.ipa` — expected output, **only if a full build succeeds**.
- `resultats/mina-build.log` — private diagnostic.
- `resultats/mina-survey.md` and `resultats/mina-profile.tsv` — when the upstream exploratory survey/provisional profile exist, returned privately even on compile failure.

The forced-command gateway accepts only fixed `mina-*` routes, recognizes `PFS0` NSP headers and optional title ID/version *filename hints*, and validates the presence of exactly two regular NSP files. It does not decrypt Nintendo content or verify the internal version. nxnative itself makes those checks after transfer. The transfer uses atomic private temporary files and numeric-only public progress. File names and private keys are not printed into public Actions logs.

## Nonstandard local NSP filenames — 2026-11-02

The first `setup_mina.sh` reported `MINA_DIAG_V1 source=ok packages=fail keys=ok`. The old gateway classified both files by rigid filename hints, even for unprofiled games with no stable filename convention. The fix retains exactly two regular, bounded PFS0 files and checks explicit title/version hints, but when a role remains unidentified it can infer **the larger NSP as base and the smaller as update only when the sizes differ by more than 2×**. Conflicting explicit role tags still fail. This is an admission heuristic, **not** proof of NSP identities.

The Mac's `mina_identify_update.py` still uses the pinned encrypted `nx_extract --contents` reader and rejects a mismatched Application/Patch CNMT pair or invalid update version **before starting the game build**. Original NSP names and content never change.

Setup calls the redacted `mina-diagnose-v2` route. It reports source/packages/keys and one fixed reason category (count, size_or_role, header, title_id, version_or_name, file_type, source, role). If the local check still fails, collect that category plus a local listing of the two NSP basenames/sizes, **never the keys or NSP bytes**.

### Confirmed 1.0.5 filename classification defect

After the previous generic fallback fix, the user supplied the exact source basenames and sizes:

- `Mina the Hollower [0100DCD01F306000][v0].nsp` — 875425557 bytes (base)
- `Mina the Hollower v1.0.5.nsp` — 34497814 bytes (update)

The issue was not the volume or the keys. The update filename contained the game's title but lacked the literal word `update` and a Nintendo-style `[vNNN]` token; the classifier consequently marked it as **base** and rejected a duplicate base. The updated classifier recognizes commercial dotted versions `vMAJOR.MINOR.PATCH` greater than 1.0.0 as an update hint and retains checks against contradictory explicit IDs and `[vNNN]` values.

Synthetic tests now use exactly these two basenames and sparse files with the reported byte lengths. The actual encrypted update CNMT remains the authoritative check on the ephemeral Mac runner. Never equate displayed 1.0.5 with an assumed numeric Nintendo update version.

## 2026-11-02: encrypted CNMT inspector failure on first real transfer

The first actual `mode=build` passed Xcode 27.2, keys verification, local gateway and **both private NSP transfers** (875425557 and 34497814 bytes). It then failed before nxnative itself started: `MINA: encrypted package identification failed (RuntimeError)`. The old inspector swallowed the precise upstream .NET/LibHac error and did not preserve an inspection log, so the available public run does not identify whether `dotnet build`, the base `--contents` read or update `--contents` read failed.

Fix: `security/mina_identify_update.py` now performs the same strictly pinned `nx_extract` operations but emits only fixed `stage=build-inspector|base-contents|update-contents|validate-metadata|rename-update` and numeric statuses to public CI. It writes bounded (at most 1 MiB of each stdout/stderr per subprocess) detailed logs to the runner's `mina-inspection.log`. The workflow's `always()` cleanup uses the new fixed route `mina-write-inspection` to transmit that log privately to `~/portage-ipados/mina-the-hollower/resultats/mina-inspection.log`.

If the next run fails at the same location, inspect the **private** file locally and report only errors with secret/file paths removed. Never post `prod.keys`, tickets or NSP content. Unlike the previous `RuntimeError` summary, stage + exit status should identify which part of the tool failed. The inspector still must verify base Application CNMT and update Patch CNMT before renaming the runner's update copy; neither bypass this step nor assume that commercial `1.0.5` equals a specific integer Nintendo update revision.

## 2026-11-02: dotnet apphost exit 131 — runtime discovery

The follow-up real run `41439393008` confirmed:

- `stage=build-inspector; exit_code=0` — `dotnet build` successfully compiled nx_extract.
- `stage=base-contents; exit_code=131` — executing the generated native macOS `nx_extract` apphost failed before reading any metadata; it wrote 701 bytes to stderr.
- `update-contents` was not reached.

This is consistent with .NET runtime discovery when Homebrew supplies the CLI in a non-default installation directory. The pinned upstream nxnative script explicitly computes a `DOTNET_ROOT` for its own apphosts, while the previous standalone Mina inspector did not. To avoid changing the runner's global environment, the Mina inspector now invokes `dotnet <runner>/mina-nsp-inspection/nx_extract.dll <keys> --contents <package>`. The `dotnet` CLI (already used to build the tool successfully) finds the appropriate runtime relative to itself; the CNMT validation and private diagnostics remain unchanged. A synthetic regression test verifies the exact managed-DLL invocation and update copy rename.

**Important:** The private stderr contents have not been inspected; runtime discovery is a strongly supported hypothesis, not yet an empirically confirmed diagnosis. Verify the next real run. If it fails again, use `resultats/mina-inspection.log` on CachyOS, not the public GitHub log or key material.

## Execute on CachyOS after merge

```bash
(
set -euo pipefail
cd "$HOME/portage-ipados/ff-resonance/github-build"
test "$(git branch --show-current)" = main
test -z "$(git status --porcelain)"
git pull --ff-only origin main
bash security/setup_mina.sh
python3 -m unittest -v security/test_cache_import.py security/test_mina_gateway.py security/test_mina_transfer.py security/test_mina_setup.py security/test_mina_identify_update.py
gh workflow run build-mina.yml -R Domessy/ffr-ipados-build --ref main -f mode=build
gh run list -R Domessy/ffr-ipados-build --workflow build-mina.yml --limit 3
)
```

The GitHub runner selects Xcode 27.2, verifies the pinned nxnative compiler, checks the game source via fixed SSH routes, restores the Mina-specific shader cache, transfers the base and update NSP plus keys, verifies the encrypted package identities and the real update version, and runs the upstream auto-survey + provisional build. It streams the IPA back to CachyOS only on success; diagnostics (including the survey) are private and can guide future revisions.

If the workflow fails, inspect **only the private** `resultats/mina-build.log`, `resultats/mina-survey.md`, and `resultats/mina-profile.tsv`. A failed exploratory build is evidence of a missing or incorrect profile, unsupported rendering technique or incompatible binary, not automatically an NSP or keys issue. Do not disable compiler fingerprint verification or game file integrity to force success.

## Recovery, rollback and next steps

- No system packages, permanent services or original files change on CachyOS.
- To revert the workspace, remove only the Mina project directory *after saving any desired IPA, logs and shader CAS*. Revert the `mina-` gateway dispatch by Git commit only when there is no active build.
- If an IPA is produced, verify iPad Pro M5 first launch, input, menus, game saves, sound, shader rendering and memory before calling it playable.
- If no IPA is produced, use the survey/profile and compile logs to build and test a proper game profile or needed engine hooks; don't promise performance before device testing.
