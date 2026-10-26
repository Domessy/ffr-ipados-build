# FINAL FANTASY RESONANCE -> iPadOS : GitHub Actions gratuit

Le depot GitHub ne contient **que ce workflow**, sans NSP, `prod.keys`, ressources du jeu ou IPA. `workflow_dispatch` uniquement.

Le workflow utilise un runner Apple Silicon `macos-15` standard, supprime les Xcode non necessaires sur cette machine ephemere, copie directement les deux NSP et `prod.keys` par SSH sur Tailscale depuis CachyOS, compile avec [nxnative](https://github.com/seedds/nxnative), puis renvoie l'IPA et le journal sur CachyOS. Aucune publication d'artefacts GitHub.

## Premiere utilisation sur CachyOS

- Pre-requis : `gh`, `git`, `openssh` (service `sshd`), `tailscale` deja connecte et `prod.keys` extrait de sa propre Switch.
- Sur CachyOS, extraire l'archive fournie, ouvrir un terminal dans le dossier et executer : `bash setup.sh`.
- S'il manque GitHub CLI : `sudo pacman -S github-cli` (paquet amovible). S'il manque OpenSSH : `sudo pacman -S openssh`.
- Le script installe une cle SSH distincte, limitee aux IP Tailscale, et cree un lien local vers `prod.keys`. Il cree un depot **public** de code sur ton compte GitHub. Les deux NSP restent a `/home/syssy/Documents/FF Resonance/`.
- Generer une cle Tailscale pour CI sur https://login.tailscale.com/admin/settings/keys et la coller lorsque le script la demande. Preferer une cle reutilisable, ephemere et taguee, avec des restrictions reseau adaptees. Si les ACL Tailscale empechent l'acces du runner au PC, les ajuster pour n'autoriser que l'acces au port 22 du PC.
- Puis `gh workflow run build-ffr.yml -R TON_COMPTE/ffr-ipados-build` et `gh run watch -R TON_COMPTE/ffr-ipados-build`.

## Resultat

`~/portage-ipados/ff-resonance/resultats/FFR-iPadOS.ipa`, et `ffr-build.log` pour le diagnostic en cas d'echec de compilation.

## Limites

- **Pas teste de bout en bout sur les runners GitHub** : la premiere compilation peut echouer sur les dependances, la place restante ou l'adaptation nxnative a macOS 15 / Xcode 26.
- Le runner annonce 14 Go de SSD ; le workflow tente de recuperer au moins 30 Go en supprimant les Xcode non selectionnes. C'est une hypothese d'optimisation basee sur la presence des versions preinstallees, pas une garantie. En dessous de 30 Go, il s'arrete avant de copier les NSP.
- Le runner Apple Silicon standard dispose de 7 Go de RAM, ce qui peut egalement limiter cette compilation.
- Pour un depot **public**, les runners standard GitHub Actions sont gratuits ; les **logs de build sont publics**. Ne jamais activer de logs de debug affichant les cles. Les GitHub Secrets sont accessibles au workflow et les cles sont temporairement transferees sur une infrastructure tierce : il subsiste un risque de confidentialite. Le code public seul ne contient aucun fichier du jeu.
- Ne pas autoriser les pull requests non examinees a modifier le workflow et ne jamais y ajouter de `pull_request` ou `pull_request_target` avec acces aux secrets.
- Au terme de la construction, invalider la cle d'authentification Tailscale CI si elle n'est pas reutilisee.
- La sortie est non signee. L'installation depend des entitlements et de LiveContainer/SideStore, et le fonctionnement du jeu sur iPadOS 27 n'est pas garanti.

## Annulation des modifications locales

D'abord supprimer le depot GitHub et les secrets depuis GitHub, puis supprimer la cle SSH de `~/.ssh/authorized_keys` correspondant au commentaire `ffr-github-actions`. Ensuite :

```bash
rm -f "$HOME/.ssh/ffr-gh-actions" "$HOME/.ssh/ffr-gh-actions.pub"
rm -f "$HOME/portage-ipados/ff-resonance/private/prod.keys"
rm -rf "$HOME/portage-ipados/ff-resonance/github-build"
```

Ne pas supprimer les NSP ou les autres repertoires du projet. Si `sshd` a ete demarre uniquement pour ce test, l'arreter avec `sudo systemctl stop sshd`. Si des paquets ont ete ajoutes specifiquement pour ce test, les retirer apres verification des dependances.

L'archive inclut egalement `cleanup-local.sh`, qui retire la cle SSH dediee de `authorized_keys` et le lien `prod.keys`, sans toucher aux fichiers du jeu, aux autres cles SSH ou aux resultats du build.
