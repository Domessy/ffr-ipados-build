# OOT2 v13 — préparation du 21 novembre 2026

## État

Branche experimental/oot2-v13-complete-upstream-20261121, depuis la v12. Source officielle figée **a63ca65115cbd586ccca3bedc4af89984eddf2e5**, **122 commits après v12** (28 puis94 relevés), chaîne réellement recalculée **26e1a5f38264**, recette **efd65d45793f2fd3d236a5d09b34175f15fad6dd341ced5a9331464ca33e4f1e**. Toutes les nouveautés de ces commits conservées, sans cherry-pick partiel. Au terme de la préparation, aucun build privé v13 n’avait été lancé. **Préparation terminée :préflight Apple public44929593636 SUCCESS**, compilation iOS et archives comprises. PR96 draft prête pour le build privé, lancé ensuite sous le run44930522270 (état courant en fin de document).

Le run v12 **44685671639** a terminé build et finish SUCCESS ; reprise non nécessaire. Livraisons et caches v11/v12 conservés. La livraison v12 doit encore faire l'objet d'un contrôle indépendant avant de l'annoncer vérifiée de bout en bout.

## Code et options

Profil officiel :alias virtuel8 Gio/réservation16.5 Gio pour la transition Chambre des Sages, écran Vert+4:3 avec caméra/HUD/menus adaptés et films16:9 ; table BAHS corrigée déjà en amont, aucune seconde transformation appliquée. Le vérificateur impose les empreintes des huit fichiers du profil, les42847 clés, les indices contigus et les tailles virtuelles. Les données des tables BAHS correspondent au rafraîchissement v12, seuls les commentaires diffèrent.

Chaîne :offsets runtime gather corrigés et helpers subgroup mesh hors ligne pour contourner un crash du backend Apple. Autres nouveautés complètes :staging libéré hors feedback Metal4, transition arrière-plan bornée, écritures périodiques des archives différées pendant le jeu, reprise NDVE après interruption compilateur, ordonnancement audio, correctifs textures/vues/blend, scans de tables réduits, sondages d'archives partagés et zstd sans sous-processus par fichier. Les gains FPS/mémoire M5 ne sont pas présumés. Le nouveau chargement des metallibs utilise des données possédées plutôt que des mappings retenus :cela corrige un épuisement d'adresses mais peut augmenter la mémoire résidente.

Exporter metadata-only rebasé sur le nouveau lib_from_map ; la propriété upstream des octets et le digest sont conservés, l'association du chemin et les constantes suivies sont réservées à OOT2_FULLWARM_TOOL. En production les macros restent les opérations originales. Fixture pullmain/Short4, constantes, fragment fusionné, profondeur et alias stage4/7 conservé. Le NUP éphémère est libéré après extraction, identité vérifiée, uniquement sans siblings ni DLC externe ; l'ancre a été adaptée à stage_external_dlc. Tests de refus/suppression réelle sur données synthétiques.

Défauts conservés :DM_GUEST_FILE=1,DM_NVN_RT_RECYCLE=1,DM_GFX_SCALE=1,DM_FPS_HOLD=off,DM_NVN_UPLOAD_IDLE_MS=2000,DM_NVN_UPLOAD_SRC_MB=96. Aucun aspect forcé par env.txt :le lanceur iOS amont choisit Match screen (auto) par défaut, et propose16:9 après correspondance des hooks.4:3 peut augmenter le coût GPU ; commencer les comparaisons au même format que v12. Documents/env.txt prioritaire.

## Workflow et transfert

Alias enregistré prebake-oot2-full-v8.yml, copie identique build-oot2-v13.yml. Inputs build / ipad-v13 / local-bundle. Build → resume éventuel sur Mac frais → finish ; seule pause75 avec cache durable autorise la reprise, une seconde pause/une vraie erreur échoue. Identités et chemins v13 séparés :shader-cache-v13,shader-cache-conflicts-v13,cache-transfer-v13, checkpoints/hostkits/slim/logs v13. Aucun index v12 relabellé. Snapshot SQLite+blobs et sorties Mac/iOS, chaînes et SHA contrôlés avant NUP ; export données avant index sans tri des blobs ; place disque contrôlée avant cache/NUP et après restauration ; progression transfert octets/pourcentage conservée. NUP toujours nécessaire par nouveau workspace Mac. RomFS original assemblé dans l'IPA sur CachyOS ; sources et données privées hors GitHub.

## Vérifications

**461 tests pipeline PASS**. **243 tests natifs comptabilisés,5 ignorés** sur CachyOS (Metal/GPU indisponibles). Suite ARM64 Unicorn des hooks OOT2 exécutée. Split complet186583 fichiers/42847 shaders :les quatre tables de données correspondent exactement au profil officiel, zéro RED. Réécriture réelle de main réussie :SCREEN_ASPECT=1,DYNAMIC_RESOLUTION=1 ; empreinte du binaire privé conservée localement. Préparation depuis fichiers propres et chaîne recomputée PASS. Quatre workflows/90 blocs shell vérifiés, DAG/pause/finish testé. Gateway déployé atomiquement (dépendances puis dispatcher), readiness v13 et v12 PASS, CAS v13 vide.

Préflight Apple réussi :outils verrouillés ; tests gather/mesh/shape/NUP/BAHS et mémoire (fixture native compilée avant sa suite Python) ; host Mac ;28 fixtures graphiques compilées dont lifecycle CPU exécuté ; producteur R/M réel et archives iOS/g17g synthétiques, réemploi et index stables ; app iOS de production compilée/éditée de liens. Les fixtures GPU ne seront pas exécutées sur le runner sans Metal4. Régression complète cinq jeux demandée (OOT2,Bananza pour gather/mesh, BOTW/TOTK pour mémoire/pipeline, Skywalker Saga pour blend/vues) :outil indisponible sur Linux à l'import libproc.dylib, aucun résultat GPU cinq-jeux revendiqué.

Preuves locales resultats/oot2-v13-{pipeline-tests,native-tests,private-split,rewrite,profile-verified,rewrite-verified,workflows,five-game-regression}-20261121.*. Données privées dans oot2-v13-split-20261121 et oot2-v13-rewrite-20261121, jamais dans le dépôt public.

## Protocole iPad après construction

Préserver sauvegarde et ancienne IPA. Comparer20 min de Kokiri puis intérieur/extérieur, mêmes options et16:9, Metal4 pipelines activé ; relever préchauffage, fréquence/durée des drops, porte brillante, feuilles caméra immobile, sols et fermetures. Refaire à chaud. Tester ensuite Picture shape/Match screen :HUD/menus aux bords, films non étirés, comparaison du coût GPU. La Chambre des Sages exige une sauvegarde qui atteint cette transition. Tester enfin arrière-plan/retour ; conserver log.txt, heure et JetsamEvent en cas de fermeture. Les défauts idle2000ms/source96MiB restent expérimentaux, A/B possibles avec0 une option à la fois.

PR96 draft. Premier contrôle public44929325351 arrêté avant conclusion pour limiter la suite gather aux réécritures CPU et aux tests du traducteur runtime (ampere_mem) ; la classe OnGpu suppose une exécution matérielle, indisponible sur le runner. Aucun test GPU runtime prétendu réussi. Le contrôle corrigé44929593636 a ensuite réussi.

Contrôle Apple public courant **44929593636**, commit8a1042f5425af00dffba3c875dace39a722cc80e :https://github.com/Domessy/ffr-ipados-build/actions/runs/44929593636 . Toutes les étapes réussies, compilation terminée le21 novembre à17:28 UTC (18:28 Paris). Métadonnées R/M, archives iOS/g17g, réemploi et app de production compilée/éditée de liens validés. Tests de préservation explicitement exercés sur les IPA/checkpoint/cache v12 ;14 tests de réception/reprise passent,461 tests pipeline au total. Au terme de la préparation, aucun build privé v13 n’avait été lancé.

## État final vérifiable

PR **96 draft** :https://github.com/Domessy/ffr-ipados-build/pull/96 . Code testé Apple au commit **8a1042f5425af00dffba3c875dace39a722cc80e** ; dernier commit fonctionnel identique. Les changements suivants ne touchent que documentation, tests de conservation v12 et docstring du gateway (corps strictement identique), vérifiés dans resultats/oot2-v13-apple-scope-20261121.json. Les461 tests pipeline du dernier état passent. Log public complet :resultats/oot2-v13-public-44929593636.log ; bilan :resultats/oot2-v13-prepared-20261121.json.

Le build privé v13 a été lancé ensuite sous le run44930522270 ; voir l’état courant ci-dessous. Chemin opérationnel prêt :workflow enregistré prebake-oot2-full-v8.yml sur la branche v13, mode=build/runtime_variant=ipad-v13/ipa_layout=local-bundle. NUP requis ; première CAS v13 vide. Ne pas modifier le pin ou importer les index v12 lors du lancement. Les preuves de compilation ne remplacent pas les essais de jeu sur M5.


## Run v13 lancé — 21 novembre 2026,18:31 Paris

**État courant :run44930522270 IN_PROGRESS**, https://github.com/Domessy/ffr-ipados-build/actions/runs/44930522270 . Branche experimental/oot2-v13-complete-upstream-20261121, commit **b5789daaaaaca5c6990df9a05266d2a5c08e1f87**. Inputs build/ipad-v13/local-bundle. Un seul dispatch HTTP204, aucun build actif ou en attente avant lancement. Source a63ca65115cbd586ccca3bedc4af89984eddf2e5, chaîne26e1a5f38264, implémentation identique à celle validée Apple44929593636 (diff documentation/tests/docstring seulement).

NUP sélectionné et identité validés, RomFS original prêt26247576430 octets, CASv13 vide attendue pour la nouvelle chaîne ; espace local libre2.0T. Sur le runner :checkout, tests pipeline et secrets réseau réussis ; préparation Xcode/Metal/nettoyage disque en cours au premier contrôle. Pas encore de transfert NUP ni de compilation du jeu à cet instant. Reprise automatique éventuelle et finish/assemblage CachyOS prévus. Pas d'IPA v13 livrée à ce stade. Toutes les versions précédentes conservées. Preuve :resultats/oot2-v13-run-44930522270-20261121.json.
