# Super Mario Bros. Wonder — portage nxnative vers iPadOS

Date : 2026-11-02. État : préparation et tests synthétiques du pipeline. **Aucune compilation réelle des XCI/NSP utilisateur, aucune validation sur iPad à ce stade.**

## Source

- Emplacement original : `/home/syssy/Documents/Super Mario Bros Wonder/`.
- Source observée : `Super Mario Bros Wonder.xci` (base, **7 985 954 816 octets**) et `Super Mario Bros Wonder v1.2.0.nsp` (mise à jour, **146 680 088 octets**), avec `prod.keys` local. Aucun déplacement ni conversion.
- Titre principal : `010015100B514000` ; titre mise à jour : `010015100B514800`.
- Version utilisateur annoncée : **1.2.0** (Nintendo l'a publiée le 25 mars 2026). Elle doit être confirmée par les métadonnées réelles des NSP : révision CNMT à lire dans le NSP, puis version affichée dans le NACP **1.2.0** après extraction. La révision Nintendo exacte n'a pas été fournie : le pipeline la lit et interdit les numéros déjà associés aux versions enregistrées 1.0.1 et 1.2.1, afin de générer un profil dérivé. Si les métadonnées ne correspondent pas à la version annoncée, le build s'interrompt.

## Profil nxnative et variante 1.2.0

Dépôt amont figé : `seedds/nxnative@65501fbbaf8526f7aab0a1edd028135888590f8` ; profil existant `dm/games/010015100B514000/` avec la base v0, 1.0.1 (v65536) et la version **1.2.1 (v327680)** ; la version utilisateur 1.2.0 n'y est pas enregistrée.

Le mécanisme `scripts/build_ipa_from_nsp.py` prend une version non enregistrée, puis produit un **profil dérivé** sous le répertoire temporaire du runner, à partir des identifiants réels des modules et de la mise à jour. Les tables de shaders sont créées avec les fichiers de la version dérivée, au lieu de reprendre sans contrôle celles de 1.2.1. Ne pas réétiqueter la version 1.2.0 comme une 1.2.1 pour forcer la sélection du profil amont.

`security/wonder_identify_update.py` vérifie les identifiants chiffrés Application/Patch et le numéro de révision, puis écrit uniquement `wonder-verified-patch.version` (entier) sur le runner. `security/run_wonder.py` lit cette preuve locale et passe explicitement `-p v<révision vérifiée>` à nxnative ; après l'extraction, le script vérifie la ligne NACP de la version affichée `1.2.0` **avant** de laisser la compilation continuer. Les erreurs sont transmises au poste uniquement par le canal privé. La génération des shaders peut nécessiter davantage de travail que pour une version officiellement enregistrée ; le fait de compiler une IPA ne prouve pas qu'elle démarrera correctement.

## Isolation, sécurité et fonctionnement

- Scripts : `security/setup_wonder.sh`, `security/wonder_gateway.py`, `security/wonder_transfer.py`, `security/wonder_identify_update.py`, `security/run_wonder.py`.
- Dossier privé de travail CachyOS : `~/portage-ipados/super-mario-bros-wonder/`, avec `source` lien symbolique vers les fichiers originaux, `private/prod.keys` en mode 0600, `shader-cache/`, `shader-cache-conflicts/`, `resultats/`.
- Aucune modification des NSP source, aucune modification des autres jeux, aucun paquet/service installé sur CachyOS.
- Xcode 27.2 et Metal 32023.922 requis sur runner macOS ; snapshot du cache de shaders et retours privés, aucun NSP ni IPA publié comme artifact public.
- Preflight local : exactement un XCI et un NSP au niveau racine, marqueur XCI HEAD à l'offset 0x100 et marqueur NSP PFS0 à l'offset 0, tailles bornées, rôles issus des formats ; le contrôle des vrais identifiants reste réservé à nx_extract sur le runner.
- Tests synthétiques Linux et macOS (sans clés ni NSP d'utilisateurs) avant publication. Les diagnostics de préflight sur CachyOS n'affichent que les noms et tailles des fichiers de jeu, jamais le contenu des clés.

## Déclenchement de la première compilation après fusion

```bash
(
set -euo pipefail
cd "$HOME/portage-ipados/ff-resonance/github-build"
test "$(git branch --show-current)" = main
test -z "$(git status --porcelain)"
git pull --ff-only origin main
bash security/setup_wonder.sh
python3 -m unittest -v security/test_cache_import.py security/test_wonder_gateway.py security/test_wonder_transfer.py security/test_wonder_identify_update.py security/test_wonder_setup.py security/test_wonder_run.py
gh workflow run build-wonder.yml -R Domessy/ffr-ipados-build --ref main -f mode=build
gh run list -R Domessy/ffr-ipados-build --workflow build-wonder.yml --limit 3
)
```

Sortie attendue si les étapes réussissent : `~/portage-ipados/super-mario-bros-wonder/resultats/SuperMarioBrosWonder-nxnative.ipa`. Journaux privés `wonder-build.log` et `wonder-inspection.log`. En cas d'échec au contrôle de version, consulter d'abord le journal d'identification et les lignes NACP du journal de build ; **ne jamais substituer la version amont**.

## Correction du format XCI + NSP (2026-11-02)

Le premier précontrôle échouait avec `FFR gateway failed: ValueError` parce que le pipeline Wonder, cloné de Hollow Knight, attendait deux NSP. La source réelle comprend un XCI de base et un NSP de mise à jour 1.2.0, comme dans le portage réussi de Metroid Dread.

La passerelle exige exactement un XCI et un NSP dans le dossier, vérifie leur nature régulière, l'en-tête `HEAD` du XCI à l'offset 0x100 et l'en-tête `PFS0` du NSP. Elle détermine les rôles par extension, jamais par la taille. Le workflow reçoit les deux formats sur le canal SSH privé ; le runner macOS conserve un nom XCI pour la copie de base, et le lecteur CNMT contrôle ensuite leur véritable contenu avant la compilation. Les sources de CachyOS restent inchangées.

La version 1.2.0 reste construite via profil dérivé en utilisant la révision chiffrée réellement lue, avec contrôle du numéro de version NACP affiché. Aucun remplacement artificiel par le profil 1.2.1.

## Reversibilité

Tous les fichiers additionnels sur CachyOS sont confinés à `~/portage-ipados/super-mario-bros-wonder/`; sauvegarder l'IPA et les caches souhaités avant une éventuelle suppression de ce seul répertoire. La branche/PR documente le routage `wonder-*` ajouté à `security/ffr_ssh_gate.py`, à révoquer séparément si ce jeu est abandonné.
