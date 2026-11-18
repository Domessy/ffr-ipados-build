# Audit nxnative OOT2 — 18 novembre 2026, après livraison v10

Référence installable : v10 livrée et vérifiée, source `e4b0d9b75d39c41c10fdcfec2f0b070df496d7e5`, chaîne `a9bfaeb9fa8c`. Main officiel figé lors de ce contrôle : `0b5fd6020093407af8bb5ad166e78e00bd2b7242` ; **50 nouveaux commits**. En-tête de chaîne officiel : **03a3ac831bfb**. La page README OOT2 a quatre commits nouveaux. `game.tsv`, `pso_manifest.tsv` et le reste du profil OOT2 sont inchangés : seul README.md diffère dans son dossier. Cet audit ne modifie ni l’IPA, ni le moteur, ni les shaders privés et ne lance aucun run.

## Nouveautés directement documentées sur OOT2

- **cd8c97e4 / PR2771 — stores couleur masqués** : suivi du masque physique réellement écrit ; évite des stores couleur lors de passes depth-only. Cas Kokiri docked, M6 : **55,4 Mio de stores évités à l’image 3600**, sept passes 1920×1080, nombre de passes et octets chargés inchangés. Premières mesures M2 Air : 29,5–35,5 Mo/frame. Ce sont des écritures/du trafic GPU, PAS une baisse établie de RAM résidente de cette taille ; gain FPS inconclusif.
- **083c5e4f / PR2889 — lectures de buffers read-only** : promotion vers l’espace constant des seuls shaders fragment dont l’analyse prouve l’éligibilité ; conserve bindings et représentation des lectures, refuse pointeurs/références qui s’échappent. Option DMSH_SCONST incluse dans les clés de cache/chaîne. Trois shaders benchmark recompilent après rebase ; mesure gameplay rapportée issue d’un build cut9p antérieur de l’auteur : 20,43→19,82 ms/frame sur M2 Air, shader isolé 17,1 % plus rapide et sortie identique. Pas une mesure du main actuel sur notre M5.
- **736a2ecb / PR1833 — recherche de pools mémoire dans les shaders** : vérification abrégée de la dernière entrée pour les lectures ; stores et atomiques gardent leurs plages exactes. Deux runs par version sur M6, Kokiri immobile : GPU médian **8,05→7,85 ms**. Validation M4 concerné encore ouverte, pas de mesure M5 iPad. Couplage ABI hôte/traducteur : ne pas reprendre un seul côté ni renommer les bibliothèques v10.
- **c25d4011 / PR1822 — microphone** : entrée micro optionnelle dans le launcher **Mac** pour Ocarina Mic Input. Pas de portage iPad ajouté dans dm/ios par ce commit ; ne pas présenter cette option comme disponible dans notre IPA.

## Autres changements du moteur pertinents pour une future IPA

- **5ca161f2 — préchauffage NVN2 task/mesh** : stage lu depuis shader_map, accepte stage mesh NVN2 7 puis normalise en stage hôte 4, déduplique les entrées normalisées. Peut éviter une préparation omise d’anciennes lignes ; ne prouve pas que les 164 lignes M de notre v10 vérifiée sont absentes/défectueuses.
- **64a1b8f6 + 3984f5aa — cadence display link** : maintien des images selon les ticks du lien et borne inférieure à zéro pour les métriques d’acquisition précoce. Pertinent au 60 fps sur lien 120 Hz ; pas une promesse de résolution des drops calcul/GPU.
- **efd1bddd + 4df29405 — résolution de textures** : petit cache par thread des conformités de classes Metal, puis références empruntées dans les durées de vie déjà protégées au replay ; réduit requêtes Objective-C et ARC. Tests de remplacement/retrait de texture et SDK iPhone documentés. Aucun gain mémoire/FPS OOT2 iPad mesuré.
- **2a67900b — buffers de commandes** : croissance géométrique et contrôle de dépassement, pour limiter les réallocations/copies sur grandes soumissions.
- **a739027a, 30d89215, 5916c3b5 — passes de rendu** : fusion plus efficace tout en conservant l’ordre des accès dépendants, et indépendance depth/stencil. Résultats autres jeux, transposition OOT2 à mesurer.
- **5012821e — anticipation des pipelines** : ne résout/alloue plus de textures futures dans la prédiction ; évite de fermer un encoder sous un draw demandeur. Régression prouvée Mario Kart World, bénéfice OOT2 non établi.
- **4f4bfb6a + 3443d482** : initialisation Metal sérialisée et attachement des seuls residency sets existants ; robustesse init/arrêt, cas classic/VM.
- Autres corrections de traduction (arrondis dirigés f32, i64→float, zéros signés, HFMA2, IDP, VABSDIFF, packing F2FP) intégrées au nouveau main, sans mesure spécifique OOT2 ici.

La page indique toujours que le hang GPU mesh global n’est pas établi comme corrigé. Pas de preuve d’une nouvelle correction vm-pageshortage/Jetsam spécifique à l’iPad. Une migration complète exigerait de vraies bibliothèques et archives de chaîne 03a3ac831bfb, puis validation native/iOS et M5 ; le checkpoint et les archives compilées v10 restent cohérents avec la v10 mais ne constituent pas les bibliothèques de cette nouvelle chaîne. Des backports hôte limités restent une option distincte à valider ; ne pas lancer automatiquement une compilation depuis cette simple demande d’audit.

Sources : [page OOT2 figée](https://github.com/seedds/nxnative/blob/0b5fd6020093407af8bb5ad166e78e00bd2b7242/dm/games/0400486024DEC000/README.md), [diff depuis v10](https://github.com/seedds/nxnative/compare/e4b0d9b75d39c41c10fdcfec2f0b070df496d7e5...0b5fd6020093407af8bb5ad166e78e00bd2b7242), [PR2771](https://github.com/seedds/nxnative/pull/2771), [PR2889](https://github.com/seedds/nxnative/pull/2889), [PR1833](https://github.com/seedds/nxnative/pull/1833).

## Historique exact des 50 commits

```text
0b5fd602 rewriter: avoid guest stack spills for x18 conditional selects
7493ce8c packing/shaders: refresh Fortune's Weave and Z-A maps (PR #2948)
831b22bb docs/mkw: record cold pipeline rerun on main
c84297cf host/movie: report NV12 keys for the loaded movie SDK (PR #2955)
501df0e2 opengl/textures: expand RED and RG uploads (PR #2955)
5df3dbe8 packing/shaders: reject stray BAHS descriptors (PR #2943)
e7dc2d9a host/account: return cancellation for offline network accounts
8da8081e game: Orbitals packs with the checked first-copy shader map
79f28b06 host/audren: pace burst refills and preserve PCM order (PR #2983)
48f6bd3b nvn/tests: stop swizzle image case when texture setup fails
b83913bc host/codec: forward C Opus calls on C++ decoder objects (PR #2974)
8da15b21 lint/c: clear geometry and haptics ratchet failures
cf4ff071 docs/mkw: record cold pipeline benchmark
736a2ecb chain/gmem: shorten raw load pool checks (PR #1833)
c48a98d5 host/input: select the Steam Link Xbox 360 HID layout (PR #2958)
5012821e nvn/pso: keep texture resolution out of pipeline lookahead
313f226c nvn/tests: use the wait counter in geometry replay
42d02fa8 packing/shaders: refresh Wonder and Mario Tennis Fever maps
5d101030 nvn/mdx: invalidate indirect masks after primitive barriers (PR #2945)
66cd8d8c host/input: restore left in the raw HID hat table (PR #2933)
a3663659 chain/ampere: translate VABSDIFF (PR #2053)
31b537f1 packing/uepak: read version 9 frozen pak indices (PR #2476)
2dacca8d chain/ampere: translate IDP dot products (PR #2052)
3984f5aa nvn/present: clamp early acquire lateness to zero (PR #1041)
c25d4011 host/audio: capture opt-in Mac microphone streams (PR #1822)
c379a903 chain/f2fp: honor packing modifiers (PR #2046)
64a1b8f6 nvn/present: hold queued frames by display link ticks (PR #1045)
6a4e3215 chain/i2f: round 64-bit inputs once (PR #2045)
c22f30a3 chain/rounding: honor directed f32 arithmetic (PR #2051)
3443d482 nvn/mtl: attach only existing residency sets
50bdfe87 chain/minmax: preserve NVIDIA signed-zero ordering
cd8c97e4 nvn/render: track color stores with the draw write mask (PR #2771)
4f4bfb6a nvn/mtl: serialize shared Metal initialization
4df29405 nvn/textures: borrow replay lookup results (PR #1473)
be4c103c chain/ampere: round packed HFMA2 once to half
50bb4ba1 mac: set the default task role for windowless games (PR #2876)
efd1bddd nvn/textures: cache Metal texture conformance per thread (PR #1467)
461a5f9f chain/rewrite: skip source scans that cannot match
a3e5ec1e nvn/texture: use the owning device's GOB order (PR #1257)
083c5e4f chain: promote read-only fragment storage buffers (PR #2889)
391c68f9 chain/ampere: translate HFMA2.MMA and preserve RELU NaNs (PR #2049)
a739027a nvn: continue render passes across independent depth and stencil use
631ceb39 host/threads: notify same-core handoffs when peers block
6212f018 chain/spirv: compare proven uniform bounds by row
eaf327a7 nvn/compute: honor guest barriers for unknown ranges
30d89215 nvn/mtl: merge face-split draws with independent accesses
2a67900b nvn/queue: grow command buffers geometrically
5ca161f2 nvn/pso: normalize NVN2 mesh stages during prewarm
2ddea510 nvn/queue: read replay timing through the pthread port
5916c3b5 nvn/mtl: scan compact binds when merging render slices
```

## Diff exact du README OOT2

```diff
diff --git a/dm/games/0400486024DEC000/README.md b/dm/games/0400486024DEC000/README.md
index 28dec822..c73ece96 100644
--- a/dm/games/0400486024DEC000/README.md
+++ b/dm/games/0400486024DEC000/README.md
@@ -211,4 +211,10 @@ Its 37 kernels that correct samples, NDSR's network among them, gave about 0.25
 ## Found on this game
 
+- [Masked color targets store back during depth-only draws](../../../docs/reference/rendering.md#masked-color-targets-store-back-during-depth-only-draws). The depth prepass loaded a 1440×810 RG11B10F color target in eight passes per frame with all channels masked off. The author reported 35.5 MB/frame less attachment-store volume in the first A/B and 29.5 MB/frame less in the follow-up on an M2 MacBook Air. GPU and frame-time results were inconclusive. [PR #2771](https://github.com/seedds/nxnative/pull/2771)
+
+  On an Apple M6 with macOS 27.2, the extracted fix saved 55.4 MiB of attachment stores at frame 3600 against `a3e5ec1e`, standing on the Kokiri Forest deck in docked mode. Seven 1920×1080 passes each dropped an 8,100 KiB color store. Both captures had 128 render passes and the same total attachment load bytes. Screenshots at frames 3000 and 3600 showed the same scene with moving leaves and fairies in different positions.
+
+- Device loads from read-only storage buffers cost GPU time in several of its hottest fragment shaders. The PR's three benchmark shaders still promote their buffers and compile after the rebase. The in-game measurement comes from the author's earlier cut9p test build. [Device loads from read-only storage buffers](../../../docs/reference/shaders.md#device-loads-from-read-only-storage-buffers)
+
 - [Raw global memory through a pointer read when the draw is bound](../../../docs/reference/shaders.md#raw-global-memory-through-a-pointer-read-when-the-draw-is-bound): the reported isolated culling-loop hang from an omitted pointer target; discovery now populates the existing raw table. On an Apple M6 (macOS 27.2, 2026-11-17), `f75708d176bb6591`, `47f9b38490dcf9a2` and `99280b7b8aae78df` compile with source `[0, 0]` (task storage slot 0, byte 0); their MSL is byte-identical to main `2925d7af`. These are partial three-shader builds, not stamped full libraries or a gameplay retest. The separate whole-mesh GPU hang is not established as fixed by this change.
 
@@ -322,5 +328,5 @@ Its 37 kernels that correct samples, NDSR's network among them, gave about 0.25
 - [Extended products behind spirv-cross's optnone helper](../../../docs/reference/shaders.md#extended-products-behind-spirv-crosss-optnone-helper): 348,587 constant divisions left as unoptimized calls; the Kokiri Forest deck 54.0 → 59.1 fps on an M4 Pro.
 - [HMMA chains keep their matrices in the SIMD-group](../../../docs/reference/shaders.md#hmma-chains-keep-their-matrices-in-the-simd-group): the NDVE movie networks behind the title and the opening, 14.8 → 11.4 ms of compute a frame on this M6.
-- [Raw global memory lookups that start from their last entry](../../../docs/reference/shaders.md#raw-global-memory-lookups-that-start-from-their-last-entry): the foliage, vertex and compute shaders read structures word by word through loaded addresses; about 2 ms less GPU a frame at the spawn point.
+- [Raw global memory lookups that start from their last entry](../../../docs/reference/shaders.md#raw-global-memory-lookups-that-start-from-their-last-entry): the foliage, vertex and compute shaders read structures word by word through loaded addresses; about 2 ms less GPU a frame at the spawn point. The shorter load check from [PR #1833](https://github.com/seedds/nxnative/pull/1833) took GPU p50 from 8.05 to 7.85 ms in the standing Kokiri Forest scene on an M6 (macOS 27.2, v131072, 1440×810 with MetalFX spatial to 1920×1080, two clean runs per build from the `c22f30a3` baseline). Presentation timing was unavailable. Retest on the affected M4 is open.
 - [The GPU idles with the next command buffer already committed](../../../docs/reference/frame-rate.md#the-gpu-idles-with-the-next-command-buffer-already-committed): the 25-40 ms frames.
 - [The uniform copy thread's hand-off convoys on its mutex](../../../docs/reference/frame-rate.md#the-uniform-copy-threads-hand-off-convoys-on-its-mutex): resolved. On one host build (M4 Pro) the replay thread spent half its busy samples in `ubc_wait`, 221-333k instructions a draw and 23-57 ms of submit CPU a frame against 38.9k and 7.1 ms with `DM_NVN_UB_COPY_THREAD=0`; about 35 shadows a frame that `um_overlay` writes into are now copied on the submit thread (PR #2078).
@@ -333,5 +339,5 @@ Its 37 kernels that correct samples, NDSR's network among them, gave about 0.25
 - [Textures made for GPU use kept from their CPU rewrites](../../../docs/reference/nvn-objects.md#textures-made-for-gpu-use-kept-from-their-cpu-rewrites): the terrain tiles' height, blend and hole maps rewritten as tile slots are reused; flat blue holes in the ground after an hour of play.
 - [`EventFd` needs no network](../../../docs/reference/services.md#eventfd-needs-no-network)
-- [No virtual audio input devices (SDK 22)](../../../docs/reference/audio.md#no-virtual-audio-input-devices-sdk-22)
+- [Virtual audio input streams](../../../docs/reference/audio.md#virtual-audio-input-streams-sdk-2122): enable Microphone in the Mac launcher and use the game’s Ocarina Mic Input setting for humming or playing an instrument.
 - [`nn::ndve`'s movie enhancement file](../../../docs/reference/shaders.md#nnndves-movie-enhancement-file)
 - [Task and mesh shaders in BNSH, and indirect mesh draws](../../../docs/reference/shaders.md#task-and-mesh-shaders-in-bnsh-and-indirect-mesh-draws)
```
