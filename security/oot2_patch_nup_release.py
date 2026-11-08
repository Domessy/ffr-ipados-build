#!/usr/bin/env python3
"""Patch only the PINNED, ephemeral nxnative checkout for the OOT2 runner.

nxnative's Nup object keeps a read-only mmap of the original NUP for the
duration of main(). After extraction and optional DLC handling, the OOT2
single-update NUP is no longer consulted; keeping it mapped occupies ~23.3 GiB
of precious GitHub-hosted Mac disk while shader compilation is running.

This surgical opt-in patch releases that mapping and unlinks ONLY the verified
runner-local copy, after extraction succeeded and the fully populated RomFS.img
has been checked. CachyOS originals and cached entries are never touched.
"""
from pathlib import Path
import sys

ANCHOR = "    aoc = extract_aoc(nx, keys, repo, work, app, fam, logs)\n"
MARKER = "    # OOT2_RUNNER_NUP_RELEASE_V1\n"

# This code is inserted in nxnative's main(), immediately after the complete
# extract_aoc call. It uses nxnative's existing os, Path and BuildError imports.
INJECTION = '''    # OOT2_RUNNER_NUP_RELEASE_V1
    release = os.environ.get("OOT2_RELEASE_EPHEMERAL_NUP")
    if release:
        runner = Path(os.environ.get("RUNNER_TEMP", "")).resolve()
        expected = runner / "oot2-nup" / "OcarinaOfTime.nup"
        candidate = Path(release)
        valid = (
            runner.is_dir()
            and candidate.resolve() == expected
            and not candidate.is_symlink()
            and candidate.is_file()
            and nup is not None
            and Path(nup).resolve() == expected
            and platform == "ios"
            and app == 0x0400486024DEC000
            and pkg_ver == "v131072"
            and versions == [pkg_ver]
            and len(fam["updates"]) == 1
            and not fam["dlc"]
            and not g.get("programs", "")
            and os.environ.get("OOT2_RELEASE_EPHEMERAL_NUP_ID") == (
                f"{candidate.stat().st_size}:{fam['nup'].toc_sha.hex()}"
            )
            and (dirs[pkg_ver] / "RomFS.img").is_file()
            and not (dirs[pkg_ver] / "RomFS.img").is_symlink()
            and (dirs[pkg_ver] / "RomFS.img").stat().st_size > 0
        )
        if not valid:
            raise BuildError("OOT2 ephemeral NUP release safety conditions failed")
        free_before = shutil.disk_usage(work).free
        fam["nup"].close()  # releases the mmap, which otherwise pins the file
        candidate.unlink()  # runner-local copy only; NEVER CachyOS originals
        free_after = shutil.disk_usage(work).free
        say("OOT2 runner-only NUP released after full extraction: "
            f"disk recovered {(free_after - free_before) / 2**30:.1f} GiB")
'''


def patch(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink() or path.name != "build_ipa_from_nsp.py":
        raise ValueError("target")
    source = path.read_text(encoding="utf-8")
    if MARKER in source:
        raise ValueError("already_patched")
    if source.count(ANCHOR) != 1:
        raise ValueError("upstream_anchor")
    # Guard against changing another upstream API: the extraction and NUP
    # mmap close mechanism must exist in the pinned version.
    if ("def scan_nup(path, want=None):" not in source
        or "fam['nup']" not in source
        or "def extract_aoc(nx, keys, repo, work, app, fam, logs):" not in source
        or "def main(args=None):" not in source):
        raise ValueError("upstream_contract")
    modified = source.replace(ANCHOR, ANCHOR + INJECTION, 1)
    compile(modified, str(path), "exec")
    path.write_text(modified, encoding="utf-8")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: oot2_patch_nup_release.py PINNED_SCRIPT")
    patch(Path(sys.argv[1]))
    print("OOT2 upstream runner-only NUP release patch: applied, syntax checked.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, SyntaxError) as exc:
        print(f"OOT2 upstream patch: refused ({type(exc).__name__})", file=sys.stderr)
        raise SystemExit(1)
