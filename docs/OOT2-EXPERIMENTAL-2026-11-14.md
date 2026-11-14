# OOT2 : audit et branche expérimentale du 14 novembre 2026

Branche : `experimental/oot2-20261114-host-optimizations`. Aucun changement de main, de l’IPA livrée ou des données privées. Aucun build privé déclenché.

## Sources et comparaison

Commentaire étudié : https://github.com/seedds/nxnative/discussions/1789#discussioncomment-19609742 (MJC626, 14/11, 09:23 UTC). L’auteur annonce environ 30 FPS sur un iPad M1 8 Go, mais précise ne pas avoir isolé les gains des patches. Ce résultat ne constitue pas une mesure sur notre M5.

Référence livrée : nxnative `ccd834e06a3938834bb5579e2ccc6a0ad13d3970`, préparation v8 fullwarm puis refresh du 13/11 ; chaîne `d24f05cf9d78`. Dernier main audité : `5a4e23a2e952dae92e1ccf0e6b7bf24e3266d4e8`, chaîne `d254f45e8002`. Les bibliothèques des deux chaînes ne sont pas interchangeables.

| Référence du commentaire | Constat dans le code et décision |
| --- | --- |
| #2306 (`f993848a`, test `d8a865a2`) | **Porté partiellement** : initialisation des grandes textures Depth16/Depth32F par copies, au lieu d’un clear pass susceptible d’échouer par allocation GPU. Seuil 16 Mio par tranche, blocs de 4 Mio, niveaux et couches traités. Les petites textures et MSAA gardent leur chemin précédent. |
| #2306 : retries d’uploads | Non repris dans ce lot : notre base a déjà des générations de pertes et des uploads partiels absents du patch original. Ajouter son compteur sans adapter ces invariants serait incorrect. |
| #1331 | Non activé : remplacement optionnel de la reconstruction NDVE par un agrandissement bilinéaire des vidéos. Modifie l’image et ne traite pas les baisses de FPS du gameplay. Ce n’est pas un correctif général des shaders. |
| #1379 | Non porté : dépend de #1377 et modifie l’horloge/abandon des images AV1 ; concerne la synchronisation vidéo/audio. Notre base ne contient pas `DM_CV_LATE`. À traiter avec ses tests de pause, EOS et reprise dans un lot vidéo séparé. |
| #1584 | Le réglage `DM_FPS_TARGET` et le pas entier sont déjà présents dans notre préparation revue (#1942). Aucun nouveau plafond 30 FPS imposé. |
| #1453 | Non porté : heap partagé avec hypothèses sur les offsets/alias des RT. Son propre rapport indique que les autres correctifs ont réduit le gain de sa scène fixe à environ 1 %. Le recyclage des RT existe déjà dans v8. |
| #1497 | Non porté : nouveau hook de réécriture lié à un build ID et à une instruction précise. Le kit privé contient les modules déjà réécrits ; une variable seule ne suffit pas. Notre profil conserve son réglage `DM_GFX_SCALE=1`. |
| #2241 | Référence mal décrite : c’est de la **génération d’images**, pas le scaler spatial MetalFX. Ajoute buffers/images et mémoire ; non porté dans ce lot mémoire. Le scaler spatial est déjà disponible dans notre base via `DM_UPSCALER=metalfx`. |
| #2090 | Non porté : monte la limite des allocateurs de 8 à 32. Notre code reste à 8, partage 64 soumissions par allocateur, soit 512 soumissions possibles. Augmenter la limite nécessite aussi revoir les anneaux et mesurer la mémoire. |
| #2469 | Objectif déjà traité par le refresh officiel `6e1f5068`/`b5150895` : POST/VIS dimensionnés à la limite réelle de 512, sans reprendre l’ancienne proposition 1024. |
| #2075 / #1969 | Stand-ins de première lecture déjà présents (`DM_NVN_POOL_STANDIN`, activé par défaut). #1969 est une issue, pas un patch à appliquer. |
| #2078 | Aucun objet issue/PR résolu par l’API officielle à ce numéro ; pas de code vérifiable à reprendre. |
| #2218 | Issue, dont #2219 est la proposition de correction des limites de lecture des uniforms. Touche aux shaders : pas de changement aveugle en conservant les bibliothèques d24. |
| `DM_XC_GUEST_RAM`, heatmap, HUD flash | Pas de source fournie dans le commentaire. Pas de reprise spéculative du « pinning » de 1,5 Go ni de purge. Une faute de page n’est pas une mesure des écritures physiques du SSD. |

## Nouveautés officielles hors du commentaire

- **Porté** : `f63ecbd4b87d68ab000b622e9dd6f1e740ebd846`. `gw_commit` parcourt seulement les emplacements de pages écrites par la soumission au lieu des 16 384 emplacements à chaque commit. Les règles de visibilité/fence restent identiques. Coût permanent de l’index : 32 Kio. L’amont rapporte environ 30 soumissions par frame pour OOT ; aucun gain M5 encore mesuré.
- **Priorité mémoire suivante** : `8653238e8a756aa8dcfd36e4f9fbcbde341b6b83`. Libère les RT GPU écrasés par d’autres, inutilisés depuis 3 s, en conservant les textures épinglées et les textures lues chaque frame. Rapport amont sur M6 : environ 5,4 → 3,7 Go de footprint ; une seule route avant/après, retest iPhone encore ouvert. Pas intégré ici : dépend du propriétaire extrait dans `nvn_owner.m`, de son retrait des entrées et de son invalidation des vues. Notre propriétaire est encore interne à `nvn_mtl.m`. Une application partielle laisserait des références/résidences incohérentes. À porter avec son test `t_dead_targets`, y compris vues parentes, pins et recréation.
- `34ada028` : vide la file de présentation après un retard ; candidat distinct pour la latence, à reprendre avec tests des ticks/cadences.
- `f31d6074` : réduit les copies/textures intermédiaires du scaler spatial MetalFX. Utile seulement avec ce scaler sélectionné ; dépend de l’ordonnancement MetalFX plus récent. Pas intégré partiellement.
- Les changements de traduction présents sur main ne sont pas repris : ils nécessitent de produire une nouvelle chaîne et de reconstruire les shaders correspondants.

## Implémentation et validation

La recette expérimentale s’applique **après** `oot2_fullwarm_prepare.py` et `oot2_fullwarm_refresh.py` :

```
python3 security/oot2_experimental_prepare.py /chemin/vers/nxnative
```

Le script exige le commit et les SHA256 exacts de ses sources d’entrée, vérifie le patch et les sorties, refuse les nouveaux fichiers préexistants et restaure les fichiers modifiés si une vérification finale échoue. La chaîne d24 est vérifiée. Les chemins de construction privés restent inchangés : ne pas lancer le workflow de production en pensant qu’il applique automatiquement cette recette.

Le switch expérimental `DM_NVN_DEPTH_ZERO_COPY=0` permet de retrouver l’initialisation précédente ; absent ou `1`, le nouveau chemin est actif. Ne pas l’utiliser comme réglage de performance général : il sert à isoler ce correctif.

Vérifications locales : recette complète appliquée à un nouveau checkout ccd, hashes de sortie vérifiés, `git diff --check`, 131 tests Python du pipeline réussis. La fixture CPU exerce réellement `gw_commit` : doublons, marques report-only, fences terminées, soumission suivante et débordement de génération. `t_zero_depth` est le test GPU amont : poison non nul, lecture de tous les texels, niveaux/couches et dernière tranche partielle.

Le workflow public `test-oot2-experimental.yml` compile les deux fixtures, exécute le test CPU et compile/lie l’hôte iOS sur données synthétiques. Il n’accède ni au NUP ni aux caches privés. Il **n’exécute pas** le test GPU : le runner ne dispose pas de Metal4. CI **verte** sur le code `800591e5b7e281a92b0fdbba186f128355cb02a7` : [run43603314990](https://github.com/Domessy/ffr-ipados-build/actions/runs/43603314990), 925 vérifications CPU sans échec, test profondeur compilé, hôte iOS compilé et lié (`BUILD SUCCEEDED`). Contrôles synthétiques existants également verts : [run43603315123](https://github.com/Domessy/ffr-ipados-build/actions/runs/43603315123). Les tests Metal et les routes cinq jeux sur Mac/M5 ne sont pas validés dans cet environnement.

## Protocole iPad avant toute promotion

1. Conserver l’IPA v8 fullwarm livrée comme référence, sauvegarde et caches. Relever mêmes options (dont Metal4 pipelines, mode portable, scaler), charge batterie et état thermique.
2. Construire/livrer ultérieurement un hôte expérimental dans un fichier distinct, seulement après CI verte. Aucune traduction de shaders ni nouveau NUP requis pour ces deux changements ; identité des ressources à revérifier lors du pack.
3. Avec le nouveau chemin actif : trois chargements de la même sauvegarde ; vérifier ligne `new-texture zeroing: depth texture ... zeroed by copies`, absence de GPU OOM, textures/ombres intactes, mémoire et éventuel Jetsam.
4. Même trajet de 10 minutes depuis la zone de départ, mêmes mouvements/caméras ; journal des pauses et de leur durée, médiane/p95/p99 des frame-times si disponibles. Ensuite une transition de zone et session prolongée si stable.
5. Comparer aux mêmes essais sur l’IPA de référence ; la désactivation du seul chemin profondeur permet un contrôle supplémentaire si nécessaire. Ne pas confondre caches froids/chauds, préchauffage et jeu. Aucun bénéfice FPS ou mémoire ne sera annoncé sans mesure comparable.

Contrôles négatifs locaux supplémentaires : une mauvaise empreinte de sortie provoque le rollback exact des originaux et la suppression des nouvelles fixtures ; la même recette réussit ensuite, et une deuxième application est refusée sans mutation. Preuve locale `resultats/oot2-experimental-validation-20261114.json`, log CI public `resultats/oot2-experimental-public-ci-43603314990.log`.
