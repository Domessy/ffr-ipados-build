# Hollow Knight: Silksong — iPadOS Build

This repository includes an experimental [GitHub Actions workflow](.github/workflows/build-silksong.yml) based on [nxnative](https://github.com/seedds/nxnative).

The upstream game profile is available at [nxnative's Silksong profile](https://github.com/seedds/nxnative/tree/main/dm/games/010013C00E930000). Compatibility depends on the game revision, toolchain, and target environment.

The workflow is configured independently from the other game build and uses separate build outputs and compilation caches.

No game files, decryption keys, generated IPAs, private logs, or personal environment configuration are included in this document. Build inputs and credentials must be supplied and protected outside the public repository.

See the [repository overview](README.md) for security and scope limitations.
