# OOT2 iPad v9 — official runtime and translator migration

Requested by the user on 16 November 2026: integrate the audited fixes, apply the translator optimizations and launch a run. Isolated branch `experimental/oot2-v9-chain-20261116`, draft PR [92](https://github.com/Domessy/ffr-ipados-build/pull/92), based on the previous experimental branch. No merge or device action.

## Immutable source and real translation

Upstream `87422462a4c020def29cc39d3042b08cc9eab02a`, chain **9eecb8412308**. The runtime includes pool Finalize reclamation (13c35e90), final command-buffer residence including snapshots/layer (83a74d7d), capture claims (75758b94), ordered lazy clears (c3afe786), unbounded indexed pending writes (2acc593b), reduced occlusion counting (0de2ac2e), and the other official changes in this snapshot. This replaces the older stack of backports, rather than applying that stack to a different source tree. Official depth-zero copies and indexed GPU-write commits remain implemented upstream.

Translator changes include raw-global-search sharing, MSL3.2 memory/execution barriers, corrected LDC immediate semantics, compute uniform handle origins and typed fragment outputs. Native binary, embedded source fingerprint, SPIRV-Cross, Metal toolchain and computed chain are verified before private transfers. The old d24 libraries or archives must never be renamed to the new chain. New libraries are actually translated/compiled; previously compiled identical Metal source may be reused through its content key.

The full-build path consumes the original NUP again for this migration. This is a one-off full translation path, unlike the previous host-only run. It restores the existing compiled Metal snapshot and checkpoints changed shader CAS entries to CachyOS; original NUP, caches and old IPA files stay intact. The new host kit is exported for future host-only work; it is a new-version input and is not accepted by v8's host-kit validator.

## Full prewarm retained

The official loader already opens bundled render/mesh prewarm archives. A hash-locked metadata-only export overlay records native function constants and uses the actual new `warm_parse`, `pso_desc`, pulling-layout selection and `mtk_desc4`. Export creates no pipelines and executes no game. Its public fixture covers render, mesh/task/no-task, constants and the native depth-only exception. Every recorded row must be archived or explicitly classified as native depth-only; missing/stale/failed rows fail the build.

After translation and unsigned iOS packing, `oot2_v9_archives.py` rebuilds pair/compute and complete native render/mesh archives for iOS/applegpu_g17g, then repacks the original executable/resources with the archives. Existing v8 archives stay separate. Receipt validates new chain, upstream/overlay identity, host hash, render/mesh coverage and every full-list archive's hash before CachyOS assembles RomFS.

## Defaults and private outputs

Preserve guest files, RT recycling, scaling tier 1 and the prior experimental profile's hold-off default. Documents/env.txt overrides remain authoritative. Do not conflate hold with frame buffering. No automatic device settings change.

- `OOT2HostKit-v9.tar.zst`
- `ZeldaOcarinaOfTime-v9-slim.ipa`
- `ZeldaOcarinaOfTime-ipad-v9-fullwarm-livecontainer.ipa`
- `ipad-v9-local-bundle-result.json`
- `oot2-v9-build.log`

Fixed v9 gateway routes have no caller-supplied path. Previous v9 outputs are preserved by content hash before replacement; v8 outputs are untouched. The registered fullwarm dispatcher is reused **on the v9 branch only**; its filename retains v8 for GitHub registration, while its displayed name and immutable recipe describe v9. No workflow registration change on main is required.

## Validation and remaining limits

142 local pipeline tests pass, including genuine-chain rejection of v8 input, host tampering and output preservation. 119 native cadence checks pass on Linux. Workflow shell syntax checked. Public run 43928096813 caught an omitted `--check-tools` argument in the validation wrapper before any private transfer; fixed in ff5c946. Current public validation: [43928334216](https://github.com/Domessy/ffr-ipados-build/actions/runs/43928334216).

Public gates: actual locked translator/Metal tests (raw search, MEMBAR/BAR.SYNC, LDC, typed outputs and chain), native CPU owner/pending writes/cadence, compilation of residency/capture-race/RT/lazy-clear/occlusion GPU fixtures, production iOS compile/link and real offline render/mesh archive generation/reuse from synthetic libraries. GPU fixture compilation is not execution. The five-game GPU regression and real OOT M5 behavior remain unmeasured in this Linux/GPU-less-runner environment. No FPS, memory or crash improvement is claimed yet. Final validation and private dispatch identifiers belong in the handoff.

## iPad protocol

Keep the previous IPA and saves. Compare the same save/route and options, with similar temperature. Three save loads, 10-minute Kokiri route and an area transition; then a longer route through the shadow-pool transitions if stable. Record memory/Jetsam, global/foliage flicker, missing surfaces, frame p95/p99, time at 30/60 and preparation first/second launch. Confirm archives are opened **and used**; opening a file alone does not prove coverage. Compare Handheld + MetalFX with hold on/off separately; no universal M5 gain follows from the M2 Max report.

## Dispatch with mandatory public gates

Run **43930899728** launched on code **8197d48d349f0b19e8d6f0e00b3579c34cf4a644**, branch experimental/oot2-v9-chain-20261116, mode build/local-bundle/metal-snapshot. The job is in progress. The same job runs locked-translator tests, production iOS compile/link, CPU ownership/write-index tests and genuine synthetic archive compilation/reuse before Tailscale or any private cache/NUP transfer. No claim of completed macOS validation at dispatch.

Local total is now 143 tests, including complete v9 reception/RomFS assembly and clean CRCs. 33 additional static source tests pass (one Metal-dependent case skipped); impact via dm/tools/usage.py records 4 affected games and 180 unknown, including OOT's missing manifest. The regress.py wrapper itself imports libproc.dylib even for impact, so the same static usage function was invoked directly on Linux; no GPU regression was run.

The first public wrapper issue and a macOS /var temporary-path test alias were corrected before this dispatch. Separate public run 43928774631 remained queued without a job; cancel and force-cancel were refused by GitHub with inconsistent queue state. It is a duplicate public-only validation, not another private build.

## Failed run 43930899728: exporter identity adaptation

Run failed in public synthetic preflight, before Tailscale, NUP/cache transfer or game shader compilation. The official runtime now tags MTLLibrary by content digest; the custom metadata exporter incorrectly consumed that tag as a resolvable metallib filename. Strict path validation rejected the resulting digest.

The v9 overlay now records an independent tool-only relative library source path for both loose and packed-image loads. Runtime digest identity and normal application behavior are preserved. No validator was loosened. Public regression exercises identical library bytes under several shader names, export from loose files and a packed image, resolving every emitted filename to the original bytes, and complete offline archive reuse. Local 143 tests pass; overlay applies to fresh upstream 87422462 and chain remains 9eecb8412308. macOS validation pending; no iPad behavior claim.
