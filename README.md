# iPadOS Game Build Experiments

Experimental GitHub Actions pipelines for building native iPadOS applications with [nxnative](https://github.com/seedds/nxnative).

## Workflows

- **Final Fantasy Resonance:** [build-ffr.yml](.github/workflows/build-ffr.yml)
- **Hollow Knight: Silksong:** [build-silksong.yml](.github/workflows/build-silksong.yml)

Each workflow uses a macOS build environment and is intended for inputs that the operator is authorized to use. Game assets, decryption keys, signing credentials, build outputs, and private diagnostics are **not distributed through this repository**.

## Security

The workflows require separately configured, access-restricted private inputs. Review workflow and dependency changes before executing them. Do not commit game files, credentials, compiled shader caches, private logs, or generated IPAs.

Public repository code and GitHub Actions logs are visible to others. The build environment is externally hosted; keeping a credential in GitHub Secrets does not eliminate the need to trust code executed by the workflow.

## Status

This is an experimental, independently maintained build setup. Successful compilation does not guarantee compatibility or performance on every iPadOS version or device.

Upstream implementation and game compatibility information: [seedds/nxnative](https://github.com/seedds/nxnative).
