# OOT2 v11 — livraison du 19 novembre 2026

## IPA v11 complète livrée et vérifiée — 19 novembre 2026

**Run 44467253078 SUCCESS : build et finish réussis.** IPA finale **/home/syssy/portage-ipados/oot-switch2/resultats/ZeldaOcarinaOfTime-ipad-v11-fullwarm-livecontainer.ipa**, **34877127738 octets (34,88 Go / 32,48 Gio)**, SHA256 **d014940f180044d817dd0dfbde4252be0aabbe616c96b36133d1b2ed8f67e6bd**. Source officielle **0b5fd6020093407af8bb5ad166e78e00bd2b7242**, chaîne **03a3ac831bfb**, recette **223676a28e67942a8d954fb522037edf3ccd6dc7c4690a280c41250dcef38aae**. RomFS original inclus, **26247576430 octets**, SHA256 **872de47b913bb97890880e9f17dccedc4144953a258e9a6aecf04c379427a669**. Utiliser cette IPA fullwarm-livecontainer ; checkpoint et slim sont des intermédiaires.

Contrôle indépendant terminé après réception : format ZIP/ZIP64 et chemins, CRC et SHA256 de chaque membre, provenance hôte/chaîne/recette, empreinte de chaque ressource pipeline, comparaison de tous les fichiers compilés avec la slim, intégrité du RomFS embarqué et SHA256 de l’IPA entière. Défauts intégrés vérifiés : DM_GUEST_FILE=1, DM_NVN_RT_RECYCLE=1, DM_GFX_SCALE=1, DM_FPS_HOLD=off ; Documents/env.txt reste prioritaire. Pas de signature ni changement appareil. Anciennes IPA conservées.

Préchauffage : **29 archives iOS/g17g**, R7138 = **7125 archivés + 13 à créer sur appareil** (passes sans fragment non acceptées par le compilateur Metal4 hors appareil), **M164/164 archivés**, S16818/C1043 dans les listes, 0 tâche échouée, 0 clé périmée. Index natifs complets vérifiés. Le préchauffage hors appareil ne couvre donc pas les 13 passes de profondeur ; aucune promesse de zéro préparation ou zéro ralentissement. **Aucun test M5 de cette IPA encore reçu.**

Preuves : **resultats/oot2-v11-delivery-verified-20261119.json**, script reproductible **verify_oot2_v11_delivery.py**, log **oot2-v11-delivery-verification-20261119.log**, état final **oot2-v11-complete-run-44467253078.json**. Rapport de livraison : docs/OOT2-V11-LIVRAISON-2026-11-19.md. PR94 reste draft jusqu’au retour M5.

## Protocole iPad M5

1. Importer ZeldaOcarinaOfTime-ipad-v11-fullwarm-livecontainer.ipa dans LiveContainer selon la procédure habituelle ; préserver la sauvegarde existante. Les fichiers slim/unwarmed-checkpoint ne sont pas la livraison complète.
2. Garder les mêmes réglages que le test v10 pour comparer : Metal 4 pipelines activé, même mode console, même upscaling ; compteur FPS activé. Ne pas ajouter DM_GUEST_FILE : il est intégré, sauf surcharge dans Documents/env.txt.
3. Relever la durée de préparation du premier lancement, charger la même sauvegarde et parcourir Kokiri pendant 20 minutes, puis entrer/sortir d’un bâtiment. Observer la porte brillante, les feuilles caméra immobile, les sols et les bandes verticales.
4. Noter la fréquence et la durée des chutes FPS, ainsi que toute fermeture et son heure. En cas de fermeture, conserver Documents/log.txt et le JetsamEvent correspondant pour distinguer pression mémoire et crash du moteur.
5. Répéter le même trajet après relance pour comparer premier lancement et caches chauds. Conserver v10 comme référence ; aucun gain FPS ou mémoire de v11 n’est encore mesuré sur M5.
