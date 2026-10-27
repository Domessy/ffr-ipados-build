# Final Fantasy Resonance → iPadOS (GitHub Actions)

This PUBLIC repository contains only the build workflow and a restricted SSH gateway. The NSP files, `prod.keys`, and compiled IPA must never be committed or uploaded as Actions artifacts.

## Security model

- GitHub-hosted `macos-15` builds are disabled by default: the job needs the repository variable `FFR_SECURITY_READY=true`.
- The runner connects using Tailscale and a dedicated, **rotated** SSH key.
- CachyOS `authorized_keys` forces that one key to execute only `security/ffr_ssh_gate.py`, restricted to Tailscale IPv4 peers (`100.64.0.0/10`).
- The gateway permits six literal operations: `probe`, `read-base`, `read-update`, `read-keys`, `write-ipa`, and `write-log`. It has **no shell or arbitrary file access**. Transfers are direct from CachyOS to the ephemeral Mac and back.
- Outputs are written atomically to `~/portage-ipados/ff-resonance/resultats/`. The old unrestricted SSH credential is removed from CachyOS and replaced in GitHub Secrets when the hardening script executes.
- nxnative is pinned to a specific commit hash. The Tailscale CLI is installed through the Homebrew formula. GitHub Actions, Homebrew, Python dependencies and the operating-system image remain external trust boundaries.
- Full nxnative console output is intentionally kept **out of public GitHub Actions logs**. The private build log is sent only to CachyOS.
- No uploaded GitHub Actions artifacts contain the game, IPA or key files.
- SSH secrets are still available to code running on the GitHub-hosted runner; the game decryption key material **must** be temporarily copied onto that runner. This is not a zero-trust solution.

## Before the next build (CachyOS)

Your existing files and original NSPs remain in place. The original `setup.sh` is **not** to be rerun: it created the old general-purpose SSH key.

Update the local checkout, then run the hardening procedure once:

```bash
cd "$HOME/portage-ipados/ff-resonance/github-build"
git pull --ff-only origin main
bash security/harden-cachyos.sh
```

The hardening script:
1. Disables CI builds first.
2. Generates a new FFR-only SSH key; removes the original FFR key from `authorized_keys`.
3. Backs up `authorized_keys` and inserts a forced-command entry while preserving other keys.
4. Rotates `FFR_SSH_KEY` in GitHub Secrets; sets `FFR_SSH_USER`.
5. Re-enables builds only after the local configuration is complete.

It **does not start a build**. The SSH gateway always runs under your own CachyOS account, so protecting the private key and repository write access remains necessary. A forced-command SSH key cannot be used as a normal shell, even if the private key is stolen.

## Tailscale network policy (manual)

The tag used by the ephemeral CI runner should be given access only to your CachyOS device on TCP port 22. Use Tailscale's admin console to constrain the tag's grants/ACL; the `from=100.64.0.0/10` restriction on the SSH key alone is **not** a complete Tailscale ACL. If the tag is not yet configured, adjust Tailscale policy before running.

The Mac runner installs the `tailscale` Homebrew formula and starts `tailscaled` with an in-memory state. This intentionally replaces `tailscale/github-action@v4`: that action unconditionally calls macOS `networksetup` when MagicDNS is enabled, even if `--accept-dns=false` was supplied, and blocked earlier runs. The manual connection does not modify macOS DNS settings; SSH uses the Tailscale IPv4 address.

The CI auth key should be revoked in the Tailscale admin console when finished. For repeated use, replace the reusable auth key with a scoped OAuth/OIDC credential.

## Build

```bash
gh workflow run build-ffr.yml -R Domessy/ffr-ipados-build
gh run watch -R Domessy/ffr-ipados-build
```

Game assets remain on CachyOS, transferred via encrypted SSH directly to the temporary GitHub runner. The resulting IPA and `ffr-build.log` return to `~/portage-ipados/ff-resonance/resultats/`.

## Disable or revert

```bash
cd "$HOME/portage-ipados/ff-resonance/github-build"
bash security/disable-cachyos.sh
```

This disables future jobs and removes both FFR public keys from `authorized_keys`, **without restoring the previously unrestricted SSH access**. It does not touch game files, other SSH keys, the backup of `authorized_keys` or generated IPA.

After final use, also revoke the FFR Tailscale auth key in the Tailscale admin console, and remove the dedicated GitHub Secrets if no longer needed. If desired, delete only the dedicated `~/.ssh/ffr-gh-actions*` key files after the public keys have been de-authorized.

## Limitations

- This setup has not yet completed an end-to-end nxnative build; the build could fail on memory limits, toolchain compatibility or iPadOS signing.
- The runner is temporary and external. An untrusted change to the workflow or build dependencies could still leak temporary inputs; review any future changes before use.
- The build job lasts at most 180 minutes. The game has not yet been confirmed to launch on iPadOS 27.
