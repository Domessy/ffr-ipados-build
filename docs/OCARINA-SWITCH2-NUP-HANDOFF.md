# The Legend of Zelda: Ocarina of Time — Switch 2 NUP → IPA iPadOS

État historique au 06/11/2026 (supersédé par la reprise du 07/11 en fin de document) : NUP utilisateur inspecté **localement par l’utilisateur** (en-tête et TOC seulement), aucune donnée du jeu ni clé transférée à GitHub, IPA non construite. Les tests synthétiques du pipeline initial ont réussi ; correctif de compatibilité standalone fusionné (PR #23, commit `409e38d`), validation locale du NUP réussie. Aucun lancement automatique sur l’iPad.

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

## Contrôle de compatibilité amont avant une nouvelle compilation — 07/11/2026

Le correctif de fermeture du `mmap` du NUP a été validé sur des fixtures synthétiques Linux/macOS (PR #26), mais un vrai run `mode=build` n'avait pas encore confirmé son application au code complet nxnative. La suite de tests OOT2 télécharge désormais, **sans données privées**, le commit amont strictement épinglé `seedds/nxnative@c229bd7d52e30f072362e31c7b1e3206d107d4cd`, applique `security/oot2_patch_nup_release.py` dans une copie éphémère puis vérifie la syntaxe, le point d'insertion et l'ordre fermeture du mapping/suppression de la copie. Le test est exécuté sur Linux et macOS. Ce smoke test ne mesure pas le gain disque réel, qui reste à constater sur une prochaine compilation.

Le workflow de production demeure limité à un lancement explicite `workflow_dispatch` ; aucun déclenchement automatique par push n'est ajouté à `main`. Les clés et le NUP restent exclusivement sur CachyOS tant que `mode=build` n'est pas lancé.

## Reprise mémoire et graphique du 07/11/2026 — audit et expérimentation

### État réel et conservation

Le handoff local `HANDOFF_WORK_OOT2_IPADOS_JETSAM_2026-11-07.md` et le retour utilisateur établissent que l'IPA du run [42364126574](https://github.com/Domessy/ffr-ipados-build/actions/runs/42364126574), pipeline `d1b919f1064912f1c07702c7f068f4992424152a`, atteint introduction, chargement et déplacement sur iPad. Des anomalies graphiques puis un Jetsam restent ouverts. Le run 42344930333 avait réussi la compilation mais pas le retour SSH complet. Aucun nouveau build IPA n'a été lancé pendant cet audit.

Les sources et clés sous `/home/syssy/Documents/The Legend of Zelda Ocarina of TIme/`, le cache sous `/home/syssy/portage-ipados/oot-switch2/shader-cache/` et l'IPA sous `resultats/` n'ont pas été modifiés. Travail isolé : `audit-pipeline/` (branche `fix/oot2-ipados-memory-20261107`), `audit-nxnative/` (amont observé), `audit-pinned/` (copie de test patchée). Le checkout historique `ff-resonance/github-build` demeure à son ancien état ; ne pas le réinitialiser brutalement.

### Évidence directe, limites de mesure

Le rapport local `/home/syssy/Téléchargements/JetsamEvent-2026-11-07-175241.ips` est relu par `security/oot2_memory_report.py --jetsam` :

- pages de 16 384 octets ; LiveContainer `vm-pageshortage`, actif au premier plan, 613 605 pages = **9 587,578 Mio / 9,363 Gio résidents** ; maximum 9 597,563 Mio ; pages libres 8 599 = **134,359 Mio** ;
- six MTLCompilerService = **817,844 Mio résidents cumulés**, cinq `highwater`, un `proc-thrashing` ; les processus du rapport ne forment pas nécessairement une photographie simultanée permettant de reconstituer toute la RAM ;
- preuve de pression système, pas preuve d'une fuite, d'une limite d'entitlement atteinte ou d'une cause shader unique. Le RSS n'est pas le heap guest ; une allocation Metal peut couvrir des alias et n'est pas une consommation physique supplémentaire indépendante.

L'iPad a ensuite été connecté par l'utilisateur. Lecture USB : `iPad17,1`, iPadOS `27.0.1`, build `24A446`. Les métadonnées InstallationProxy de l'hôte **LiveContainer** indiquent `com.apple.developer.kernel.increased-memory-limit=true`, `get-task-allow=true`, extended-virtual-addressing absent. L'autre hôte LiveContainer2 n'a pas l'autorisation increased-memory-limit. Cela vérifie les métadonnées d'installation, pas le provisioning signé extrait ni une mesure du plafond effectif. Aucun changement d'entitlement n'a été effectué ; une autorisation ne crée pas de RAM physique.

Le conteneur de l'hôte est monté **en lecture seule** pendant l'audit ; `LCAppInfo.plist` identifie le répertoire de données OOT2. Seuls les diagnostics sont copiés dans `resultats/ipad-audit-20261107/`, privés hors Git. Ne pas publier `apps-private.json` (inventaire d'applications et identifiants). Le journal récupéré est le plus récent présent, **sa correspondance exacte avec l'incident Jetsam fourni n'est pas prouvée**, faute d'identifiant d'incident dans le log.

Journal : commit `c229bd7d52e3+dirty`, chaîne `23a1ea1db092`, GPU Apple M5 ; mémoire guest **anonyme**, `DM_GUEST_FILE unset`, pool virtuel 9 Gio, marge initiale 11,96 Gio. L'activation automatique des fichiers guest ne s'est donc pas produite ici.

| Frame | Valeur « resident » du log, en fait phys_footprint (Mio) | Metal currentAllocatedSize (Mio) |
|---|---:|---:|
| 300 | 3 634 | 2 682 |
| 600 | 4 685 | 2 800 |
| 900 | 9 913 | 11 818 |
| 1200 | 9 831 | 15 725 |

À frame 1200 : résidence explicitement déclarée 5 510 Mio / 6 672 objets ; 4 284 pools résidents ; file de libération différée 2 ; à frame 1500 résidence 5 492 Mio. Dernier temps de frame visible ~116 s. **Le mot resident est trompeur dans cette version : `hle_nvn.c` transmet `vi.phys_footprint` à `mtl_mem_stat`.** La télémétrie ajoutée distingue RSS et footprint. Il n'y a aucune justification à additionner footprint, Metal alloué et ensemble résident. L'écart Metal alloué / ensemble résident oriente vers les allocateurs de commandes, pipelines et autres allocations hors ensemble, sans attribuer à ce stade tout l'écart à une seule classe.

Le journal contient aussi `task / mesh pipeline` en échec après 10 545,8 ms : `XPC_ERROR_CONNECTION_INTERRUPTED` (plusieurs tentatives), mesh `4c7d6be5a7717c8d`, fragment `4b825abdc0916973`. Piste réelle d'éléments de végétation mal rendus, sans capture prouvant le lien avec l'anomalie utilisateur. Les quatre refus AV1 « 12 pictures waiting » ne prouvent pas un défaut de décodage : le code réessaie quand la file est pleine.

### Diff amont précis et décisions

Point d'audit `seedds/nxnative@bd979ced3ae6bad60bf86429a71d172297d93471` : **82 commits** après le pin, 234 fichiers modifiés, 132 606 ajouts / 6 678 suppressions. `game.tsv` OOT2 est inchangé. Chaîne shaders : `23a1ea1db092` → `3ee52af3ca18`. **Le pin de production reste `c229bd7d52e30f072362e31c7b1e3206d107d4cd`** ; passer globalement à main changerait la chaîne et pourrait reconstruire les 42 854 shaders et leurs variantes. Les grands nombres de lignes incluent des tables ; ce n'est pas 132 606 lignes de moteur.

Comparaison reproductible : [pin…point d'audit](https://github.com/seedds/nxnative/compare/c229bd7d52e30f072362e31c7b1e3206d107d4cd...bd979ced3ae6bad60bf86429a71d172297d93471).

| Correction vérifiée dans le code / la discussion | Présence au pin ; décision |
|---|---|
| [863bc6b789733f8cfb4d9d1488a1e921e17d1417 / #1557](https://github.com/seedds/nxnative/commit/863bc6b789733f8cfb4d9d1488a1e921e17d1417) : familles de résolution pour `COMPRESSIBLE` sans `IMAGE` | Absente. **Rétroportage ciblé** de `image_shape`, sans le recensement détaillé ajouté par le commit. Les tailles successives de profondeur peuvent partager le heap existant au même pool/offset/format. Exclusions display, vidéo, linéaire, sparse ; protections 2D/1 mip/1 échantillon conservées. Amont : 15–16 textures de 14,5 Mo au même offset ; gain GPU observé ~190 Mo dans l'ancienne pile Mac, non prédit pour l'iPad. Risque : alias de profondeur, synchronisation et tailles à valider sur GPU. |
| [5b84d37edbd60e92695eeb0a0015b793a90f5020 / #1556](https://github.com/seedds/nxnative/commit/5b84d37edbd60e92695eeb0a0015b793a90f5020) : fin d'encodeur au point de cohérence device | Absente. **Rétroportage du changement de visibilité uniquement**, sans remplacer les allocateurs pour les profiler. Les barrières d'entrée gardent l'alias flush ; les copies aliasées gardent aussi celui de sortie ; la voie de passes relâchées reste intacte. Amont : 600 passes, 88,5 → 27,7 Mo de commandes ; 8 allocateurs conservaient chacun 36–80 Mo sur le parcours. Piste particulièrement pertinente pour notre écart allocation/résidence, mais gain iPad non mesuré. `DM_NVN_END_ALIAS=1` rétablit les barrières de fin si les diagnostics de la version l'autorisent ; baseline est le retour arrière fiable. |
| [f25fa9562ee96d06f1e6412dbb91aab2b7035ec1 / #1484](https://github.com/seedds/nxnative/commit/f25fa9562ee96d06f1e6412dbb91aab2b7035ec1) : lookup shader sans résidence | Absente ; non sélectionnée en premier. La PR est fermée **sans merge GitHub**, mais la correction remaniée est intégrée dans ce commit. Le mainteneur mesure **aucun gain OOT2 isolé** (table raw gmem remettant les pools en résidence). Les « 334 Mo » venaient d'une pile de changements : ne plus promettre ce gain. |
| [#1453](https://github.com/seedds/nxnative/pull/1453), head `28cfdafa9ad3cf1bda9749400d7c6c397c130902` : heap par pool GPU-only | PR ouverte, absente de main observé ; gain récent ~1 % en scène fixe, pas les anciens 2–3 Go. Laisse les pools virtuels hors de ce chemin ; notre depth buffer bénéficie donc plutôt de #1557. Écart de layout NVN/Metal et alias imposent des tests GPU ; différée. |
| [#1588](https://github.com/seedds/nxnative/pull/1588), head `4b231acf1bfee4f8929bc2f494e9bb75c3f70253` : cibles mortes par écrasement | PR ouverte, opt-in. Mac : RT 3,5 → 1,1–1,2 Go dans une pile donnée ; aucun test unitaire de reclaim dans la PR et exclusions nombreuses. Pas intégrée à l'aveugle. |
| [#1492](https://github.com/seedds/nxnative/pull/1492), head `f6fc93eb0feb1d12dfda9d96ff24270c1e3cf174` : trous dans les fichiers guest et contrôle disque | PR ouverte. Traite surtout blocs disque / pages dirty des fichiers guest. Notre log est en mémoire anonyme ; ce n'est pas le premier correctif de notre arrêt. Forcer `DM_GUEST_FILE=1` déplace une partie de la pression vers APFS sans corriger les duplications GPU, demande un essai indépendant et un budget disque. Aucune activation ici. |
| [#1486](https://github.com/seedds/nxnative/pull/1486) : arrêt à la première erreur GPU OOM iOS | PR ouverte. Réduit les suites d'erreurs/paniques après OOM GPU, pas l'empreinte et pas un correctif Jetsam ; non assimilée à une réussite. |
| [#1436](https://github.com/seedds/nxnative/pull/1436) : poolstat/texstat | PR ouverte ; diagnostic utile mais pas correctif. Le rapport externe de 8 259/8 192 Mo concerne un autre iPad et une autre pile ; notre événement est une pénurie système, pas une erreur Metal explicite. |
| [e2b76d4e / #1604](https://github.com/seedds/nxnative/commit/e2b76d4e), [b547f1e2 / #1558](https://github.com/seedds/nxnative/commit/b547f1e2), [d4c11e2b](https://github.com/seedds/nxnative/commit/d4c11e2b) : écritures CPU de terrain | Absentes. Le profil active déjà dirty/flush upload, mais la règle au niveau pool et le test d'usage du host peuvent écarter des réécritures valides. #1558 dépend du suivi d'intervalles de #1604 ; des écritures voisines partageant une page ont ensuite exigé d4c11e2b. À rétroporter comme ensemble cohérent après identification visuelle, pas en copiant isolément une ligne. |
| [0e4480d2 / #1607](https://github.com/seedds/nxnative/commit/0e4480d2), [fa9cfb84 / #1644](https://github.com/seedds/nxnative/commit/fa9cfb84) | Absentes ; vues de texture périmées et durée de résidence des textures encore détenues. Correctifs de page faults / durée de vie, pas preuve de fuite ; importants avant intégration de la série CPU terrain. |
| [d365496d / #1575](https://github.com/seedds/nxnative/commit/d365496d), [16776913 / #1376](https://github.com/seedds/nxnative/commit/16776913), [e5f1adee / #1673](https://github.com/seedds/nxnative/commit/e5f1adee), [30fb2136 / #1307](https://github.com/seedds/nxnative/commit/30fb2136) | Absentes. Respectivement débordement mesh, barrières LDSM upscaler, invariance de position végétation, archives compute. Changent les outils/chaîne ou les artefacts de compilation. À isoler après mesures ; conserver les anciens caches. Le pin contient des corrections plus anciennes float atomics et gather, mais **pas** la correction HMMA 13b432b4 : sa chaîne 23a1ea1db092 introduit précisément la régression de slot corrigée ensuite. Les mesures et le README du pin ne suffisaient pas à l’exclure. |

Source Apple : [recommendedMaxWorkingSetSize](https://developer.apple.com/documentation/metal/mtldevice/recommendedmaxworkingsetsize) est une **approximation de budget performant**, pas une preuve universelle de plafond dur à 8 Go. [currentAllocatedSize](https://developer.apple.com/documentation/metal/mtldevice/currentallocatedsize) décrit les ressources allouées du device, pas du RSS additionnable à la RAM guest.

Le [message X S2ARM](https://x.com/happyjoejiang/status/2118623895305777222) renvoie 403 via la consultation disponible. Aucun contenu primaire vérifiable ni code de ce moteur obtenu ; aucun chiffre de gain repris comme mesure comparable, aucun moteur tiers intégré. Cette piste reste non auditée.

### Modifications préparées et contraintes de validation

`security/oot2_patch_runtime.py` vérifie le SHA Git exact **et** le SHA-256 intégral de `nvn_mtl.m` avant application atomique de patchs versionnés. Une source différente ou déjà patchée est refusée. Trois variantes proposées à `workflow_dispatch` :

- `baseline` (défaut) : télémétrie seule, règles de résidence et barrières originales ;
- `depth` : télémétrie + famille de profondeur #1557 ;
- `memory-v1` : télémétrie + famille de profondeur + barrières #1556.

Toutes conservent le profil et la chaîne shaders. Les correctifs sont appliqués dans le checkout éphémère **avant tout transfert privé**. Le patch NUP/disque existant reste indépendant. Aucun workflow coûteux n'est déclenché par push/PR : seul un smoke test de compilation des sources iOS est ajouté, limité à 15 minutes, sans jeu ni shaders traduits du jeu, sans IPA, sans signature. Le compilateur compile les petits shaders propres au host requis par ses en-têtes ; ce n'est pas la reconstruction des 42 854 shaders.

Télémétrie `[oot2-mem]` : à chaque appel de mesure existant (300 frames), 240 échantillons maximum, RSS, footprint, Metal alloué, budget recommandé, marge processus, internal/compressed, temps monotone. Aucun parcours de ressources ni attente GPU ajouté. Le temps est celui de l'horloge monotone et doit être ramené au premier échantillon ; ce n'est pas une date. Ne couvre pas les pics entre échantillons, ni la phase avant les premières frames, ni les MTLCompilerService d'autres processus. Le diagnostic antérieur reste présent. Le parseur convertit correctement le champ « resident » historique en footprint ; il ne rebaptise pas un ancien log en RSS.

Validation locale initiale : 42 tests synthétiques pipeline existants réussis ; smoke `oot2_runtime_smoke.py` réussi pour les 3 variantes sur le code réellement épinglé. Il compile/exécute la fonction `image_shape` extraite, avec les constantes NVN réelles, cas depth, display/vidéo/linéaire/sparse, layout, mip, profondeur, samples et stride ; vérifie application unique et maintien des barrières d'entrée. **Ce n'est pas un test d'aliasing Metal sur GPU.** Les tests du parseur et la compilation iOS sont ajoutés à la CI ; résultats définitifs à consigner après exécution. La variante baseline demeure la valeur par défaut tant que les tests GPU et la comparaison iPad manquent.

### Protocole iPad et retour arrière

1. Conserver IPA installée, cache et sauvegardes. Archiver le `log.txt` avant chaque relancement (l'app fait tourner ses logs). Ne pas effacer les caches système ou les données du jeu pour « nettoyer » les chiffres.
2. Après compilation iOS du candidat réussie et inspection de la PR, préparer **une seule IPA expérimentale** `memory-v1` avec le cache existant ; pas de build effectué ici. Vérifier l'IPA ZIP et son hash avant remplacement. Signer/installer manuellement ; aucune installation automatique pendant l'audit.
3. Même sauvegarde et parcours : titre 30 s, chargement, maison, forêt ; rester immobile 30 s puis marche + caméra 60 s ; si stable, 5 min puis 15 min, changements de zone, retour et sauvegarde/chargement. Relever les temps réels ; ne pas appeler « stable » une minute sans crash.
4. Collecter `Documents/log.txt` du **conteneur OOT2**, et JetsamEvent si arrêt. Photographier/capturer le même endroit à mêmes réglages : terrain/trous bleus, végétation blanche, lignes horizontales, luminosité/upscaler, UI. Séparer défaut permanent, défaut au chargement et défaut après mouvement. Le message de pipeline interrompu doit être corrélé à la scène.
5. Mesurer pic RSS et footprint échantillonnés, changement après chargement, pente sur scène fixe/marche, Metal alloué et ensemble résident séparément, nombre d'erreurs de compilation, durée avant arrêt. Un second passage à cache chaud sans supprimer l'ancien cache distingue les compilations à froid d'une croissance persistante.
6. En cas de régression, revenir à l'IPA originale conservée. Pour attribution, comparer `baseline`, puis `depth`, puis `memory-v1` seulement si le gain justifie le coût des builds. Revenir au commit `d1b919f` restaure intégralement le pipeline antérieur ; pas de réduction arbitraire de `app_pool`, `mem_reserve` ou alias. Ne pas supprimer le dossier entier contenant les caches pour restaurer du code.

Les trois commandes Linux suivantes gardent le brut local. La première reste active pendant le parcours et s'arrête avec Ctrl-C ; les deux autres s'exécutent ensuite. Les stderr nxnative sont parfois exclusivement dans `log.txt` : l'absence de lignes dans syslog n'est donc **pas** une absence de consommation. Dans ce cas, utiliser le `log.txt` récupéré comme entrée du parseur.

```bash
umask 077; mkdir -p "$HOME/portage-ipados/oot-switch2/resultats/ipad-test-memory-v1"; idevicesyslog > "$HOME/portage-ipados/oot-switch2/resultats/ipad-test-memory-v1/syslog-private.txt" 2>&1
```
```bash
rg -i '\[oot2-mem\]|memory up to frame|residency set up to frame|GPU out of memory|vm-pageshortage|MTLCompilerService|XPC_ERROR_CONNECTION_INTERRUPTED' "$HOME/portage-ipados/oot-switch2/resultats/ipad-test-memory-v1/syslog-private.txt" > "$HOME/portage-ipados/oot-switch2/resultats/ipad-test-memory-v1/diagnostic.txt"
```
```bash
python3 "$HOME/portage-ipados/oot-switch2/audit-pipeline/security/oot2_memory_report.py" "$HOME/portage-ipados/oot-switch2/resultats/ipad-test-memory-v1/diagnostic.txt"
```

Critères non atteints à cette étape : baisse mesurée sur iPad, disparition du Jetsam, correction visuelle démontrée, session prolongée, sauvegarde/rechargement validés sur candidat. Les tests de code ne remplacent pas ces mesures.


### Captures utilisateur et candidat graphique graphics-v2

Les trois HEIC fournis (`IMG_0905`, `IMG_0907`, `IMG_0908`, originaux sous Téléchargements) ont été inspectés après conversion locale de prévisualisation, sans modification des originaux ni publication des images. Ils montrent des **bandes verticales périodiques** traversant la scène, y compris l'intérieur de la maison, une végétation blanche très brillante et une scène presque entièrement blanche. Les bandes noires et la surimpression FPS du lanceur ne présentent pas ce motif. Ce sont des défauts de l'image rendue ; les captures seules ne prouvent pas leur instruction fautive.

L'[issue primaire #1537](https://github.com/seedds/nxnative/issues/1537) rapporte explicitement des lignes fortes et constantes sur **notre même commit c229bd7d et chaîne 23a1ea1db092**. Elle décrit des lignes horizontales alors que les captures utilisateur sont verticales : correspondance de famille de défauts plausible, pas identité visuelle démontrée. Le correctif HMMA 13b432b4 est donc un candidat prioritaire ; il était incorrect de considérer la présence d'optimisations HMMA au pin comme preuve que ce défaut était déjà corrigé. Remplacer seulement l'upscaler final par MetalFX ne corrige pas les réseaux de lumière `agl_ndsr_vr` touchés par ce bug.

Une quatrième option **`graphics-v2`**, toujours explicite et jamais par défaut, est préparée :

- elle inclut le lot mémoire `memory-v1` ;
- HMMA : rétroportage du seul corps `HMMA_BODY` de `13b432b4`, calcul local C/D et lecture/écriture des accumulateurs de chaîne uniquement lorsque les flags le demandent ;
- mesh : arrondir l'aire des indices de primitives à des blocs de 32 (`d365496d` / #1575), évitant les écritures des lanes 126–127 hors tableau ; position `[[position, invariant]]` (`e5f1adee` / #1673), pour l'égalité de profondeur entre les deux passes de végétation ;
- LDSM : outils de traduction **officiels** du commit `167769131235226c739517a0a3e53fce48025b1f` (#1376), barrières SIMD avant/après lecture collective. Le script charge uniquement huit fichiers allowlistés depuis cet objet Git immuable : lock, cinq binaires/DLL/PDB de traduction et deux sources Ampere. Le binaire inclut aussi ATOMG.CAS de l'amont intervenu entre le pin et ce commit ; le source correspondant est copié avec lui. Aucun .NET recompilé localement, aucun binaire arbitraire ; chaque fichier a son SHA-256 intégral dans `security/oot2_graphics_manifest.json`. Les fichiers de départ sont également vérifiés ;
- `dmsh_chain.py --header` génère réellement la nouvelle chaîne **`07ebbab64578`**, vérifiée contre le manifeste. Le host n'accepte pas de vieux shaders sous une fausse estampille. Les anciennes bibliothèques `23a1ea1db092` et le CAS privé sont préservés ; les clés nouvelles peuvent imposer une reconstruction substantielle. Le taux de réutilisation reste à mesurer.

Cette variante est une pile de correctifs candidats issus de défauts démontrés dans l'amont, pas une correction graphique iPad déjà validée. Le suivi de terrain CPU (#1604/#1558) est différé : les captures donnent priorité aux réseaux de lumière/upscaling et aux meshes plutôt qu'aux trous de terrain.

Validation locale graphique : **29 tests meshstage, 28 exécutés / 1 ignoré (compilateur Metal absent sous Linux)** ; **10 tests HMMA, 6 exécutés / 4 ignorés (GPU Xcode et traducteur natif Mac absents)**. Les tests incluent le cas max_p=126 et l'invariance. Le test GPU d'accumulateur apporte une référence numérique sur Mac ; il ne s'exécute pas sur Linux. Les tests/compilation iOS de la CI doivent être relancés sur cette nouvelle pile avant toute fusion. Aucun build IPA déclenché ; ne pas lancer d'abord une IPA memory-v1 qui laisserait volontairement ces défauts de shader si l'objectif est de limiter les compilations.

La CI du premier lot mémoire seul, [run 42399313542](https://github.com/Domessy/ffr-ipados-build/actions/runs/42399313542), commit `2b964ffe88b1f6f94bc9ffbe55b3a88eaaa638f1`, a réussi **Linux, macOS, compilation des sources iOS**. La PR est [#28](https://github.com/Domessy/ffr-ipados-build/pull/28). Ce succès ne valide pas automatiquement les ajouts graphics-v2 suivants.

### Validation finale du candidat et test immédiat sans recompilation

La PR [#28](https://github.com/Domessy/ffr-ipados-build/pull/28) est **fusionnée**, commit de fusion `3cd6f6251202a20c3f1429e6748d758ad1964506`, après succès du [run 42399812419](https://github.com/Domessy/ffr-ipados-build/actions/runs/42399812419) sur le head exact `c8d626ce247246df5149c05819ae7fd335d5b209` :

- Linux et macOS : 46 tests pipeline, smoke des trois variantes mémoire, application/fingerprints du candidat graphique ;
- Xcode 27.2, Metal 32023.922 : **29/29 tests meshstage réussis**, y compris compilation de fixtures Mac/iOS ; **10 tests HMMA, 9 exécutés réussis / 1 ignoré** (TranslatorFlags nécessite le lancement explicite du traducteur, non configuré pour cette suite). Les tests HMMA GPU ont donc réellement été exécutés ici, y compris la référence numérique des appels hors chaîne ;
- **261 sources iOS compilées, 0 échec**, 13 petites bibliothèques Metal propres au host, aucune donnée de jeu et aucun shader du jeu compilé ;
- Linux local : **17/17 tests `dm/tools/tests/test_nsp_chain.py`** réussis avec la nouvelle chaîne.

Cela valide le candidat synthétique/compilation, **pas** le rendu de l'IPA sur iPad. Aucune nouvelle IPA n'a été construite. Les captures et le journal justifient maintenant une seule prochaine compilation `graphics-v2`, plutôt que plusieurs reconstructions mémoire puis graphique, mais l'essai réversible suivant peut d'abord préciser le rôle du stockage guest.

Le stockage de l'iPad a été lu via `com.apple.disk_usage` : **222 911 045 632 octets disponibles (~207,6 Gio)** au moment de la préparation. La condition par défaut de `guest_file_wanted` au pin est `pool > room` : les 9 Gio du pool sont inférieurs aux ~11,96 Gio de marge initiale, d'où le mode anonyme, sans tenir compte des futures textures/pipelines Metal. Ce choix initial explique un mécanisme de pression plausible ; une réserve GPU arbitraire n'est pas introduite dans le code.

Un essai **sans nouvelle compilation et sans installation** est préparé sur l'iPad : le seul fichier `Documents/env.txt` du **conteneur de données OOT2** est créé, après vérification qu'il n'existait pas, avec `DM_GUEST_FILE=1`. Aucun autre réglage, profil ou cache n'est changé. Il s'agit de fichiers guest sparse, privés et désindexés après ouverture, déjà implémentés par nxnative, pas de l'ajout d'un swap système. Les buffers no-copy qui restent câblés par Metal peuvent limiter le gain ; cela ne corrige ni les doublons GPU ni les shaders. Le garde-fou disque original de 5 Gio reste actif. Les fichiers disparaissent après fermeture de leurs descripteurs ; pendant un long essai ils peuvent conserver les blocs du maximum déjà touché (#1492 non intégré).

- L'application n'a pas été lancée automatiquement. L'utilisateur a reçu la consigne de fermer complètement LiveContainer, le rouvrir puis tester OOT2 2–3 minutes sur le même parcours, mouvement/caméra. **Résultat non encore reçu à ce point.** Vérifier dans le prochain log la ligne `DM_GUEST_FILE=1` et `guest memory ... files` avant d'interpréter toute différence.
- Copie locale privée de provenance/restauration : `resultats/ipad-audit-20261107/guest-file-experiment.json`, chemin exact, ancien fichier absent, SHA-256 du contenu posé. Le montage a ensuite été démonté. L'iPad est donc laissé avec cette seule configuration d'essai, pas avec une IPA corrigée.
- Retour arrière du test immédiat : fermer LiveContainer, supprimer **seulement ce nouveau `env.txt` du conteneur OOT2**, puis relancer. Pour automatiser le retrait depuis Linux, vérifier d'abord que son SHA-256 est encore celui du ledger ; s'il a changé, préserver le contenu et inspecter avant toute suppression. Ne jamais retirer un env.txt d'une autre application ni supprimer le conteneur de jeu.
- Les défauts graphiques restent attendus avec cette IPA originale : le test immédiat évalue la mémoire, pas les corrections `graphics-v2` fusionnées dans les outils.

Un enregistrement syslog privé borné à 240 s a été démarré localement pour cet essai ; sa fin ne démontre pas que le jeu a été lancé ni qu'un test a eu lieu. Le `log.txt` du conteneur OOT2 reste la source principale à récupérer après le retour utilisateur. Aucun log brut ni identifiant de conteneur n'est ajouté à GitHub.

### Résultat iPad du test guest-file — 07/11/2026

Retour utilisateur : **2–3 minutes ingame sans crash**, avec baisses de framerate et glitchs persistants. Lecture USB du journal courant, sauvegardé localement sous `resultats/ipad-audit-20261107/guest-file-live-log.txt` (451 368 octets au prélèvement), confirme `boot: env DM_GUEST_FILE=1 (env.txt)` et `guest memory ... DM_GUEST_FILE 1: in files`. Pas de changement d'IPA, chaîne originale et défauts graphiques encore présents.

Mesures extraites (`guest-file-summary.json`, privé) :

- 25 échantillons de la mesure historique `memory up to frame` = **phys_footprint**, pas RSS ; maximum échantillonné **5 181 Mio = 5,06 Gio**, dernier échantillon **3 978 Mio = 3,88 Gio** ; l'autre mesure guest-file finit à 3,86 Gio. Avant : maximum échantillonné 9 913 Mio = 9,68 Gio. Diminution du maximum observé d'environ **48 %** ; parcours et état des caches non strictement contrôlés, donc ce n'est pas un benchmark isolé reproductible à 48 % garanti ;
- dernier temps de frame visible **232,64 s** depuis le démarrage du host, frame 10 675 ; confirme une session plus longue que le journal initial (~116 s), sans transformer ce temps de host en durée exacte de déplacement ingame ;
- zéro ligne `GPU out of memory:` et zéro `XPC_ERROR_CONNECTION_INTERRUPTED` dans ce prélèvement ; le retour utilisateur confirme l'absence de crash jusqu'à son message, pas la stabilité prolongée ;
- Metal alloué reste élevé : maximum **16 374 Mio**, dernier **15 172 Mio**. Le mode fichiers ne corrige pas cette allocation et ces chiffres ne sont pas du RSS additionnable au footprint ;
- fichiers guest : 13 fichiers sparse, 12,50 Gio de longueur virtuelle totale ; **7,13 Gio de blocs réellement alloués** en fin de prélèvement ; volume APFS du processus : **38,5 Gio libres initialement, 31,5 Gio ensuite**, garde-fou de 5 Gio non atteint.

**Correction de l'estimation de stockage précédente :** le chiffre `com.apple.disk_usage TotalDataAvailable` de ~207,6 Gio n'est pas la capacité immédiatement disponible observée par `statfs` dans l'app. La mesure du volume vue par le processus (38,5 → 31,5 Gio ici) prime pour le budget de ce test ; ne pas présenter les ~208 Gio comme marge réellement disponible aux fichiers guest. L'écart de méthodes est constaté, son origine exacte (espace récupérable/réservations/comptabilité) n'est pas établie.

Conclusion vérifiable : le choix de mémoire guest anonyme contribuait fortement à l'empreinte comptabilisée ; l'adossement à des fichiers réduit nettement cette empreinte et l'essai dépasse la durée du premier journal. Il ne démontre pas une disparition définitive du Jetsam. Les framerates et glitchs persistants restent distincts : les captures appellent toujours les corrections de shaders de `graphics-v2`, et les deux correctifs Metal restent pertinents. Aucun nouveau build IPA lancé lors de ce point de mesure. Configuration d'essai laissée active, retrait selon la procédure précédente ; aucun autre changement sur l'iPad.

### Terrain absent et session prolongée — 07/11/2026

Nouveau retour utilisateur : pas de crash, jeu plutôt fluide entre des chutes drastiques intermittentes ; lignes à l'écran et sol manquant. Capture privée `E97F4A77-FBAF-4ED6-9372-69760E3E6118.png` inspectée : grands trous bleus à la place du terrain, végétation et objets conservés au-dessus, bandes verticales périodiques ; FPS affiché 59 sur cette seule image. Ce n'est pas une mesure du framerate sur toute la session.

Lecture USB en mode lecture seule, diagnostic privé `resultats/ipad-audit-20261107/terrain-live-log.txt` : 1 432 973 octets au prélèvement, dernier timing frame 36 227 à **783,62 s (~13 min depuis démarrage host)**. Dernière ligne guest-file : **4,14 Gio de footprint, pic de cette comptabilité 5,47 Gio**, **7,17 Gio de fichiers alloués sur APFS**, **31,4 Gio libres**. Le dernier échantillon NVN est 4 183 Mio de footprint / 15 365 Mio Metal alloué. Zéro ligne OOM GPU et zéro interruption du compilateur. Les deux méthodes de comptabilité ne doivent toujours pas être confondues avec du RSS ; pas de preuve de stabilité illimitée.

**Gels de framerate : preuves et limite.** Le journal `longframe` montre notamment :

| Frame / temps host | Temps frame | Pipelines nouveaux / temps compilation | GPU |
|---|---:|---:|---:|
| 26 258 / 567,48 s | 7 464,9 ms | 6 / 7 450,1 ms | 27,7 ms |
| 28 105 / 610,94 s | 6 857,6 ms | 6 / 6 772,0 ms | 29,9 ms |
| 6 485 / 147,04 s | 4 850,7 ms | 3 / 4 840,2 ms | 21,6 ms |
| 34 365 / 750,56 s | 4 773,8 ms | 3 / 4 744,8 ms | 25,9 ms |
| 33 148 / 724,15 s | 22 478,9 ms | 0 / 0 ms | 23,7 ms |

Plusieurs gels sont donc directement corrélés aux compilations PSO synchrones, alors que le GPU met quelques dizaines de ms. Le gel de 22,48 s ne l'est pas (submit+present 278,8 ms, zéro upload enregistré) : blocage CPU/hors compteurs non attribué. Ne pas l'expliquer arbitrairement par le paging APFS, le GPU ou la compilation. Ne pas promettre que les corrections de terrain résoudront tous les gels. Conserver les caches et comparer un deuxième passage sur le même parcours ; toute nouvelle chaîne shader rend une partie des caches PSO de nouveau froide. Les shaders metallib compilés offline et les PSO spécialisés à l'exécution sont des artefacts distincts.

**Candidat `terrain-v3`, ajouté après cette capture.** Il inclut `graphics-v2` et `memory-v1`, conserve le pin du moteur et la chaîne graphique candidate `07ebbab64578`, et rétroporte les corrections host suivantes ensemble :

- `e2b76d4e` / #1604 : propriété GPU suivie par **intervalles de stockage de textures**, plutôt qu'un bit pour tout le pool ; une normal map rendue dans le pool ne rend plus les height/blend/hole maps voisines inéligibles à leur premier upload CPU ;
- `b547f1e2` / #1558 : les cartes CPU réécrites après première utilisation sont réévaluées suivant la même règle de stockage, plutôt que rejetées parce que Metal leur avait donné l'usage renderTarget ; les réécritures futures restent observées lorsque le GPU possède temporairement les octets ;
- `d4c11e2b` : hash des portions de texture dans les pages de bord partagées, pour qu'une écriture CPU à côté ne déclenche pas à tort un upload qui écraserait le rendu GPU ;
- `fa9cfb84` / #1644 : une texture rendue encore référencée par un serial live/finalisé reste résidente après retirement, jusqu'à disparition de sa dernière référence ; le correctif terrain de propriété ne doit pas introduire de page faults GPU ;
- `0e4480d2` / #1607 : un ID sans texture invalide sa vue mise en cache au lieu de conserver une vue libérée lorsque `nil == nil`.

Patch local `security/oot2_terrain.patch`, six fichiers (quatre sources/headers NVN, deux tests GPU synthétiques), **631 ajouts / 95 suppressions** sur le pin. Deux adaptations de backport sont explicites : conservation de `REC_SNAP` dans CopyBufferToTexture et remplacement du seul appel de propriété (le refactoring `rec_copy` de l'amont n'est pas requis) ; commentaire de lifetime adapté au cache de tables du pin, sans importer l'optimisation de table #1489. Pas de shader traduit ni de profil de jeu modifié par ce lot terrain.

`security/oot2_patch_terrain.py` exige le SHA exact du pin et les SHA-256 des six fichiers **après `memory-v1`** ; application unique et atomique par git apply, avant toute donnée privée. Le manifeste conserve la provenance ; la CI doit vérifier l'empilement complet dans un checkout propre, compiler les sources iOS puis exécuter **`check_t_cpu_storage` et `check_t_cpu_tex --metal`** avec validation Metal. Linux local : 46 tests pipeline toujours réussis, application terrain réussie sur la pile préparée. Les tests GPU et la compilation de ce nouveau lot ne sont pas encore déclarés réussis à ce point.

Protocole du prochain candidat : garder le réglage guest-file qui a permis la session prolongée ; comparer ce même point de vue et le sol après déplacement/changement de zone, les cartes devant se réuploader sans remettre les normal maps à zéro. Tester aussi la réutilisation des textures et un passage prolongé pour les durées de vie GPU. Les bandes restent traitées par le lot shaders déjà préparé. Aucune nouvelle IPA construite pendant ce diagnostic ; aucun réglage supplémentaire modifié sur l'iPad.

Première CI terrain : [run 42401996087](https://github.com/Domessy/ffr-ipados-build/actions/runs/42401996087), head `38f0615118b92e5e10e9538e1b4476e83ed613cc` : Linux/macOS synthétiques et compilation des **261 sources iOS** réussis ; compilation des deux tests de textures réussie, puis exécution refusée par `mtl_init` : **Apple Paravirtual device sans famille GPU Metal 4**. L'échec ne démontre pas une réussite des tests GPU ni une régression du correctif.

Adaptation de validation : le test storage ajoute un mode CPU `--ownership-only`, qui exerce directement les fonctions de production d'intervalles et le vrai suivi de pages protégées : propriété limitée à la texture, voisin dans le même pool non contaminé, faute de page sur réécriture CPU, écrasement GPU partiel préservant l'état des intervalles extérieurs, reprise de propriété GPU, destruction du pool, exclusion des pools virtuels. Le test CPU de classification de `t_cpu_tex` est aussi exécuté. Une sonde de capacité Metal 4 décide si les tests GPU complets peuvent ensuite s'exécuter ; son absence est annoncée explicitement, jamais comptée comme un succès GPU. Aucune voie de production n'est assouplie pour le runner.

### Terrain candidat validé pour compilation, puis build expérimental lancé

CI [42402309982](https://github.com/Domessy/ffr-ipados-build/actions/runs/42402309982), head exact `17004987ab1f04f0b0bcf3b00ec25f903b2cf37f` : Linux/macOS réussis ; **261 sources iOS, 0 échec** ; 29 tests meshstage réussis, 10 HMMA dont 1 ignoré ; **10 checks ownership-only et 23 checks classification, 0 échec**. Les deux binaires de tests textures complets compilent. La sonde confirme Apple Paravirtual GPU sans Metal 4 : leurs exécutions GPU complètes sont **non validées**, sans modifier le backend pour contourner cette exigence. La PR [#31](https://github.com/Domessy/ffr-ipados-build/pull/31) fusionne la variante expérimentale opt-in, commit `73d55ac056df9bfece8aa8c4645edf4e4cf80b79`. Le défaut du workflow reste baseline ; ce n'est pas une déclaration de terrain corrigé sur iPad.

Le journal révèle en outre une liste embarquée `pso_manifest.tsv` vide et une liste utilisateur de 9 267 lignes (8 316 shaders, 838 pipelines render, 113 compute), préchauffée en ~0,83 s sur cette session. Cela n'empêche pas des variantes PSO nouvelles de bloquer un draw plus tard. Ne pas effacer cette liste utilisateur ; le manifeste enrichi de l'amont n'a pas été importé dans ce lot, et les gels restent un critère de test distinct. Le gel de 22,48 s est proche de messages graphics suspend/resume et de reprise audio/focus, ce qui rend une attribution à un défaut de rendu ou au paging encore moins justifiée sans reproduction contrôlée.

**Une unique compilation IPA `terrain-v3` est effectivement déclenchée** : [run 42402648755](https://github.com/Domessy/ffr-ipados-build/actions/runs/42402648755), créé le 07/11/2026 à 19:42:57 heure de Paris, workflow source **`73d55ac056df9bfece8aa8c4645edf4e4cf80b79`**, `mode=build`, `runtime_variant=terrain-v3`. Le lancement intervient après audit des causes, preuve visuelle du terrain, validation CPU et compilation iOS ; son objectif est précisément la validation graphique/résidence Metal 4 sur l'iPad, que le GPU virtuel du runner ne peut pas faire. Pas de compilations successives intermédiaires memory-v1 puis graphics-v2.

Avant lancement, copies locales Btrfs copy-on-write créées sans modifier les originaux :

- `/home/syssy/portage-ipados/oot-switch2/resultats/ZeldaOcarinaOfTime-baseline-c229bd7-guest-file-tested.ipa`, même taille que l'IPA existante, répertoire ZIP relu et présence du binaire DmIOS vérifiée (pas de décompression complète prétendue) ;
- `resultats/oot2-build-baseline-c229bd7.log` ; ledger privé `resultats/terrain-v3-build-request.json` ;
- cache de shaders original intact ; passerelle CAS à création exclusive, variantes en conflit préservées ; checkpoints périodiques existants, arrêt contrôlé à 7 Gio libres et limite de temps du wrapper maintenus ; aucune clé transmise.

À ce point, seul le démarrage du run et ses premiers contrôles scripts/secrets sont confirmés. **Ni la réussite du build, ni une IPA disponible, ni la correction visuelle ne sont annoncées.** La chaîne graphique candidate change : ne pas promettre un taux de cache ni une durée de compilation. La réception éventuelle utilise le chemin standard `resultats/ZeldaOcarinaOfTime.ipa`, l'ancienne version restant conservée sous le nom ci-dessus. En cas d'échec, inspecter étape et diagnostic privé avant toute relance.

Pour le prochain test : conserver les données/sauvegardes existantes du conteneur OOT2 dans LiveContainer. Le réglage `Documents/env.txt` guest-file appartient à ce conteneur et n'est pas un changement système ; **vérifier de nouveau la ligne `DM_GUEST_FILE 1: in files` après remplacement de l'application**, surtout si LiveContainer crée un nouveau conteneur. Ne pas interpréter un test anonyme comme celui du candidat file-backed. Aucune signature ni installation automatique sur l'iPad n'est réalisée par le workflow.
