# OOT2 v12 — préparation du prochain run (19 novembre 2026)

## État

Branche **experimental/oot2-v12-complete-upstream-20261119**, depuis la v11 livrée. Source officielle figée **087faba98da29811e59e52658e1d51715258830e**, les 51 commits audités après v11 intégrés, chaîne recalculée **d80be0f9fadd**, recette **caafe78d258293a055ada7d6fa6a052883eefde61d4e2f9e46d1c3f872186965**. Migration complète, sans renommer les bibliothèques v11. IPA et caches v11 conservés. Aucun build privé du jeu lancé pour cette demande de préparation. Validation Apple publique à exécuter avant de déclarer la préparation terminée.

## Changements

Quatre correctifs mémoire : marge des grandes cibles recyclées plafonnée à4 MiB, zéro-remplissage par bandes utilisant le tampon4 MiB, libération du staging terminé au repos, budget des sources zéro-copie par lot. Réglages expérimentaux intégrés : **DM_NVN_UPLOAD_IDLE_MS=2000**, **DM_NVN_UPLOAD_SRC_MB=96** ; comparaison M5 encore ouverte, remise à0 possible dans Documents/env.txt pour A/B. Valeurs retenues parmi les essais amont, pas un gain iPad affirmé. Défauts v11 conservés : DM_GUEST_FILE=1, RT_RECYCLE=1, GFX_SCALE=1, FPS_HOLD=off. Empreinte des défauts liée à la recette et contenu intégré contrôlé à la réception.

Optimisations du traducteur/compilateur : variantes vertex groupées, noms d’entrée pull/vin lus dans la réflexion, scans de gardes abrégés, ainsi que les autres nouveautés main (staging iOS, HUD initial, correction d’adresses mesh, attentes relatives). Nouveau fixture du préchauffage force une conversion Short4 et une entrée pullmain distincte pour vérifier le parcours de noms d’entrée, en plus des constantes, des passes de profondeur, du fragment fusionné et des alias stage4/7. Exporteur uniquement sous OOT2_FULLWARM_TOOL ; comportement ordinaire de production conservé. Chaîne d80be0f9fadd réellement recalculée avant/après adaptation.

## Workflow

Chemin enregistré à dispatcher sur cette branche : **prebake-oot2-full-v8.yml**, copie identique **build-oot2-v12.yml**. Inputs mode=build/runtime_variant=ipad-v12/ipa_layout=local-bundle. Trois jobs : build → reprise éventuelle → finish. Seul le code75 du wrapper, après accusé d’un cache durable non vide, produit state=paused ; resume démarre sur un Mac frais et restaure automatiquement cette CAS. Une deuxième pause ou une vraie erreur échoue explicitement. finish s’ouvre uniquement après state=ready et checkpoint compilé accusé, ou sur mode=finish explicite. Les checkpoints et hostkits sont ignorés tant que la compilation est en pause.

CAS et conflits dédiés **shader-cache-v12 / shader-cache-conflicts-v12**, route fixe de sauvegarde et restauration auto vide/présente. Aucun index ancien importé dans la nouvelle chaîne. Snapshot vivant vérifié par SHA256, taille, inventaire, intégrité SQLite et tous les blobs, complétude des sorties Mac/iOS et chaîne de chaque réflexion ; ouverture par Store natif avant NUP. Préflight disque après cache avant NUP. Budget dynamique345 min/job, réserve15 min et sauvegardes périodiques conservés. NUP encore requis pour chaque nouveau workspace Mac ; l’IPA complète et son RomFS restent assemblés sur CachyOS. Les optimisations de variantes réduisent du travail de compilation, gain total OOT2 non encore mesuré.

## Validations locales

Préparation d’une copie propre réussie. Split complet des originaux : **186583 fichiers /42847 shaders**, aucune erreur ; toutes les tables correspondent exactement au profil corrigé BAHS, même rafraîchissement public qu’en v11. **440 tests pipeline PASS** (dont pause durable, erreur non masquée, reprise unique, anciennes chaînes refusées, défauts empaquetés et workflow). **196 tests natifs exécutés,3 skipped**, sans erreur : réécritures, cache toolchain, code_fp, pso_offline, lecteur BAHS, chaîne et split strict. Les tests nécessitant des outils Apple ne sont pas prétendus exécutés sur Linux. Quatre workflows YAML et chaque bloc shell validés ; dépendances DAG et conditions de checkpoint/finish testées. Gateway déployé atomiquement, dispatcher dernier ; readiness v12/v11 PASS ; CAS v12 actuellement vide, ce qui est normal pour cette nouvelle chaîne.

Tentative de scripts/regress.py check pour cinq jeux (OOT2, BOTW, TOTK, Pokémon Scarlet, Bananza) : indisponible sur CachyOS, import libproc.dylib échoue. Ces jeux couvrent mémoire/mesh/variantes/gardes ; aucune régression GPU cinq-jeux revendiquée. Préflight Apple prévu : suites du traducteur verrouillé, host Mac, sync-wait CPU,22 fixtures GPU compilées (pas exécutées sur VM), export R/M et archives iOS réelles, caches et index stables, entrée pull réfléchie, puis app iOS de production compilée/éditée de liens. Test M5 de la v12 encore requis.

Preuves sous resultats : oot2-v12-profile-verified-20261119.json, oot2-v12-workflow-check-20261119.json, oot2-v12-pipeline-tests-20261119.log, oot2-v12-native-tests-20261119.log, oot2-v12-five-game-regression-20261119.log. Split privé dans oot2-v12-split-20261119. Shaders extraits et données de jeu absents du dépôt public.

## Validation publique en cours et durabilité des sauvegardes

PR **95 draft** : https://github.com/Domessy/ffr-ipados-build/pull/95. Contrôle Apple public **44593528018**, commit e5f1a0d6e523c44326ac1d1c36ca15c79b6c11fb ; premiers tests réussis, compilation native/archives en cours. Aucun transfert de données privées dans ce contrôle.

Revue du transport : l’exporteur CAS envoyait les index avant les payloads par ordre alphabétique. Une coupure SSH pouvait donc exposer un index sans ses fichiers, malgré la conservation des versions. Correction générique : exporter toutes les données puis les index. Test reproduisant effectivement l’échec de l’ancien exporteur et la réussite du nouveau ; **441 tests pipeline passent**. Preuve resultats/oot2-v12-index-order-red-green-20261119.json. Cette correction du transport ne change ni source native, ni patch/recette, ni générateur d’archives testés par44593528018 ; la première étape de chaque job privé réexécutera les tests du dernier commit.
