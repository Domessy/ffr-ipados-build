# Zelda: Link's Awakening 1.1.0 → native iPadOS via nxnative

Status: isolated GitHub workflow staged; **no real NSP transferred or IPA compiled yet**.
Target iPad Pro M5 / iPadOS 27. Existing TOTK, Metroid, BOTW and other projects must remain unchanged.

## Game and provenance

- Nintendo Switch base title `01006BB00C6F0000`; update title `01006BB00C6F0800`.
- Supported nxnative build: **1.1.0 / v131072** (original base NSP + one update NSP).
- Upstream pinned to `seedds/nxnative@6a787668a15e09f2ad1e688a525e29c97ca5467d` (same checkout validated for TOTK).
- Profile: `dm/games/01006BB00C6F0000/`.
- Upstream has confirmed iPhone gameplay and targeted patches: depth mode, lower-left render origin, audio, hand-held crop, PhysX race.
- Known uncertainty: renderer still has open shader issues. No FPS or memory claim for the iPad M5.

## File and security layout

Original on CachyOS:
`/home/syssy/Documents/The Legend of Zelda Links Awakening/`
Two `.nsp` files (base/update) and local `prod.keys`. The original folder is never modified by setup or gateway.

Per-game isolated home:
`~/portage-ipados/zelda-links-awakening/`
- `source`: symlink to the original direct Documents subfolder
- `private/prod.keys`: owner-only regular copy, **not** a symlink, not committed
- `shader-cache/`: persistent isolated `DMSH_CAS` for checkpoints
- `shader-cache-conflicts/`: immutable hash conflicts
- `resultats/ZeldaLinksAwakening-nxnative.ipa`
- `resultats/zla-build.log`

The forced SSH gateway permits only fixed `zla-*` commands and denies shell commands and arbitrary paths. CI displays byte counts/progress, not original filenames, NSP content, keys or internal build logs.

## User-side setup after merge

```bash
cd "$HOME/portage-ipados/ff-resonance/github-build"
git status --short
git pull --ff-only origin main
bash security/setup_la.sh
python3 -m unittest -v security/test_cache_import.py security/test_la_gateway.py security/test_la_transfer.py
```

The setup checks PFS0 magic, two packages, distinct base/update name markers, supported update version where labeled, and private keys. The downstream nxnative extractor verifies actual internal title IDs, version, keys, and content integrity. If the fixed-code diagnostic reports `packages=fail`, inspect the filename markers with `find "$HOME/Documents/The Legend of Zelda Links Awakening" -maxdepth 1 -type f -iname '*.nsp' -printf '%f\n'` and adjust **only the gateway's identification rules** if necessary; never rename originals automatically.

## Run

```bash
gh workflow run build-zelda-la.yml -R Domessy/ffr-ipados-build --ref main -f mode=preflight
```

Preflight checks profile/toolchain, private gateway, original byte counts and admission capacity without transferring NSPs or keys. On success:

```bash
gh workflow run build-zelda-la.yml -R Domessy/ffr-ipados-build --ref main -f mode=build
```

Build streams base and update NSPs over Tailscale+restricted SSH, copies private keys to the temporary runner, compiles the iOS shaders and native binary via nxnative on Xcode 27.1, and returns the private IPA. The shader cache is checkpointed incrementally. The runner's own NSP copies may be deleted after extraction/shader stage; originals on CachyOS remain.

The compiler output is **not** available as a public GitHub artifact. Follow private diagnostics in the project-specific `resultats` directory if a build fails. For any new run, reserve capacity after reading actual NSP sizes; do not reuse TOTK byte counts.

## Verification boundaries

- Python shell syntax + synthetic tests run in the public branch CI, without Nintendo assets.
- Real source identity, iPadOS install/playability, FPS and memory use are **not verified** until the actual operator preflight/build and iPad test.
- No automated launch or installation on the iPad is implied by a successful GitHub job.
