# Tears of the Kingdom 1.4.3 — nxnative iPadOS comparison

Status (2026-10-31): **workflow and synthetic tests staged on a separate branch; no TOTK nxnative run launched**. The existing MacNativeGames IPA is functional on the iPad Pro M5; do not overwrite it.

## Targets and dependencies

- Base title: `0100F2C0115B6000`; update: 1.4.3 / `v720896` (update title `0100F2C0115B6800`).
- Upstream: `seedds/nxnative` pinned to `6a787668a15e09f2ad1e688a525e29c97ca5467d`; upstream's TOTK profile explicitly targets this version.
- GitHub workflow: `.github/workflows/build-totk-nxnative.yml`, manually dispatched, `mode=preflight|keys-check|build`.
- Target device: iPad Pro M5, iPadOS 27.
- Separate target IPA: `ZeldaTOTK-nxnative.ipa`.
- Do not change or delete existing `ZeldaTOTK-MacNativeGames.ipa`.
- No scheduled workflow and no public IPA/game artifacts. All game content, Switch keys and diagnostic logs use the existing restricted Tailscale+SSH route, never git.

## Safety and separation

The current Metroid Prime Remastered #5 build may be running. **Do not touch the local working checkout of the forced SSH gateway while it is running. Do not launch TOTK nxnative actions yet.** Staging files on a remote GitHub branch does not modify the local gateway or the Metroid run.

Local dedicated root (only configure after Metroid finishes):

`~/portage-ipados/zelda-totk-nxnative/`

Required private resources:
- `source` is a local symlink directly to the existing `~/Documents/The Legend of Zelda Tears of the Kingdom/` directory.
- `private/prod.keys` is a **regular, private copy** of the keys stored in the TOTK source directory. It must not be a symlink to a deleted legacy game project.
- `shader-cache/`, `shader-cache-conflicts/`, and `resultats/` are project-isolated.
- The output is `resultats/ZeldaTOTK-nxnative.ipa`; diagnostics `resultats/totknx-build.log`.

After the Metroid job terminates and no other game build uses the checkout, prepare the files:

```bash
ROOT="$HOME/portage-ipados/zelda-totk-nxnative"
SRC="$HOME/Documents/The Legend of Zelda Tears of the Kingdom"
test -d "$SRC" && test -s "$SRC/prod.keys" || exit 1
mkdir -p "$ROOT/private" "$ROOT/resultats" "$ROOT/shader-cache"
chmod 700 "$ROOT/private" "$ROOT/resultats" "$ROOT/shader-cache"
if [ ! -e "$ROOT/source" ] && [ ! -L "$ROOT/source" ]; then
  ln -s "$SRC" "$ROOT/source"
fi
test "$(readlink -f "$ROOT/source")" = "$(readlink -f "$SRC")" || exit 1
if [ ! -e "$ROOT/private/prod.keys" ] && [ ! -L "$ROOT/private/prod.keys" ]; then
  install -m 600 "$SRC/prod.keys" "$ROOT/private/prod.keys"
fi
test -f "$ROOT/private/prod.keys" && test ! -L "$ROOT/private/prod.keys" || exit 1
chmod 600 "$ROOT/private/prod.keys"
```

Use the same local project checkout that the forced SSH key currently executes. Before switching to the feature branch, verify no active job still needs the old gateway:

```bash
cd "$HOME/portage-ipados/ff-resonance/github-build"
git status --short
git fetch origin
git switch feature/totk-nxnative-preflight
python3 -m unittest -v security/test_cache_import.py security/test_totknx_gateway.py security/test_totknx_transfer.py
SSH_ORIGINAL_COMMAND=totknx-probe-v1 python3 security/ffr_ssh_gate.py
SSH_ORIGINAL_COMMAND=totknx-manifest-v1 python3 security/ffr_ssh_gate.py
```

Do not force-switch a dirty checkout; preserve local edits. Gate output should report `TOTKNX_GATEWAY_V1`, and the manifest should contain title/version plus positive sizes. The remote GitHub runner cannot see newly committed gateway commands until these changes are installed on CachyOS.

## Controlled run sequence (not started)

Only when Metroid is finished and the local setup/tests pass:

```bash
gh workflow run build-totk-nxnative.yml --ref feature/totk-nxnative-preflight -f mode=preflight -R Domessy/ffr-ipados-build
```

If the preflight passes and there is enough runner disk for the original NSP bytes (base `17,150,647,554`, update `526,970,136`, to be rechecked against the local manifest), the build may subsequently be dispatched with `mode=build`. The preflight **does not transfer any NSP or keys**; it checks the private command gateway, compiler compatibility, and free runner capacity. `mode=keys-check` tests key transfer without NSPs but does move key bytes to the ephemeral runner and should only be used deliberately.

The build stage streams base/update NSPs with numeric byte-count validation, restores a dedicated `DMSH_CAS`, checkpoints changed shader-cache files to CachyOS periodically, and saves bounded private logs. Temporary original NSP copies are eligible for deletion only after the iOS shader stage is observed on the runner; source NSPs on CachyOS never change.

Preflight admission uses the greater of 55 GiB and twice the source NSP total plus 20 GiB, after dependencies. Build stops before sustained disk exhaustion and checkpoints shader work, but success on the GitHub-hosted runner is **not guaranteed**. Upstream nxnative currently documents memory and rendering issues for TOTK; these require real M5 validation.

## Scope of verification

- Unit tests are synthetic and use sparse PFS0 files and synthetic key contents, never actual game files.
- No workflow execution, SSH connectivity check, runtime test, successful package, or IPA-size result has been claimed here.
- The branch is intended for code review/preflight first. A successful workflow is insufficient to establish playability.
- Compare with MacNativeGames on the same iPad and settings: startup, graphics, actual FPS, temperature, memory/JetSam, controls and save/reload.
