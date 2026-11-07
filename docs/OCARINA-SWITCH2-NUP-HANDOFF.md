# The Legend of Zelda: Ocarina of Time — Switch 2 NUP → IPA iPadOS

État au 06/11/2026 : NUP utilisateur inspecté **localement par l’utilisateur** (en-tête et TOC seulement), aucune donnée du jeu ni clé transférée à GitHub, IPA non construite. Les tests synthétiques du pipeline initial ont réussi ; correctif de compatibilité standalone fusionné (PR #23, commit `409e38d`), validation locale du NUP réussie. Aucun lancement automatique sur l’iPad.

## Entrées confirmées

- Dossier original CachyOS : `/home/syssy/Documents/The Legend of Zelda Ocarina of TIme/` (orthographe et casse de « TIme » respectées).
- Il contient **un fichier `.nup`** et `prod.keys`. Le NUP Switch 2 est un conteneur en clair : **nxnative n’a pas besoin des clés**. Elles restent dans le dossier original et ne sont ni copiées dans le projet OOT2 ni transmises à GitHub.
- Title ID confirmé dans la TOC : `0400486024DEC000`; **v131072** (mise à jour 1.2.0), **un seul paquet de type `update` avec `standalone_update=1`**, pas de paquet `base`. Le champ réservé de l’en-tête vaut `1` (toléré par le parseur nxnative).
- Source amont figée : `seedds/nxnative@c229bd7d52e30f072362e31c7b1e3206d107d4cd`, commit existant avec `dm/games/0400486024DEC000/`, compilateurs Metal 32023.922.
- Format NUP v1 selon `scripts/pack_nup.py`, non interchangeable avec NSP/XCI de Switch 1. Métadonnées locales : 25 020 741 061 octets ; TOC SHA-256 valide ; 601 répertoires ; 186 592 fichiers référencés ; ExeFS index 1 et RomFS index 2. La présence effective et l’intégrité SHA-256 du contenu des fichiers ne sont pas encore validées.

## Pipeline créé

Scripts :
- `security/oot2_nup_info.py` : validation locale **sans décompression ni lecture du contenu des jeux** de l’en-tête NUP, taille, structure bornée du TOC, SHA-256 du TOC, présence soit d’un paquet base avec mise à jour v131072, soit d’une mise à jour autonome `standalone_update=1` avec ExeFS/RomFS référencés. La validation profonde des entrées et SHA-256 des fichiers extraits reste effectuée par `scripts/pack_nup.py` sur le runner macOS. Une réussite locale n’établit pas à elle seule que tout le jeu est contenu dans le NUP.
- `security/oot2_gateway.py` et dispatch `oot2-*` dans `security/ffr_ssh_gate.py` : route SSH à commandes fixes, transmission du seul NUP par flux, cache/IPA/logs propres au jeu, aucun shell général ni transfert de clés.
- `security/oot2_transfer.py` : streaming privé NUP avec progression numérique et publication atomique uniquement si le volume exact est reçu. Cap d’entrée 80 Gio.
- `security/setup_oot2.sh` : configuration **réversible** sur CachyOS, ne modifie pas les fichiers d’origine. Le dossier dédié est `~/portage-ipados/oot-switch2/`, avec un lien symbolique `source` vers le dossier Documents, `shader-cache`, `shader-cache-conflicts`, `resultats` ; pas de dépendance système ajoutée.
- `security/run_oot2.py` : appel à `build_ipa_from_nsp.py` directement avec NUP (argument NUP, pas d’option `-k`), sélection `-p v131072 --platform ios --gpu none`, `--no-keep-extracted`, cache `DMSH_CAS` et points de sauvegarde périodiques sous SSH. Le journal brut reste privé.
- `.github/workflows/build-oot2.yml` : modes `preflight` (par défaut, aucun NUP transféré) et `build`. Vérification des scripts et secrets Tailscale/SSH avant Xcode/Homebrew, Xcode 27.2, Metal 32023.922, commit SHA nxnative vérifié sur 40 caractères, tunnel éphémère, admission du NUP et de la capacité disque, cache privé, transfert, compilation, retour IPA privé, nettoyage du runner.
- `.github/workflows/test-oot2.yml` : tests unitaires Linux et macOS, fichiers NUP de test *sparse* générés artificiellement, aucune donnée Nintendo ; teste références SHA, secrets, indépendance des autres jeux, format NUP, transferts atomiques et provenance du dossier.

## Lancement sur CachyOS (après fusion de la PR)

```bash
(
set -euo pipefail
cd "$HOME/portage-ipados/ff-resonance/github-build"
test "$(git branch --show-current)" = main
test -z "$(git status --porcelain)"
git pull --ff-only origin main
bash security/setup_oot2.sh
python3 -m unittest -v \
  security/test_oot2_nup_info.py \
  security/test_oot2_gateway.py \
  security/test_oot2_transfer.py \
  security/test_oot2_setup.py \
  security/test_oot2_workflow.py
gh workflow run build-oot2.yml -R Domessy/ffr-ipados-build --ref main -f mode=preflight
gh run list -R Domessy/ffr-ipados-build --workflow build-oot2.yml --limit 3
)
```

Seulement après un **précontrôle réussi**, déclencher `gh workflow run build-oot2.yml -R Domessy/ffr-ipados-build --ref main -f mode=build`.

Sortie IPA si réussie : `~/portage-ipados/oot-switch2/resultats/ZeldaOcarinaOfTime.ipa`, avec `oot2-build.log` local privé. La disponibilité d’une IPA ne démontre pas une exécution stable sur iPad.

## Contraintes et réserves

1. Le dépôt nxnative signale environ **42 850 shaders** ; les compilations sur runner hébergé peuvent dépasser une session. Les checkpoints CAS privés autorisent la reprise mais ne garantissent pas son résultat.
2. Profil testé principalement sur Mac. Les travaux communautaires relatent des essais iPad Pro M5 / iPadOS 27, avec des échecs GPU au-delà du **budget Metal d’environ 8 192 Mio**, et parfois un épuisement de stockage par les fichiers de mémoire invitée. La mémoire unifiée physique de 12 Go ne supprime pas cette limite.
3. Le commit amont épinglé est un point de référence reproductible. Plusieurs corrections mémoire sont encore **en PR ouvertes** (dont #1453, #1484, #1486, #1492) et ne doivent pas être appliquées sans vérification de dépendances et tests. On peut compiler une première IPA sans ces modifications, mais **pas la lancer automatiquement**, pour ne pas risquer de bloquer l’iPad.
4. Le NUP réel comporte **un paquet de mise à jour autonome** : le précontrôle accepte la forme `base=0 update=v131072` si elle est explicitement marquée `standalone_update` et référence ExeFS/RomFS, ou la forme traditionnelle base + mise à jour. Le drapeau standalone **ne garantit pas à lui seul la complétude des données** ; nxnative effectuera les vérifications profondes au dépaquetage. Un correctif non autonome ou une autre version entraînent un arrêt avant transfert.
5. Le premier précontrôle macOS réel (run #42252325321) a échoué uniquement sur l'admission disque : **60 367 396 864 octets libres** contre le seuil forfaitaire **84 401 220 490 octets** (`2 × NUP + 32 Gio`). Aucun NUP transmis. Le correctif suivant force le nettoyage des runtimes de simulateurs lorsqu'il reste moins de ~95 Go et introduit une commande SSH `oot2-space-v1` : elle calcule uniquement à partir de la TOC locale la somme des tailles de fichiers du RomFS sélectionné. Budget mesuré `NUP + RomFS + 12 Gio` avant transfert et après restauration du CAS. Cette estimation n'est pas une garantie de place suffisante pour le packaging IPA ; le contrôle de seuil en cours de compilation (~7 Gio) reste actif. Les copies NUP ne sont pas supprimées pendant l'utilisation du mapping mémoire nxnative.
6. Aucune source, clé ou IPA n’est publiée en artifact GitHub. La passerelle SSH et le stockage de sorties restent isolés pour OOT2.

## Retour arrière

Supprimer seulement `~/portage-ipados/oot-switch2/` (après sauvegarde éventuelle de l’IPA et du cache). Le dossier `~/Documents/The Legend of Zelda Ocarina of TIme/`, le NUP et les clés ne sont jamais modifiés. Si le pipeline est abandonné, retirer séparément la route `oot2-` du dispatch GitHub et le workflow dédié ; aucune autre application ni configuration CachyOS n’est touchée.

## Diagnostic utilisateur et correctif standalone du 06/11/2026

- L'exécution initiale de `security/setup_oot2.sh` s'arrêtait avec `OOT2_DIAG_V1 source=ok nup=fail reason=header`.
- Signature NUP v1 correcte, taille déclarée égale à la taille réelle, champ réservé de l'en-tête `1`, TOC SHA-256 valide.
- Un seul paquet `update` v131072, `standalone_update=1`, ExeFS/RomFS référencés. Le pipeline initial attendait incorrectement `base=1`.
- Correctif proposé : alignement sur nxnative pour le champ réservé et acceptation du cas standalone dans le validateur, la configuration locale et les deux vérifications du workflow. Tests de non-régression synthétiques sur les deux variantes.
- Suite : fusion après CI, `git pull --ff-only`, `bash security/setup_oot2.sh`, puis `mode=preflight` uniquement. Le build reste une action explicite séparée.

## Reprise après échec de capacité macOS — 06/11/2026

Le nettoyage Xcode/Android a libéré ~20 Gio sur le runner (`df` passant de 37 à 57 Gio). Le nettoyage des runtimes de simulateur n'était pas appelé, car son déclenchement était limité à 42 millions de Ko libres. La règle `2 × NUP + 32 Gio` n'était pas dérivée du RomFS de ce jeu. Le nouveau précontrôle peut refuser si `NUP + RomFS calculé + 12 Gio` dépasse la place disponible ; dans ce cas, rechercher une stratégie de stockage supplémentaire avant de lancer `mode=build`. Après fusion, une mise à jour locale de `main` est nécessaire pour exposer la nouvelle commande restreinte `oot2-space-v1` côté SSH. Aucune modification des clés ni du NUP original.


## Première compilation réelle — échec SQLite shader CAS (06/11/2026)

- Run privé GitHub Actions [#42262788651](https://github.com/Domessy/ffr-ipados-build/actions/runs/42262788651), SHA `1159a3b788cf230b191f245a1670a14c8d553f75`, mode `build` : transfert NUP complet, 23,30 Gio validés ; extraction v131072 réussie (24,4 Go), réécriture des trois modules `main`, `subsdk0`, `sdk`, séparation de **42 854 shaders** réussie.
- Échec au démarrage `[4/6] iOS shaders` : `sqlite3.OperationalError: unable to open database file` dans `shader_cache.Store` (`dmsh_build.py`). Espace disque restant ~66,7 Gio : pas un OOM ni un problème de stockage.
- Cause racine prouvée dans `seedds/nxnative@c229bd7` : `DMSH_CAS` doit désigner un **fichier SQLite `cas.db`** ; le workflow et `run_oot2.py` lui donnaient à tort le **répertoire** `$RUNNER_TEMP/oot2-shader-cas`.
- Défaut connexe : `cache_export.py` et la passerelle SSH utilisent des fichiers plats `index/`, `shader/`, `variant/`, `metallib/` ; la version nxnative épinglée emploie désormais une base SQLite. Les checkpoints précédents ont enregistré `new=0`, sans travail shader à préserver. Ne pas affirmer que le cache de shader est déjà constitué.
- Correction sur branche `fix/oot2-sqlite-shader-cas-20261106` : `DMSH_CAS=$RUNNER_TEMP/oot2-shader-cas/cas.db`, initialisation SQLite et `PRAGMA quick_check` **avant le transfert** ; `security/oot2_sqlite_cas.py` importe les entrées plates restaurées et exporte incrémentalement les entrées SQLite validées sous le protocole CAS privé/allowlisté existant. Les snapshots sont des transactions SQLite en lecture, sans accès au NUP ni aux clés.
- La compilation reprend la **phase de départ** du prochain run : l'extraction, la réécriture et le shader split seront refaits sur Mac éphémère ; seule la compilation des shaders pourra ensuite bénéficier des snapshots CAS. Les résultats ne sont pas un état binaire complet du workspace macOS.
- Après CI Linux/macOS, fusion via PR, puis mode `build` explicite après confirmation de la configuration `main`. Aucun changement local de la passerelle SSH n'est nécessaire pour ce correctif : les routes `oot2-read-cache` et `oot2-write-cache` ne changent pas.

## Interruption contrôlée des shaders et conservation du cache — 07/11/2026

Run GitHub Actions [#42284986467](https://github.com/Domessy/ffr-ipados-build/actions/runs/42284986467), commit `2c3307d45e0eb4b9bb0cf55d6641125067af5886`, `mode=build` : extraction, réécriture, shader split et démarrage de la compilation iOS réussis. La compilation a atteint le statut affiché `99 %`, `processed=42854/42854`, `not cached=8501`, sans sortir de la phase iOS shaders. **Ne pas assimiler les 99 % à la fin du processus**, ni `not cached=8501` à 8 501 échecs de shaders ; un journal détaillé est nécessaire pour savoir quelles tâches restent réellement.

- Entre 220 et 248 min, le disque libre est passé d'environ 31,9 à 7,0 Gio. Le wrapper a atteint le seuil `MIN_DISK_BYTES = 7 Gio` et a arrêté proprement nxnative (`exit 75`). Il ne s'agit pas d'un plantage du programme. Le disque éphémère aurait risqué d'être saturé sans ce seuil.
- Le diagnostic initial fondé uniquement sur les **derniers** checkpoints `new=0` était erroné. L'ensemble du log GitHub révèle 19 checkpoints, dont **305 466 nouvelles entrées** écrites sur CachyOS au total, 764 identiques réutilisées et zéro conflit. Les 305 466 entrées correspondent à des éléments CAS, **pas** à 305 466 shaders différents ni à une preuve de réussite complète. L'état restaurable doit encore être vérifié lors du prochain run.
- nxnative `scripts/pack_nup.py` construit un `mmap` sur la copie NUP et conserve l'objet dans `fam['nup']` pendant la totalité de `main()`. La simple suppression du chemin d'origine par un wrapper externe **ne libérerait pas le disque tant que ce mapping subsiste**. Sur cette version amont, après `extract_nup` et `extract_aoc`, le NUP standalone OOT2 n'est plus requis par les étapes shader et packaging.
- Correctif proposé dans `security/oot2_patch_nup_release.py` : injection idempotence refusée / point d'ancrage unique / validation syntaxique dans l'unique checkout macOS **épinglé** de nxnative. Le branchement opt-in `OOT2_RELEASE_EPHEMERAL_NUP` n'agit qu'avec `RUNNER_TEMP/oot2-nup/OcarinaOfTime.nup`, taille connue 25 020 741 061 octets, Title ID et version OOT2, mise à jour autonome sans DLC ni multiprogrammes, image RomFS extraite et existante. Il appelle `fam['nup'].close()` **avant** `candidate.unlink()`. La copie du runner seulement est supprimée ; l'original sous `Documents` et `prod.keys` restent intacts. Le gain théorique est **jusqu'à 23,3 Gio** de disque macOS.
- Ce gain dépend de la libération réelle du mapping et de la politique d'allocation APFS. Il permet d'aborder la phase de shaders avec davantage de marge, sans garantie que l'espace suffise au packaging final. Le build suivant doit confirmer le nombre d'entrées de cache **restaurées**, les `cache hits` de nxnative, le gain réel mesuré et les ressources nécessaires jusqu'à l'IPA.
- Ne pas relancer le job de 5 heures sans corriger le runner. Le code de la passerelle SSH de CachyOS n'est pas modifié par ce correctif ; aucune mise à jour locale indispensable.
