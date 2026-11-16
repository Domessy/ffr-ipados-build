# OOT2 — lot complet hôte expérimental du 15 novembre 2026

Demande utilisateur : intégrer tous les correctifs retenus par l’audit et lancer le run. Branche expérimentale existante, PR91 non fusionnée. La référence stable et le premier build expérimental sont conservés.

## Contenu

La recette `oot2_next_prepare.py` s’applique après fullwarm, refresh et la première recette expérimentale, sur nxnativeccd834e0. Patches et empreintes d’entrée/sortie sont verrouillés dans `oot2_next_manifest.json`. La chaîne recalculée reste **d24f05cf9d78** ; aucun shader traduit ni module privé n’est remplacé.

- Résidence GPU par command buffer (PR2715/ce01754e), activée par défaut sur iOS dans ce build, désactivable par `DM_RES_CB=0` dans env.txt. Les soumissions normales, coupes, uploads, snapshots, présentations et le thread encode sont couverts. Adaptation au verrou `g_res_mu` de v8 : c’est lui qui protège déjà tout le commit du residency set, contrairement au mutex séparé de main.
- Libération des RT GPU écrasés et inutilisés3s (8653238e), avec conservation des textures épinglées et vues parentes. Port du propriétaire dans l’implémentation interne v8, pas d’introduction partielle de nvn_owner. **Le bitmap simple de lecture d24 est conservé** ; ne pas importer le bitmap typé de main. Retrait des entrées live/ghost, notes de génération et vues enregistrées, libération différée derrière les fences. Désactivation : `DM_NVN_RT_DEAD=0`.
- Prévision des pipelines des vrais draws à venir (960d203e), en complément de la priorité des demandes déjà portée.
- Cadence : machine d’état et tests du snapshot23790f8d (dontb1ba6570/293b1d4d/edc07d34), avec adaptation des appels v8.119vérifications locales réussies ; aucun plafond30imposé. Suivi de la cadence des vidéos nn::movie/nn::codec (9f824c7d/PR2622) adapté au décodeur synchrone v8.
- DM_MEMSTAT/DM_THRCPU démarrent après lecture de env.txt iOS (addbe8d6). Marge hôte du choix automatique guest files (fb26adfc), tout override explicite0/1reste prioritaire.
- Prélecture ciblée à l’ouverture des archives (d9f05398), par mappings8Mio temporaires, sans copie du fichier entier. Conservation de la validation des conteneurs et du loader complet R/M.
- Arrêt du préchauffage et écriture des archives à la sortie gracieuse (3e628a0d), avec préservation de notre exclusion mutuelle sérialisation/compilation. Cela ne garantit pas une sauvegarde après Jetsam/SIGKILL.
- MetalFX : détection de tous les packs NDSR, couleurs à entrée racine carrée et copie au carré (9e0ddeeb), copies intermédiaires évitées quand compatibles (f31d6074), barrière avec travail effectif avant le scaler (partie replay b25b651 adaptée à v8). Son API de présentation existante est conservée. Le petit shader interne `copy.metal/fsq` est recompilé et embarqué dans l’hôte ; les bibliothèques du jeu restent intactes. L’option de scaler du joueur est conservée, pas forcée.

## Profil privé et livraison

La reconstruction n’abandonne pas le contrôle d’égalité du profil. `oot2_next_profile.py` n’autorise que les deux définitions `DM_GAME_UPSCALER_KEYS/N`, dont les valeurs doivent être exactement dérivées du shader_map original, avec l’ancienne et la nouvelle règle. Toute autre différence est refusée. Contrôle du kit réel sur CachyOS : **22→61clés**, aucune autre différence ; preuve privée ne contenant que comptes/empreinte : resultats/next-host-profile-preflight-20261115.json. Les modules et tables capturés restent contrôlés par SHA.

Le rapport embarqué comporte `host_next`, l’identité du patch, la chaîne et le delta de profil. La route fixe `oot2-fullwarm-v8-write-next-slim` les contrôle avant assemblage. Sorties :

- `ZeldaOcarinaOfTime-v8-next-host-slim.ipa`
- `ZeldaOcarinaOfTime-ipad-v8-next-host-livecontainer.ipa`
- `oot2-fullwarm-v8-next-private.log`
- `ipad-v8-next-host-local-bundle-result.json`

Caches AOT/RM communs compatibles, avec validation et versions précédentes protégées. Pas de NUP et pas de traduction des shaders. Pas de nettoyage de données privées ni de modification d’appareil.

## Validation avant dispatch

137tests Python locaux réussis, dont rejet de différences de profil, mauvais compte/clé, mauvaise provenance et isolation de livraison. Recette complète initialement appliquée à un checkout frais ; contrôle des empreintes à chaque préparation.119tests cadence locaux réussis.

Contrôles publics : compilation des fixtures profondeur/résidence/RTdead/MetalFX, exécution CPU propriétaire/pins/vues parentes et fences, pipelines en attente et cadence ; compilation/lien iOS et véritable reconstruction d’un kit synthétique, pack/réception/assemblage RomFS synthétique. Les premières compilations ont permis d’adapter les appels de cadence, l’absence d’encodeur TF persistant et le verrou de résidence de v8, puis d’ajouter le header de fixture MetalFX. Aucun transfert privé lancé durant ces itérations. Le statut final des contrôles et le run privé sont consignés dans le handoff.

Non réalisable dans cet environnement : exécution GPU Metal4 et routes réelles des cinq jeux de régression. Les fixtures GPU sont compilées, pas annoncées exécutées. Aucun gain mémoire/FPS ni absence de glitches M5 encore établi.

## Essai iPad

Conserver sauvegarde et caches ; mêmes options, même trajet et état thermique que référence. Metal4 pipelines activé ; MetalFX au choix du joueur, mais noter sa valeur et vérifier une ligne de remplacement effectif de dispatch si activé. Relever3chargements de sauvegarde puis trajet10min et transition de zone ; mémoire/Metal, pauses, textures/ombres, vitesse du jeu, préparation1er/2elancement. Les switches0permettent d’isoler ensuite résidence et RTdead si un problème apparaît. Une amélioration ou régression de ce lot complet n’attribue pas à elle seule un résultat à un correctif individuel.

## État vérifié du lancement

CI moteur 43745313604 et reconstruction/livraison synthétique complète 43747064343 réussies. Build privé lancé : [43747472766](https://github.com/Domessy/ffr-ipados-build/actions/runs/43747472766), code d90b4950. Les résultats réels du build et les essais M5 restent à vérifier.
