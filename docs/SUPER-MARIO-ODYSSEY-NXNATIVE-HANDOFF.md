# Super Mario Odyssey 1.4.1 — native iPadOS (nxnative)

Status: code and synthetic GitHub CI prepared; real original NSPs, iPad IPA and performance **not yet validated**.

## Input and upstream

- Local original files: `/home/syssy/Documents/Super Mario Odyssey/` with two NSPs and `prod.keys`.
- Game Title ID: `0100000000010000`; update Title ID: `0100000000010800`.
- nxnative supported update: **1.4.1 / v393216** on base v0.
- GitHub-hosted toolchain: Xcode 27.1, pinned `seedds/nxnative@5ce955ada8b7b2a1369461aa1e2c89bbd093e52a` (2026-11-01).
- Upstream game profile: `dm/games/0100000000010000/`. The author reports iPhone gameplay; the user's iPad Pro M5 remains a separate validation target.
- Launch output: `SuperMarioOdyssey-nxnative.ipa`.

## Isolation and storage on CachyOS

Project root: `~/portage-ipados/super-mario-odyssey/`

| Path | Purpose |
|---|---|
| `source` | Symlink to the existing original Documents folder. Do not modify the originals |
| `private/prod.keys` | Owner-only regular copy of the game's private keys |
| `shader-cache/` | Isolated append-only shader CAS, reusable across build runs |
| `shader-cache-conflicts/` | Versions of conflicting cache artifacts |
| `resultats/SuperMarioOdyssey-nxnative.ipa` | The finished IPA, received privately |
| `resultats/ody-build.log` | Bounded private compile log |

The existing forced-command SSH gateway dispatches **only** allowlisted `ody-*` commands. Source transfer is read-only and restricted to the chosen original folder. Cache writes are append-only, and IPA/log writes occur atomically under this game's output directory. Public GitHub logs contain only numeric progress and counts; no game content or keys.

## One local command to prepare, test, and build

Use Bash on CachyOS. The directory `~/portage-ipados/ff-resonance/github-build` must remain the local Git checkout used by the restricted forced-command SSH key.

```bash
(
set -euo pipefail
cd "$HOME/portage-ipados/ff-resonance/github-build"
test "$(git branch --show-current)" = "main"
test -z "$(git status --porcelain)"
git pull --ff-only origin main
bash security/setup_odyssey.sh
python3 -m unittest -v security/test_cache_import.py security/test_odyssey_gateway.py security/test_odyssey_transfer.py
gh workflow run build-odyssey.yml -R Domessy/ffr-ipados-build --ref main -f mode=build
)
```

This dispatches a build **only when local setup and all synthetic tests pass**. The build itself starts with game and free-disk checks; keys and NSPs are not transferred before those admission gates. The forced SSH command can access the new code after the local `git pull`.

The game's NSP filenames must identify a v0 base and a 1.4.1 update, or use recognized title IDs. The gateway checks two regular NSP files, a PFS0 header and bounded lengths, but it **does not verify encrypted package internal metadata**. nxnative's extractor performs the definitive internal checks during build; if actual update is not v393216 it cannot be silently relabeled as such.

## Build behavior

- Workflow: `.github/workflows/build-odyssey.yml`, manual inputs `mode=preflight|keys-check|build`. Running `mode=build` always executes the same preflight admission before transferring originals.
- Fetch game NSPs and keys through Tailscale over the fixed SSH gateway, never a public GitHub artifact.
- Use an isolated ephemeral macOS runner and the pinned nxnative checkout; convert original AArch64 code and offline shader libraries into an iOS IPA.
- Stream incremental `DMSH_CAS` snapshots to CachyOS approximately every twelve minutes, with a final checkpoint on completion; if the runner approaches disk/time limits, a new run can reuse already checkpointed work.
- An unsuccessful compilation leaves existing game ports untouched. First-run cache and runtime memory may depend on the iPadOS version and signing container.
- On success the IPA appears under `resultats/`. The workflow does **not** automatically install it on the iPad.

## Known technical risks

The upstream Odyssey profile documents 27,984 shader programs and a large set of render-pipeline combinations. It includes fixes for motion-controller sampling, mist and fog, alpha of 2D HUD captures, depth behavior, and shader compilation. Geometry shaders in some effects are unsupported; a previously reported command-list heap problem is not yet tested in all kingdoms. Successful compilation and first launch therefore do not establish stable gameplay across the full title.

For iPad validation, check Cap Kingdom, Cascade Kingdom waterfall mist, menus and HUD, Cappy motion gestures, saves, a longer session and memory pressure. Avoid attributing any FPS improvement to unmeasured build options.

## Rollback

There are no system packages, permanent services, sudo changes or modifications to the original game directory in this setup. Removal of this game's local root after copying out any IPA or saves reverses the added workspace files. The `ody-` dispatch branch in `security/ffr_ssh_gate.py` can be reverted via a separate Git commit; do not remove it while a build uses it.
