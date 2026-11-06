# The Legend of Zelda: Ocarina of Time — Switch 2 NUP → IPA iPadOS

État au 06/11/2026 : NUP utilisateur inspecté **localement par l’utilisateur** (en-tête et TOC seulement), aucune donnée du jeu ni clé transférée à GitHub, IPA non construite. Les tests synthétiques du pipeline initial ont réussi ; correctif de compatibilité standalone en cours de validation. Aucun lancement automatique sur l’iPad.

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
5. Le précontrôle mesure l’espace libre sur le runner **avant** un transfert potentiellement supérieur à 25 Go : budget calculé `2 × taille NUP + 32 Gio`. En cas d’insuffisance, ne pas forcer la compilation sur un runner trop petit.
6. Aucune source, clé ou IPA n’est publiée en artifact GitHub. La passerelle SSH et le stockage de sorties restent isolés pour OOT2.

## Retour arrière

Supprimer seulement `~/portage-ipados/oot-switch2/` (après sauvegarde éventuelle de l’IPA et du cache). Le dossier `~/Documents/The Legend of Zelda Ocarina of TIme/`, le NUP et les clés ne sont jamais modifiés. Si le pipeline est abandonné, retirer séparément la route `oot2-` du dispatch GitHub et le workflow dédié ; aucune autre application ni configuration CachyOS n’est touchée.

## Diagnostic utilisateur et correctif standalone du 06/11/2026

- L'exécution initiale de `security/setup_oot2.sh` s'arrêtait avec `OOT2_DIAG_V1 source=ok nup=fail reason=header`.
- Signature NUP v1 correcte, taille déclarée égale à la taille réelle, champ réservé de l'en-tête `1`, TOC SHA-256 valide.
- Un seul paquet `update` v131072, `standalone_update=1`, ExeFS/RomFS référencés. Le pipeline initial attendait incorrectement `base=1`.
- Correctif proposé : alignement sur nxnative pour le champ réservé et acceptation du cas standalone dans le validateur, la configuration locale et les deux vérifications du workflow. Tests de non-régression synthétiques sur les deux variantes.
- Suite : fusion après CI, `git pull --ff-only`, `bash security/setup_oot2.sh`, puis `mode=preflight` uniquement. Le build reste une action explicite séparée.
