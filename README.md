# Final Fantasy Resonance → iPadOS (GitHub Actions)

This PUBLIC repository contains only the build workflow and a restricted SSH gateway. The NSP files, `prod.keys`, and compiled IPA must never be committed or uploaded as Actions artifacts.

## Security model

- GitHub-hosted `xcode-27` (Apple Silicon, Xcode 27.1) builds are disabled by default: the job needs the repository variable `FFR_SECURITY_READY=true`.
- The runner connects using Tailscale and a dedicated, **rotated** SSH key.
- CachyOS `authorized_keys` forces that one key to execute only `security/ffr_ssh_gate.py`, restricted to Tailscale IPv4 peers (`100.64.0.0/10`).
- The gateway permits eight literal operations: `probe`, `read-base`, `read-update`, `read-keys`, `write-ipa`, `write-log`, `read-cache` and `write-cache`. It has **no shell or arbitrary file access**; the cache operations are confined to a dedicated directory. Transfers are direct from CachyOS to the ephemeral Mac and back.
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

- Run #5 successfully transferred both NSPs and the Nintendo key file, then nxnative aborted because the older macos-15 image exposed Metal 32023.864 instead of the locked 32023.921 compiler. The workflow now uses `xcode-27` with Xcode 27.1; it checks the exact Metal compiler before transferring private files. End-to-end compilation and iPadOS 27 execution have not yet been validated.
- The runner is temporary and external. An untrusted change to the workflow or build dependencies could still leak temporary inputs; review any future changes before use.
- The restricted SSH gateway now permits `read-cache` and `write-cache` for a dedicated shader-cache directory in addition to the six original operations; cache contents never reach GitHub artifacts.
- Run #7 reached the previous 180-minute job timeout during shader compilation. The job limit is now 345 minutes (under GitHub's 360-minute ceiling), with public timing-only heartbeat and a private diagnostic snapshot periodically copied to CachyOS. The game has not yet been confirmed to launch on iPadOS 27.

## Resumable Metal shader compilation (after run #7)

Run #7 reached about 25,031 / 73,496 shaders (34%) when GitHub cancelled the job at its configured 180-minute limit. It was advancing, not hung. Its cache was stored only on the ephemeral runner and cannot be recovered.

From the next run onward, the workflow:
- checks out this repository's exact commit, installs the pinned nxnative version and Xcode 27.1, then establishes the already restricted SSH session;
- restores the private shader content-addressed cache from `~/portage-ipados/ff-resonance/shader-cache/` on CachyOS via the forced `read-cache` command;
- transfers the original NSPs and `prod.keys` over SSH as before;
- starts nxnative with `DMSH_CAS` set to a separate cache directory on the ephemeral Mac;
- every ~15 minutes sends only newly created cache entries via the forced `write-cache` command;
- voluntarily stops a still-running build at 240 minutes of build time (or low free disk space), saves one final incremental snapshot, and returns a non-zero status so a NEW run can continue.

Each run will still need to transfer the base/update NSPs. The 345-minute job setting is unchanged, to leave time for private cache transfers and cleanup. A run that stops to checkpoint will appear as a failure in GitHub Actions, which does not necessarily mean the compilation has failed.

**Before the next run**, update the existing local checkout so its forced-command Python gateway knows `read-cache` and `write-cache`:

```bash
cd "$HOME/portage-ipados/ff-resonance/github-build"
git pull --ff-only origin main
```

No new SSH key, Tailscale configuration, package installation, or `harden-cachyos.sh` rerun is needed. The local gateway is the same already-authorized path; its allowlist now has these two extra cache-specific operations.

This cache is local and potentially large; it contains derived compiled shader code, not just generic build artifacts. Do not publish it or upload it to GitHub artifacts. Its validity depends on using the same nxnative source, profile, Metal compiler and SDK; the upstream cache keys reject incompatible entries.

The public build output reports only elapsed time, private log length, free disk and checkpoint status. Full diagnostics remain in `~/portage-ipados/ff-resonance/resultats/ffr-build.log`.
