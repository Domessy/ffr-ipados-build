# OOT2 — audit amont du 17 novembre 2026

Référence livrée v9 : `87422462a4c020def29cc39d3042b08cc9eab02a`, chaîne `9eecb8412308`, IPA complète vérifiée du run 44104588970. Main officiel consulté : `e4b0d9b75d39c41c10fdcfec2f0b070df496d7e5`, chaîne déclarée `a9bfaeb9fa8c`. 76 commits depuis la référence. Sources consultées en direct via le connecteur GitHub, puis comparaison Git immuable. Ce contrôle ne modifie pas le moteur livré et ne lance pas de compilation.

## Changements pertinents postérieurs à notre v9

- **Préchauffage officiel des IPA, 422ec240 / PR2674.** Le packer officiel intègre désormais les descripteurs natifs de rendu/mesh dans les IPA, avec publication/cache et contrôles d’index complets. Notre v9 dispose déjà de notre adaptation complète pour son ancienne liste. Nouveau profil OOT : S=16818, C=1043, R=7138, M=164, contre S=11569, C=324, R=2691, M=164 à notre révision. Donc **+4447 lignes R**, +719 C et +5249 S, soit +10415 lignes de données (diff fichier +10416 avec commentaire). Ne pas comparer directement un nombre de lignes R au nombre de bases uniques ou d’archives. Les chiffres publiés (iPhone17 historique et Mac rebased) ne constituent pas un test M5 de notre build.
- **Moins d’attentes de pipelines : 9d3a5836, edc7eff9, 015fed3a.** Recherche des bases prédites sur workers, attente de la recherche déjà en cours avant compilation concurrente inutile, persistance de la demande avant fin de compilation. Tests hôte et mesures Mac, bénéfice de performances iPhone/iPad encore non vérifié. À examiner en priorité pour les freezes de premières visites.
- **Tables de pools : d6585a2d / PR2663.** Rejoue les seules entrées modifiées dans un buffer de réserve terminé, avec limite de 16 MiB. OOT Kokiri : 16–24 tables de 33025 entrées modifiées par frame, ~5MB de copies auparavant ; temps de patch 0,015–0,025 ms contre 0,13–0,18 ms sur M6, sans gain de frame time démontré. Pas de mesure iPad.
- **Arènes GPU : 3fe574df / PR2862.** Partage des fins de blocs entre soumissions, retrait des blocs inutilisés et suppression de rétentions via les caches d’arguments. Réduction mémoire mesurée sur NieR/M4 Pro (~88MB d’allocation), pas une mesure OOT ni iPad. Examiner avec la gestion des fences/adresses corrigée dans les commits dépendants, pas en isolant arbitrairement quelques lignes.
- **Ordre des textures : 23427a7b / PR2919 ; b3fe7770.** Les uploads de textures attendent les copies GPU dont elles lisent la mémoire ; suivi ordonné des destinations physiques/sparse. Corrections générales susceptibles de concerner des défauts de rendu, sans attribution prouvée des scintillements M5. Régressions Mac de Cuphead et BOTW ; iOS non testé pour 23427a7b.
- **Robustesse des archives : 9bd8bb38 / PR2901.** Ne publie plus une période empoisonnée après arrêt du service compilateur. Ne résout pas à lui seul le crash initial du compilateur ni la récupération des anciens fichiers empoisonnés.
- **Vidéos : 7124b0ad / PR2877.** Récupère une session VideoToolbox invalidée après arrière-plan/premier-plan. Cas observé sur iPhone ; tests codecs dans une application synthétique ; synchronisation complète du jeu après récupération encore ouverte.
- **Shader/metadata : c4c1ffda (raw lookup inline dans les stages mesh finaux, contournement compilateur M1/M2), 0bd40f9f (FTZ demi-précision), bd072733 (comparaison not-equal ordonnée MSL), fb18e83a (SHFL), f15d6585 (découverte de pools de pointeurs lors des bindings avec métadonnées).** Changements de chaîne à auditer/tester ; le contournement M1/M2 n’est pas un gain M5 établi.

## Limites et proposition technique pour un prochain build

Priorité : étendre la couverture enregistrée et étudier l’intégration officielle de préchauffage ; auditer les correctifs de lookup et de mémoire avec leurs dépendances. Les correctifs purement hôte peuvent être évalués sans relabelliser ni abandonner la bibliothèque v9. Une migration **complète** au head contrôlé attend réellement `a9bfaeb9fa8c` : la bibliothèque compilée `9eecb8412308` ne peut pas être renommée et il faudrait une reconstruction authentique de la nouvelle chaîne. Le cas GPU hang OOT fait l’objet d’une nouvelle section, commit 760ef393, **diagnostic ouvert**, pas correctif de stabilité universel. Aucun résultat FPS/Jetsam iPad M5 nouveau n’est établi par cet audit.

Sources principales :
- https://github.com/seedds/nxnative/blob/e4b0d9b75d39c41c10fdcfec2f0b070df496d7e5/dm/games/0400486024DEC000/README.md
- https://github.com/seedds/nxnative/commit/422ec240
- https://github.com/seedds/nxnative/commit/9d3a5836
- https://github.com/seedds/nxnative/commit/edc7eff9
- https://github.com/seedds/nxnative/commit/d6585a2d
- https://github.com/seedds/nxnative/commit/3fe574df
- https://github.com/seedds/nxnative/commit/23427a7b
- https://github.com/seedds/nxnative/commit/9bd8bb38
- https://github.com/seedds/nxnative/commit/7124b0ad
- https://github.com/seedds/nxnative/commit/c4c1ffda
- https://github.com/seedds/nxnative/commit/760ef393
