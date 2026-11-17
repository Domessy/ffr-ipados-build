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

## Validated fix and full build relaunch

Public macOS validation **43938199620** succeeded on commit **314b8363212eebf878c561f30097b2defa98d2f9**: 143 pipeline tests, 47 locked-translator/Metal tests, production iOS compile/link, native CPU checks, real iOS/g17g render/mesh and specialized compute archive compilation/reuse. Loose and packed-image content-alias fixtures resolve real metallib paths; R=5, M=2, classified device-depth=2, failed=0. No GPU execution or M5 outcome claimed.

Corrected overlay SHA-256: `7ad87e9bafbcc4f85e2fdba6fdc1a02ecea7f3f67582e7b9e8318cd6c583c24f`. Operational independent CachyOS gateway manifest updated atomically; fixed v9 readiness route succeeds. Existing NUP, shaders and v8 IPAs preserved.

Full run **43939145417** dispatched with this validated code, build/ipad-v9/local-bundle/metal-snapshot: https://github.com/Domessy/ffr-ipados-build/actions/runs/43939145417 . The workflow retains the same mandatory public gates before private transfer. Full game build and iPad test remain pending. PR92 remains draft. Public validation proof: https://github.com/Domessy/ffr-ipados-build/actions/runs/43938199620 ; public log saved privately in resultats/oot2-v9-public-43938199620.log.

## Relance du 17 novembre 2026

À la demande de l’utilisateur, relance **43993999907** sur commit **40cb4cf91c1928cb92bc0ec73d8a08cf7a9ac0fd**, branche experimental/oot2-v9-chain-20261116, build/ipad-v9/local-bundle/metal-snapshot. L’ancien run 43939145417 est annulé pendant la compilation (dernier progrès 28 768/42 848, 67 %), pas un succès ni une nouvelle IPA.

Inventaire compilé local : **417 052 entrées, 32 078 528 079 octets**, contre 362 211 entrées dans l’ancienne archive de transfert. Régénération du snapshot en cours avant restauration, afin d’inclure les checkpoints du run annulé. Cache source et conflits conservés. Même chaîne réelle **9eecb8412308**, même code et options ; les bibliothèques compilées restent indexées par contenu et compilateur, sans renommage d’anciens shaders vers une nouvelle chaîne. Les traductions et index de reprise v8 ne sont pas injectés dans v9. Le contrôle du manifeste de passerelle et la route locale v9 réussissent. La validation Mac préalable 43938199620 reste applicable (modification documentaire seulement depuis le code testé).

Run : https://github.com/Domessy/ffr-ipados-build/actions/runs/43993999907 . Reprise effective des shaders sur le runner à confirmer après restauration ; ne pas confondre le progrès atteint avec le dernier checkpoint sauvegardé.

Snapshot actualisé et publié : **417 052 entrées**, **412 943 blobs**, 32 078 528 079 octets sources ; SQLite 33 331 265 536 octets ; transfert compressé **17 968 407 197 octets (16,73 Gio)**. Empreinte d’inventaire `c8681ff5fbd677819aa99052f13029824ab5ebe3b537afe98588ee081a7abf79`. Construction SQLite/quick_check et compression terminées sans erreur. Route SSH fixe confirmée sur ce nouveau snapshot avant restauration. Le run est en installation/validation nxnative ; le transfert effectif reste à terminer automatiquement. Preuve locale : resultats/oot2-v9-relaunch-cache-20261117.json.

## Timeout 43993999907 et reprise exacte v9 — 17 novembre 2026

Run annulé par la limite du job : 345 minutes (01:14:16–06:59:51 UTC). La compilation de l’IPA **a réussi à 06:53:06 UTC** ; kit v9 privé rapatrié (54 373 453 octets). Préparation native réelle : **R=2691, M=164, passes depth classifiées=13, échec=0**, puis **12/12** groupes R/M compilés. Arrêt durant AOT bases/compute à ~150 s ; aucune IPA finale rapatriée. Ces archives R/M et le slim étaient sur le runner éphémère et ne sont pas considérés récupérés. Les shaders et le kit locaux sont conservés.

Cause opérationnelle : 3 h 30 de transferts, puis retraitement des traductions car le snapshot Metal seul ne contient pas leurs index. Correction : route **resume-v9** indépendante de v8, vue par liens durs sélectionnant uniquement les index CODE_FP **da13969b5e94fb5c63625b3deadc1ce5ddf41adffc521b588dfe2d8747e9fd38**, issus des checkpoints v9 ; **42 848 index**, **247 591 fichiers**, 9 641 800 764 octets logiques, SQLite 9 771 204 608 octets, **2 389 805 212 octets compressés (2,23 Gio)** au lieu de 17 968 407 197 (16,73 Gio, réduction ~87 %). Pas de copie d’anciennes chaînes sous une nouvelle identité. Sources, conflits et caches v8 préservés. Choix du même Python 3.15 ; garde d’empreinte avant tout transfert.

Ajout d’un checkpoint privé de l’IPA compilée **avant** les archives. Validation ZIP/CRC, bundle, ARM64, tables, chaîne unique v9 ; stockage distinct `ZeldaOcarinaOfTime-v9-unwarmed-checkpoint.ipa`, sans validation fullwarm ni assemblage final revendiqué. Le validateur final strict reste obligatoire. Cela permet une reprise future après compilation si les archives dépassent le budget. Le NUP doit encore être transféré pour cette relance (~1 h 53 au débit précédent) ; il ne faut pas annoncer un chemin sans NUP déjà opérationnel.

147 tests locaux réussis, incluant sélection de l’index compatible parmi les conflits sans écraser l’original, routage v9 distinct, rejet d’un mauvais host/ancienne chaîne et sauvegarde séparée d’un checkpoint sans annoncer une livraison finale. Syntaxe des scripts des trois workflows vérifiée. Validation Mac/Python 3.15 et hits effectifs de reprise encore à confirmer. Pas de nouvelle compilation native ni de changement de shader requis par cette correction du workflow.

### Validation et relance corrigée

Validation Mac **44043422421 : succès**, code **576071e**. Empreinte réelle Python 3.15 **da13969b5e94fb5c63625b3deadc1ce5ddf41adffc521b588dfe2d8747e9fd38** confirmée, 147 tests pipeline + 47 tests traducteur/Metal, compilation/lien iOS, checks CPU et archives iOS render/mesh/compute avec réutilisation synthétique réussis. Validation locale du kit sauvegardé : empreintes des 56 fichiers et chaîne v9 correctes.

**Nouveau run 44044285061** lancé sur ce code, build/ipad-v9/local-bundle/**resume-v9** : https://github.com/Domessy/ffr-ipados-build/actions/runs/44044285061 . Route forcée opérationnelle confirmée : 2 389 805 212 octets compressés, 9 771 204 608 octets SQLite, 247 591 entrées. Premier contrôle du run demandé ; fin de restauration, taux réel des hits, nouvel export checkpoint et livraison complète restent à constater. Pas de garantie de durée finale ni de gain M5 mesuré. Preuves : resultats/oot2-v9-recovery-20261117.json, oot2-v9-public-44043422421.log, oot2-v9-run-44044285061.json. PR92 reste expérimentale/draft.

## Run 44044285061 : délai au rapatriement, récupération sans NUP

Run annulé à la limite de 345 min (08:09:12–13:54:40 UTC). La reprise exacte a fonctionné : **42 848/42 848 shaders depuis le cache**, mais la finition iOS a encore pris 1 h 36. IPA compilée à 12:26:51 UTC, archives complètes réellement créées à 13:42:17 UTC (dont base/compute ~75 min). Transfert final interrompu après 12 min. Fichier privé reçu incomplet : **3 038 216 192 octets**, sans répertoire central ZIP ; ne pas installer.

Erreur reconnue du correctif précédent : la route checkpoint était dans l’allowlist mais absente de la délégation v9 du dispatcher principal ; sa chute dans le dispatcher retournait 0 sans action. L’étape de 2 s a donc faussement déclaré une sauvegarde. Correctif : délégation depuis l’unique table V9_ROUTES, rejet 126 des commandes déclarées sans implémentation, accusé de réception obligatoire avec taille exacte. Test de bout en bout via le vrai dispatcher, au lieu du module enfant seul.

Récupération locale vérifiée du transfert : toutes les **36 entrées de l’application** précédaient la grosse archive AOT tronquée, dont l’image shaders v9 complète de 5 050 455 626 octets, l’exécutable ARM64 et les tables/ressources. Décompression et CRC de chaque entrée validés ; octets compressés conservés exactement ; répertoire central reconstruit, archive incomplète exclue. L’original partiel est préservé. Checkpoint reconstruit **2 844 165 412 octets**, SHA256 **ad35ca6a65d16bd13da459d071841be6dc4c5eb5a290a275729a092e90787f60** ; chaîne 9eecb8412308. Fichier distinct `ZeldaOcarinaOfTime-v9-unwarmed-checkpoint.ipa` : intermédiaire, pas encore livraison fullwarm. Preuves `v9-recovered-checkpoint.json` et `v9-checkpoint.json`.

Nouveau mode **finish** : transfère uniquement ce checkpoint via route fixe, contrôle SHA256 et disque, refait les archives iPad puis rapatrie l’IPA pour assemblage local. Transfert NUP, cache shaders, compilation du jeu et reconstitution du moteur explicitement sautés. Moteur et bibliothèques du jeu réutilisés à l’identique. Le préchauffage doit être refait car son archive n’est pas complète dans les octets reçus. 152 tests locaux passent, dont ZIP64 récupéré avec octets identiques, rejet CRC/chaîne erronés, vraie délégation write/info/read checkpoint et rejet d’une commande orpheline. Syntaxe des deux workflows vérifiée. Validation native du précédent run reste applicable : pas de nouvelle modification moteur/shader. Nouveau lancement à consigner ci-dessous.
