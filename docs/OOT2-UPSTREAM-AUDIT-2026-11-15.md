# OOT2 — nouveautés et sélection pour le prochain run, 15 novembre 2026

Audit seul : aucun patch natif ajouté, aucun run lancé. Référence : IPA expérimentale livrée par run43604382594, hôte17c646cb, nxnativeccd834e0 + fullwarm/refresh/expérience, chaîne d24f05cf9d78. Nouvel amont examiné :23790f8dcc3a3491a44f125805dfbf1e5664cd2a, chaîne30f68cc57128, comparé à5a4e23a2 du précédent audit. Reprendre main entièrement impose de nouvelles bibliothèques ; les ports hôte sélectionnés peuvent conserver d24 si leur ABI et les entrées de bibliothèques restent identiques.

Sources : [page OOT2](https://github.com/seedds/nxnative/blob/23790f8dcc3a3491a44f125805dfbf1e5664cd2a/dm/games/0400486024DEC000/README.md), [discussion1789](https://github.com/seedds/nxnative/discussions/1789). Lecture intégrale des45commentaires et réponses renvoyés par l’API ; aucune page suivante. Copies publiques locales : resultats/discussion1789-audit-20261115.json etoot2-pr-audit-20261115.json.

## À sélectionner pour le prochain lot hôte

| Priorité | Changement | Utilité, intégration et limites |
| --- | --- | --- |
| 1, expérimental A/B | [PR2715](https://github.com/seedds/nxnative/pull/2715), ce01754e, DM_RES_CB=1 | La résidence GPU est déclarée pour chaque command buffer au lieu des queues. Vise le mode durablement lent avec guest files, pas la compilation ponctuelle de pipelines. PR ouverte/non fusionnée, option désactivée par défaut. Auteur : M4,20paires, état lent10/20sans contre0/20avec ; rapport indépendant [M2 Air](https://github.com/seedds/nxnative/discussions/1789#discussioncomment-19625953) :4/4lents sans,0/4avec,12,8–16→28,7–30FPS avec plafond30. Ni preuve sur M5 ni explication définitive du driver. Port manuel nécessaire. Couvrir submit, uploads, coupes, présentation, snapshots et thread encode ; reprendre t_res_cb et tester toutes les combinaisons avant activation. N’implémenter que la variable d’environnement serait sans effet. |
| 1 | [960d203e](https://github.com/seedds/nxnative/commit/960d203ecc5bd30f0e44b45b151a00820ec5a290) | Les pipelines des vrais draws à venir sont admis indépendamment du budget des simples suppositions. Complète notre53cbb993 ; la partie runtime s’applique sans conflit à nos sources préparées. Reprendre les tests t_pso_pending, dont la priorité des demandes réelles et l’absence de blocage derrière des tâches en attente. Peut réduire certaines premières rencontres encore absentes des listes ; ne rend pas complète une liste qui ne couvre pas une zone. Surveiller le pic mémoire et la concurrence de compilation sur iPad. |
| 1, diagnostic | [addbe8d6](https://github.com/seedds/nxnative/commit/addbe8d62b2cf870c920487275b0df89ab7973f3) | DM_MEMSTAT/DM_THRCPU démarrent après lecture de env.txt iOS. Le constructeur précédent ignorait ces options fournies par ce fichier. Diff main.c/memstat.m applicable sans conflit ; aucun gain FPS direct. Utile pour comparer footprint, mémoire GPU et pauses. Activer la collecte seulement dans l’essai mesuré. |
| 1, avec dépendances | [b1ba6570](https://github.com/seedds/nxnative/commit/b1ba6570fc334a1142d8d89ac628161e58e5b99e), [293b1d4d](https://github.com/seedds/nxnative/commit/293b1d4dbfcdf00863fa1a6128d23761881d0ddf), [edc07d34](https://github.com/seedds/nxnative/commit/edc07d34bd21a2683e6e5897651a5664a15abcc7) | Reprise du palier60quand la scène tient réellement, seuil d’essai porté de0,85à0,95vsync, plus une pause isolée exclue de la moyenne30frames. Les deux derniers patches seuls ne s’appliquent pas à notre header : reprendre une séquence cohérente et les tests t_fstep. Ne pas imposer30ni forcer60lorsque le GPU ne tient pas. La page précise qu’un M5 de base à19msdoit rester30avec la synchronisation entière ; la résolution dynamique peut faire tenir60. Résultat iPad inconnu. |
| 2, démarrage | [d9f05398](https://github.com/seedds/nxnative/commit/d9f05398) | Prélecture des plages utiles avant ouverture des archives Metal. M4Max amont : archive4,4Go,8→1,6sàfroid selon la page. Ne concerne pas les pauses de gameplay une fois l’archive ouverte. Port nécessaire vers notre loader complet0a126 ; conserver validation des conteneurs et les12archives R/M. Mappings temporaires8Mio, pas de copie complète en RAM ; mesurer malgré tout le pic mémoire/cache sur iPad. |
| 2, sauvegarde du travail compilé | [3e628a0d](https://github.com/seedds/nxnative/commit/3e628a0d86ecc0d017b7e0712e457c493ea3a2f3) / PR2625 | Stoppe le préchauffage et laisse une sortie gracieuse écrire les archives ; tests et mesures surtout sur runs Mac sans fenêtre. Peut éviter de recompiler du travail non enregistré. Ne garantit rien après Jetsam/SIGKILL et n’évite pas des combinaisons jamais vues. Adapter au cycle de vie iOS et à notre sérialisationcc8f4490 avant inclusion. |

## MetalFX : candidat utile, lot distinct à valider

[9e0ddeeb](https://github.com/seedds/nxnative/commit/9e0ddeebd67565cf0042bd759d85b7c71c5455a4) reconnaît les packs NDSR_vr/_vr_light réellement utilisés, et convertit correctement leur entrée dont les couleurs sont des racines carrées. La page OOT2 indique que l’option pouvait auparavant ne rien remplacer. Effet mesuré amont sur M4Pro : GPU p50 17,15→15,79ms, mais les deux essais restent30FPS ; les contours sont plus doux. Ce résultat concerne un Mac, une route et un hôte spécifiques.

Vérification de notre shader_map.tsv dans l’IPA source, lecture seule :22clés avec la détection actuelle,61avec la nouvelle, cohérent avec la page. Il faut porter ensemble détection, classification/correction couleur, code du scaler et son petit shader de copie interne ; ne pas reprendre seulement l’ancienne proposition PR1459 « sans courbe=sans conversion ».

Le helper copy.metal est interne à l’hôte, distinct des bibliothèques traduites du jeu. Un port ciblé n’impose pas à lui seul de reconstruire toutes celles-ci. Cependant notre reconstruction hôte exige l’égalité intégrale du profil régénéré et du profil capturé dans le kit. Les nouvelles clés la feront échouer : prévoir un delta de profil explicitement autorisé et vérifié pour ces seules définitions, garder toutes les autres identités et les modules privés. Tester sur fixture et vérifier dans le log qu’un dispatch est effectivement remplacé avant d’attribuer un résultat à MetalFX. Le diff complet ne s’applique pas tel quel sur notre source.

## Mémoire : distinguer les mécanismes

- [8653238e](https://github.com/seedds/nxnative/commit/8653238e8a756aa8dcfd36e4f9fbcbde341b6b83), déjà connu hier mais NON livré : reste le candidat mémoire le plus direct, libération des RT écrasés et inutilisés3s. Mesure Mac5,4→3,7Go ; retest iPhone encore ouvert. Le propriétaire extrait nvn_owner n’existe pas dans notre base : adaptation complète et t_dead_targets requis, pas de port partiel. À traiter séparément de2715pour pouvoir attribuer les résultats.
- [fb26adfc](https://github.com/seedds/nxnative/commit/fb26adfc9e95e1c3f565e1874b6e7ac3426ec92f) ajoute une marge pour l’hôte au choix automatique guest files. Applicable sans conflit, mais notre défaut explicite DM_GUEST_FILE=1 court-circuite déjà ce choix : priorité faible pour OOT actuel. Ne corrige pas les allocations GPU.
- La [PR1386](https://github.com/seedds/nxnative/pull/1386) est toujours un prototype draft sur une pile de patches. Désactivée lorsque DM_GUEST_FILE est actif ; son propre texte signale une fenêtre possible de perte d’écriture et EFAULT lors d’un appel système. Elle libère la copie invitée, pas la mémoire GPU. À exclure du prochain run.
- Le [rapport M4](https://github.com/seedds/nxnative/discussions/1789#discussioncomment-19624133) rappelle qu’un disque insuffisant peut faire retomber guest files sur de l’anonyme. Les ~10Go cités concernent son Mac, ne pas les présenter comme seuil universel iPad. Vérifier le journal réel du mode de mémoire, pas seulement la présence de la variable.

## Discussion : portée des nouvelles observations

[19614165](https://github.com/seedds/nxnative/discussions/1789#discussioncomment-19614165) : profil M2Pro, coût fixe important, dont task/mesh. Supprimer les draws avec DM_NVN_SKIP_MESH mesure leur coût en cassant l’image ; ce n’est pas une optimisation à livrer.

[19615044](https://github.com/seedds/nxnative/discussions/1789#discussioncomment-19615044) : PR2672 ajoute une carte détaillée des passes et des diagnostics, pas un accélérateur. PR2685 documente la couverture des APIs, pas le comportement du jeu. Une sélection de diagnostic peut aider après mesures M5 ; ne pas activer une instrumentation lourde dans le benchmark de référence.

[19634575](https://github.com/seedds/nxnative/discussions/1789#discussioncomment-19634575) : auteur M4 rapporte75minà60mais17pauses de1–2,6s, dont14nouveaux pipelines prenant2,15s. Cela documente une cause distincte des sessions durablement lentes. Notre fullwarm couvre les listes enregistrées, pas toutes les zones/effets possibles du jeu ; demander le log de la pause avant de conclure.

PR2532augmente la résolution jusqu’à4K et le budget RT ; hors objectif mémoire/FPS. PR2226sur les trous des buissons reste une hypothèse non confirmée par les mesures des compteurs indirects de main ; ne pas appliquer une frontière d’encodeur systématique comme correction avérée.

## Durée des runs

Les nouveaux caches de traduction par chaîne, mémo c1/uniforms et réutilisation des splits améliorent les constructions qui traduisent/rechargent les shaders. Notre pipeline hôte réutilise déjà les bibliothèques et évite le NUP : ces changements ne supprimeront pas ses transferts. Run43604382594 : environ29min de restauration,12min de sauvegarde des caches,14min de retour/assemblage ; beaucoup plus que les6,5min de reconstruction hôte+R/M. Ne pas annoncer le gain95→6,5sdu mémo comme gain de notre workflow. Garder les caches privés et leurs versions protégées.

## Ordre proposé

1. Lot hôte d24 :2715désactivable +960d203e +diagnostics iOS, avec tests CPU et compilation/lien iOS ; essai M5 contrôlé switch off/on, plusieurs démarrages.
2. Lot cadence cohérent avec ses dépendances et tests ; comparer temps de frame et vitesse du jeu, pas seulement FPS.
3. Lot mémoire RT8653238et lot MetalFX/profil séparés, chacun avec son test graphique. Ouverture des archives et conservation à la sortie sont des compléments à mesurer.
4. Aucun build coûteux avant validation de ces adaptations. Ne pas remplacer la chaîne d24par30f68dans les métadonnées sans reconstruire les bibliothèques réelles.

Preuve de faisabilité en lecture seule : resultats/oot2-integration-feasibility-20261115.json (hash des sorties expérimentales vérifiés avant git apply --check). Un diff applicable n’est ni un test de compilation ni une preuve de gain. Aucun code natif modifié par cet audit.
