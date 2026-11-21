# OOT2 v13 — préparation du 21 novembre 2026

## État

Branche experimental/oot2-v13-complete-upstream-20261121, depuis la v12. Source officielle figée **a63ca65115cbd586ccca3bedc4af89984eddf2e5**, **122 commits après v12** (28 puis94 relevés), chaîne réellement recalculée **26e1a5f38264**, recette **0a55055d5c8f861488c1a50d89845f6d12b1149bbccc8c04cd7d0cdcacae0739**. Toutes les nouveautés de ces commits conservées, sans cherry-pick partiel. Aucun build privé v13 lancé. Préflight Apple public à exécuter avant de déclarer la préparation terminée.

Le run v12 **44685671639** a terminé build et finish SUCCESS ; reprise non nécessaire. Livraisons et caches v11/v12 conservés. La livraison v12 doit encore faire l'objet d'un contrôle indépendant avant de l'annoncer vérifiée de bout en bout.

## Code et options

Profil officiel :alias virtuel8 Gio/réservation16.5 Gio pour la transition Chambre des Sages, écran Vert+4:3 avec caméra/HUD/menus adaptés et films16:9 ; table BAHS corrigée déjà en amont, aucune seconde transformation appliquée. Le vérificateur impose les empreintes des huit fichiers du profil, les42847 clés, les indices contigus et les tailles virtuelles. Les données des tables BAHS correspondent au rafraîchissement v12, seuls les commentaires diffèrent.

Chaîne :offsets runtime gather corrigés et helpers subgroup mesh hors ligne pour contourner un crash du backend Apple. Autres nouveautés complètes :staging libéré hors feedback Metal4, transition arrière-plan bornée, écritures périodiques des archives différées pendant le jeu, reprise NDVE après interruption compilateur, ordonnancement audio, correctifs textures/vues/blend, scans de tables réduits, sondages d'archives partagés et zstd sans sous-processus par fichier. Les gains FPS/mémoire M5 ne sont pas présumés. Le nouveau chargement des metallibs utilise des données possédées plutôt que des mappings retenus :cela corrige un épuisement d'adresses mais peut augmenter la mémoire résidente.

Exporter metadata-only rebasé sur le nouveau lib_from_map ; la propriété upstream des octets et le digest sont conservés, l'association du chemin et les constantes suivies sont réservées à OOT2_FULLWARM_TOOL. En production les macros restent les opérations originales. Fixture pullmain/Short4, constantes, fragment fusionné, profondeur et alias stage4/7 conservé. Le NUP éphémère est libéré après extraction, identité vérifiée, uniquement sans siblings ni DLC externe ; l'ancre a été adaptée à stage_external_dlc. Tests de refus/suppression réelle sur données synthétiques.

Défauts conservés :DM_GUEST_FILE=1,DM_NVN_RT_RECYCLE=1,DM_GFX_SCALE=1,DM_FPS_HOLD=off,DM_NVN_UPLOAD_IDLE_MS=2000,DM_NVN_UPLOAD_SRC_MB=96. Aucun aspect forcé :16:9 par défaut, Picture shape/Match screen disponible seulement après correspondance des hooks.4:3 peut augmenter le coût GPU ; commencer les comparaisons au même format que v12. Documents/env.txt prioritaire.

## Workflow et transfert

Alias enregistré prebake-oot2-full-v8.yml, copie identique build-oot2-v13.yml. Inputs build / ipad-v13 / local-bundle. Build → resume éventuel sur Mac frais → finish ; seule pause75 avec cache durable autorise la reprise, une seconde pause/une vraie erreur échoue. Identités et chemins v13 séparés :shader-cache-v13,shader-cache-conflicts-v13,cache-transfer-v13, checkpoints/hostkits/slim/logs v13. Aucun index v12 relabellé. Snapshot SQLite+blobs et sorties Mac/iOS, chaînes et SHA contrôlés avant NUP ; export données avant index sans tri des blobs ; place disque contrôlée avant cache/NUP et après restauration ; progression transfert octets/pourcentage conservée. NUP toujours nécessaire par nouveau workspace Mac. RomFS original assemblé dans l'IPA sur CachyOS ; sources et données privées hors GitHub.

## Vérifications

**461 tests pipeline PASS**. **243 tests natifs comptabilisés,5 ignorés** sur CachyOS (Metal/GPU indisponibles). Suite ARM64 Unicorn des hooks OOT2 exécutée. Split complet186583 fichiers/42847 shaders :les quatre tables de données correspondent exactement au profil officiel, zéro RED. Réécriture réelle de main réussie :SCREEN_ASPECT=1,DYNAMIC_RESOLUTION=1 ; empreinte du binaire privé conservée localement. Préparation depuis fichiers propres et chaîne recomputée PASS. Quatre workflows/90 blocs shell vérifiés, DAG/pause/finish testé. Gateway déployé atomiquement (dépendances puis dispatcher), readiness v13 et v12 PASS, CAS v13 vide.

Préflight Apple prévu :outils verrouillés ; tests gather/mesh/shape/NUP/BAHS et mémoire (fixture native compilée avant sa suite Python) ; host Mac ;28 fixtures graphiques compilées dont lifecycle CPU exécuté ; producteur R/M réel et archives iOS/g17g synthétiques, réemploi et index stables ; app iOS de production compilée/éditée de liens. Les fixtures GPU ne seront pas exécutées sur le runner sans Metal4. Régression complète cinq jeux demandée (OOT2,Bananza pour gather/mesh, BOTW/TOTK pour mémoire/pipeline, Skywalker Saga pour blend/vues) :outil indisponible sur Linux à l'import libproc.dylib, aucun résultat GPU cinq-jeux revendiqué.

Preuves locales resultats/oot2-v13-{pipeline-tests,native-tests,private-split,rewrite,profile-verified,rewrite-verified,workflows,five-game-regression}-20261121.*. Données privées dans oot2-v13-split-20261121 et oot2-v13-rewrite-20261121, jamais dans le dépôt public.

## Protocole iPad après construction

Préserver sauvegarde et ancienne IPA. Comparer20 min de Kokiri puis intérieur/extérieur, mêmes options et16:9, Metal4 pipelines activé ; relever préchauffage, fréquence/durée des drops, porte brillante, feuilles caméra immobile, sols et fermetures. Refaire à chaud. Tester ensuite Picture shape/Match screen :HUD/menus aux bords, films non étirés, comparaison du coût GPU. La Chambre des Sages exige une sauvegarde qui atteint cette transition. Tester enfin arrière-plan/retour ; conserver log.txt, heure et JetsamEvent en cas de fermeture. Les défauts idle2000ms/source96MiB restent expérimentaux, A/B possibles avec0 une option à la fois.
