# OOT2 v11 — intégration complète du 18 novembre 2026

## État

Branche `experimental/oot2-v11-complete-upstream-20261118`, PR94 draft : https://github.com/Domessy/ffr-ipados-build/pull/94. Migration de l’ensemble des 50 commits audités après v10, source officielle figée **0b5fd6020093407af8bb5ad166e78e00bd2b7242**, chaîne réellement recalculée **03a3ac831bfb**. Pas de sélection partielle, pas de bibliothèque v10 renommée. La v10 complète livrée, ses checkpoints, ses fichiers de contrôle et ses caches restent préservés.

Intègre stores couleur selon masque effectif, promotion des buffers fragment read-only, recherches abrégées des pools mémoire GPU, normalisation des stages mesh NVN2, cadence display link, caches de recherches de textures/références ARC, croissance géométrique des buffers de commandes, fusion et ordre de passes, barrières et masques indirects, initialisation Metal sérialisée, corrections numériques du traducteur et réécriture x18 CSEL. Le code micro récent est conservé dans sa portée officielle Mac ; aucune nouvelle option micro iPad n’est annoncée.

## Adaptations iPad/runner

Modules et chemins v11 distincts pour source, défauts, checkpoints, archives, logs et réception. Préparation refuse source/empreintes/chaîne inattendues. Seules adaptations locales : libération contrôlée de la copie NUP du runner après extraction et outil de métadonnées séparé sous OOT2_FULLWARM_TOOL. Ses variantes ordinaires conservent le comportement upstream ; toutes les nouveautés du renderer/traducteur sont prises depuis la source officielle.

Exporteur R/M rebasé : compte les identités mesh après la même normalisation que warm_parse (stage NVN2 7 vers hôte 4, déduplication par task optionnel et clé). Fixture synthétique fournit les deux écritures de stage pour chaque mesh. Archives natives iOS/g17g et index complets DMPSOIX2 restent obligatoires, contenus vérifiés par SHA256 avant assemblage du RomFS original. `DM_GUEST_FILE=1`, RT_RECYCLE=1, GFX_SCALE=1 et FPS_HOLD=off conservés.

Workflow prêt en deux jobs de 345 min : build → checkpoint durable avec accusé de réception exact, puis finish → archives et livraison. Mode finish relançable sans NUP/compilation jeu. Nouvelle chaîne : premier CAS vierge, aucun cache ancien arbitrairement requalifié. Réserve dynamique ajoutée : le budget du compilateur est plafonné au temps restant du job après transferts, moins 15 min de sauvegarde, avec plafond habituel 265 min ; refus avant lancement s’il ne reste pas une minute utile. Évite qu’un transfert lent rende le plafond fixe incompatible avec le délai global. Si une pause contrôlée intervient, les nouvelles entrées CAS sont conservées mais un snapshot exact de reprise doit être préparé avant relance ; le workflow fresh ne constitue pas une reprise automatique. Les tests couvrent le temps restant, l’expiration et l’absence de lancement du compilateur.

## Validation à ce stade

- Préparation d’un checkout propre officiel, empreintes, application contrôlée du patch, et chaîne recalculée après patch : PASS.
- **174 tests OOT2 / 414 tests sécurité** sous environnement réel ipad-v11/local-bundle : PASS ; anciens tests v10 conservés. Tests de routage via le vrai dispatcher, rejet des bibliothèques de chaîne v10, reçus/CRC/SHA et couverture/index manquants.
- Syntaxe de tous les blocs shell, inputs déclarés, égalité dispatcher-template : PASS.
- Gateway autonome déployé atomiquement, dépendances avant dispatcher ; readiness v11 ET v10 : PASS, RomFS original inchangé.
- Exécution ARM64 émulée du correctif x18 CSEL avec pile non mappée : **4 tests PASS** sous Unicorn 2.1.4, aucune omission de ce test sur CachyOS. Le runner Mac peut omettre l’exécution ARM64 optionnelle s’il n’a pas Unicorn ; ses contrôles statiques et sa compilation restent exécutés.
- Tests C de pacing exécutés sur CachyOS : link latch **13/13**, drain **92/92** PASS.
- Parseur C upstream exact (structures/normalisation/parsing, seul writer ObjC exclu de la fixture portable) sur le vrai manifest public : **R7138/M164 uniques normalisés, zéro clé invalide**, taille clé512. Aucun effondrement inattendu de la couverture après le nouveau dédoublonnage.
- Validation publique Mac/iOS **44383126199 SUCCESS**, commit156ab4e (patch natif et chaîne identiques au HEAD courant ; seul budget du wrapper a changé après le lancement). Suites traducteur élargies (wide/constant reads, raw-last et arithmétique Ampere), x18 select, construction complète host Mac, clés pipelines et ticks CPU exécutés, fixtures GPU compilées pour les changements, export natif synthétique avec normalisation mesh, vraies archives iPad render/mesh et compute, réutilisation du cache et index stables entre processus, compilation/édition de liens iOS de production.

Limites : runner virtuel sans GPU Metal4, donc pas d’exécution des fixtures GPU ni de benchmark M5. Régression gameplay cinq jeux impossible ici (CachyOS, pas de Mac/corpus multi-jeux local) ; ne pas annoncer cette vérification comme passée. Gain FPS/mémoire/rendu, ouverture et hits des archives sur iPad restent à mesurer. Le hang GPU mesh global n’est pas établi comme corrigé par l’amont. Aucun build privé du jeu ni nouvelle IPA v11 lancé/livré à ce stade de l’implémentation.

Après production d’une IPA : conserver save et options comparables à v10, Metal4 pipelines activé ; deux démarrages chronométrés, trois chargements de save, dix minutes Kokiri puis transition ; noter chutes FPS (fréquence/durée), scintillements/textures/lignes, crash/heure et JetsamEvent éventuel. La recette nouvelle exige bibliothèques et archives de la nouvelle chaîne ; ne pas installer un checkpoint/slim comme livraison finale.

## Validation terminée

**44383126199 SUCCESS**, contrôle achevé le 18 novembre vers 20:53 Paris. Tous les chemins du script public ont terminé : suites traducteur verrouillé, construction du moteur Mac, compilation des 14 fixtures ciblées, exécution CPU des clés pipelines et ticks/latch/drain, fixture R/M avec alias stage7/4, archives iOS/g17g render/mesh/compute, réutilisation et stabilité des index, puis build iOS de production. Source native, patch, recette et outils d’archives au HEAD identiques octet pour octet au commit156ab4e testé ; commits ultérieurs limités au budget du wrapper, tests associés et documentation. Vérification d’identité effectuée localement.

Preuves : resultats/oot2-v11-implementation-20261118.json, oot2-v11-public-run-44383126199.json, oot2-v11-public-44383126199.log, oot2-v11-profile-keys-20261118.json, script reproductible oot2-v11-profile-key-check.py, et oot2-v11-x18-select-20261118.log. Implémentation prête pour le prochain build privé : workflow_dispatch prebake-oot2-full-v8.yml sur experimental/oot2-v11-complete-upstream-20261118, inputs mode=build, runtime_variant=ipad-v11, ipa_layout=local-bundle. **Aucun run privé de jeu lancé par cette demande d’implémentation ; IPA v11 encore à construire.** Tester la v10 existante reste utile comme référence M5. PR94 reste draft pour distinguer vérification de compilation et validation appareil.

## Lancement du build privé v11 — 18 novembre 2026

Utilisateur : « Vas y ». **Run [44385904117](https://github.com/Domessy/ffr-ipados-build/actions/runs/44385904117)**, commit **f321004d038c0e4290488599f245640b1c0bda6d**, mode=build/runtime_variant=ipad-v11/ipa_layout=local-bundle, source **0b5fd6020093407af8bb5ad166e78e00bd2b7242**, chaîne **03a3ac831bfb**. Validation Mac/iOS précédente 44383126199 SUCCESS ; recette manifeste et modules déployés gateway identiques vérifiés avant dispatch. Readiness RomFS v11 PASS (26247576430 octets). Aucun autre build du même workflow actif au contrôle de départ.

Deux jobs automatiques build → checkpoint compilé privé vérifié → finish archives iPad et livraison/assemblage CachyOS. NUP transféré pour la nouvelle chaîne, CAS de première construction vierge, sauvegardes périodiques et budget dynamique avec réserve de 15 min après le temps réel de transfert. La v10 livrée et tous ses caches/checkpoints restent préservés. Ne pas annoncer de nouvelle IPA disponible avant succès du second job et validation indépendante finale. Preuve **resultats/oot2-v11-launch-20261118.json** ; instantané run **oot2-v11-run-44385904117.json**. Gains M5 toujours à mesurer après livraison.
