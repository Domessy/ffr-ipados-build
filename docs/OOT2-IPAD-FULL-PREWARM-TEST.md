# Validation iPad — archives complètes des listes R/M

Build futur distinct v8-fullwarm, même chaîne d24f05cf9d78. Ne pas confondre avec v8-aot (bases/compute seulement).

1. Conserver sauvegardes et caches existants. Relever le nom exact de l’IPA, l’espace disponible, la version iPadOS et les réglages. Activer Metal 4 pipelines avant lancement ; conserver les mêmes options, résolution et mode console que la comparaison.
2. Après installation par l’utilisateur, relever le délai Play→fin de préparation→personnage contrôlable. Faire un deuxième lancement dans les mêmes conditions. Avec les caches existants, le premier essai n’est pas une mesure à froid ; le noter. Ne pas effacer les données pour obtenir artificiellement un essai froid.
3. Récupérer Documents/log.txt après fermeture normale par l’utilisateur. Chercher « pipeline archive bundled with the app » pour les bases, « prewarm archive bundled with the app » pour les listes complètes : fichiers ouverts/présents, MB, temps. Toute erreur « failed to open » ou construction sur appareil doit être conservée pour diagnostic. Le compte des pipelines uniques peut être inférieur aux lignes de la liste.
4. Relever « pipeline bases so far » : compiled/from the archive/reused ; « pipeline prewarm » pour les mesh : from archive/built. Comparer à la v8-aot sur un parcours identique. Un chargement de fichier seul ne prouve pas un lookup réussi.
5. Jouer 10 minutes dans la zone de départ : même sauvegarde, trajet, rotations de caméra et transitions porte/intérieur/extérieur. Noter durée et fréquence des pauses, FPS habituel/minimum, brillance et scintillement. Le HUD de performance peut être activé pour un passage séparé, en notant son état.
6. Relever la mémoire et l’état thermique disponibles dans les diagnostics, puis toute terminaison/Jetsam et son heure. Arrêter le test si la pression mémoire entraîne des fermetures répétées ; conserver le rapport pour l’analyse.

Critère de succès : archives complètes ouvertes ET pipelines rendus/mesh trouvés dans les archives, préparation moins coûteuse, ressources inchangées et aucune nouvelle instabilité. Aucun gain FPS ou délai de quelques secondes n’est acquis avant cette validation. Le préchauffage couvre les listes enregistrées, pas tous les états futurs possibles du jeu.


## Complément — correctifs hôte du 13 novembre

La recette PR80 conserve les textures actives et réutilise leurs vues, ajuste les buffers de visibilité, limite les prédictions répétées et corrige les invalidations sparse et l’ordre des archives. Comparer aussi un passage caméra immobile puis les mêmes rotations/transitions ; relever séparément scintillement, textures brillantes et pauses. Faire un passage prolongé de 15–20 minutes si la session est stable et noter mémoire/thermique : conserver davantage de textures actives peut accroître la mémoire résidente. Le plafond des buffers de visibilité est de32Mio, alloué à la demande. Ne pas attribuer une variation au patch à partir d’un seul instantané FPS. Les tests publics valident CPU/compilation/assemblage, pas le rendu ni la pression mémoire du M5.


### Limite Metal4 identifiée au premier build privé

Le manifeste v8 contient13variantes R de profondeur sans fragment (12tâches) que l’hôte prépare avec MTLDevice. Le rapport fullwarm doit distinguer cesdevice_render_rows desemitted_render archivées ; leur somme doit couvrir tous lesrender_rows. Toutes les164lignesM doivent être archivées. Les13variantes natives peuvent encore coûter du temps sur l’iPad ; ne pas présenter un compteur non nul de constructions natives comme une corruption de l’archive. Toute autre ligne manquante ou erreur reste à diagnostiquer. Le rendu et les shaders de ces passes restent inchangés.
