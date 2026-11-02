#!/usr/bin/env python3
"""Inspect encrypted NSP CNMT locally on the ephemeral Mac and name update correctly.

This is required for titles without an nxnative profile: a versionless update
file is silently omitted by nsp_versions() when no build is registered.
Nothing modifies the original CachyOS NSPs, and no private metadata is logged
to public GitHub Actions beyond an integer version.
"""
import os
from pathlib import Path
import re
import subprocess
import sys

TITLE = "0100DCD01F306000"
UPDATE = "0100DCD01F306800"
CONTENT = re.compile(r"^content (Application|Patch|AddOnContent) ([0-9A-Fa-f]{16}) (\d+)$", re.M)


def meta_rows(stdout):
    return [(kind, title.upper(), int(version))
            for kind, title, version in CONTENT.findall(stdout)]


def validate_metadata(base_stdout, update_stdout):
    base = meta_rows(base_stdout)
    patch = meta_rows(update_stdout)
    if base != [("Application", TITLE, 0)]:
        raise ValueError("base NSP CNMT does not match the expected application")
    if len(patch) != 1 or patch[0][:2] != ("Patch", UPDATE):
        raise ValueError("update NSP CNMT does not match the expected patch title")
    version = patch[0][2]
    if not 0 < version <= 0x7FFFFFFF:
        raise ValueError("invalid update version from encrypted CNMT")
    return version


def main():
    temp = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    folder = temp / "mina-nsp"
    keys = temp / "mina-prod.keys"
    base = folder / f"Mina the Hollower [{TITLE}][v0].nsp"
    update = folder / f"Mina the Hollower update [{UPDATE}].nsp"
    upstream = temp / "nxnative" / "dm" / "tools" / "nx_extract"
    output = temp / "mina-nsp-inspection"
    output.mkdir(mode=0o700, exist_ok=True)
    for path in (base, update, keys):
        if not path.is_file() or path.is_symlink():
            raise ValueError("source or key not a regular file in the dedicated runner folder")
    if not (upstream / "nx_extract.csproj").is_file():
        raise ValueError("pinned extractor project is missing")

    # Build the exact nx_extract used by the pinned nxnative commit.
    built = subprocess.run(["dotnet", "build", str(upstream), "-c", "Release",
                            "-o", str(output), "-v", "quiet", "-nologo"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, timeout=300, check=False)
    exe = output / "nx_extract"
    if built.returncode or not exe.is_file():
        raise RuntimeError("private package inspector compilation failed")

    def inspect(path):
        result = subprocess.run([str(exe), str(keys), "--contents", str(path)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, timeout=180, check=False)
        if result.returncode:
            raise RuntimeError("private NSP CNMT inspection failed")
        return result.stdout

    version = validate_metadata(inspect(base), inspect(update))
    renamed = folder / f"Mina the Hollower update [{UPDATE}][v{version}].nsp"
    if renamed.exists():
        raise ValueError("refusing to overwrite existing runner NSP")
    update.rename(renamed)
    print(f"MINA: base title and update CNMT verified; update v{version}.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"MINA: encrypted package identification failed ({type(error).__name__}); no game data disclosed.", flush=True)
        raise SystemExit(1)
