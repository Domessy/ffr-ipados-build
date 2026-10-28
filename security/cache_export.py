#!/usr/bin/env python3
"""Stream only finished nxnative CAS files as a gzip tar, never game NSPs/keys.

Usage: cache_export.py ROOT [SINCE_NS] [BEFORE_NS]
SINCE_NS is an exclusive mtime cutoff. BEFORE_NS is an inclusive cutoff.
Each file remains under one of the fixed CAS namespaces.
"""
import os
import pathlib
import re
import stat
import sys
import tarfile
import time

ALLOWED = {"index", "shader", "variant", "metallib"}
SAFE = re.compile(r"[A-Za-z0-9_.-]{1,180}\Z")
MAX_FILE = 1 << 30


def valid(parts):
    return (2 <= len(parts) <= 7 and parts[0] in ALLOWED
            and all(p not in (".", "..") and SAFE.fullmatch(p) for p in parts))


def main():
    root = pathlib.Path(sys.argv[1]).resolve()
    since = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    before = int(sys.argv[3]) if len(sys.argv) > 3 else time.time_ns() - 10_000_000_000
    if not root.is_dir():
        raise SystemExit("CAS folder not ready")
    count = 0
    # Tar owns stdout. Never print anything on stdout.
    with tarfile.open(fileobj=sys.stdout.buffer, mode="w|gz", compresslevel=1) as archive:
        for prefix in sorted(ALLOWED):
            directory = root / prefix
            if not directory.is_dir():
                continue
            for folder, dirs, files in os.walk(directory, followlinks=False):
                dirs[:] = sorted(d for d in dirs if not os.path.islink(os.path.join(folder, d)))
                for name in sorted(files):
                    path = pathlib.Path(folder) / name
                    parts = path.relative_to(root).parts
                    if not valid(parts):
                        continue
                    try:
                        meta = path.lstat()
                    except FileNotFoundError:
                        continue
                    if not stat.S_ISREG(meta.st_mode) or meta.st_size > MAX_FILE:
                        continue
                    if not since < meta.st_mtime_ns <= before:
                        continue
                    try:
                        archive.add(str(path), arcname="/".join(parts), recursive=False)
                        count += 1
                    except FileNotFoundError:
                        pass
    print(f"FFR_CACHE_EXPORT_FILES={count}", file=sys.stderr)


if __name__ == "__main__":
    main()
