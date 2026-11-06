#!/usr/bin/env python3
"""Bounded, read-only, stdlib preflight for a Switch 2 NUP v1.

This checks container metadata and its TOC digest WITHOUT decompressing the
retail payload. nxnative verifies each payload SHA256 when unpacking on the
private Mac runner. Never print private filenames, package content or keys.
"""
import hashlib
import os
from pathlib import Path
import stat
import struct

TITLE = 0x0400486024DEC000
VERSION = 131072
SUPER = struct.Struct("<4sHHQQ32sQQII16s32s")
TOC = struct.Struct("<4sIQQQQQ")
PKG = struct.Struct("<QIIIIBBHIQI20x")
DIR = struct.Struct("<IIIIQ")
FILE = struct.Struct("<IIQQQ32sBBH12x")
MIN_BYTES = 128 * 1024**2
MAX_BYTES = 80 * 1024**3
MAX_TOC = 512 * 1024**2
MAX_PACKAGES = 256
MAX_FILES = 1_000_000


class NupInvalid(ValueError):
    """A fixed code from local metadata validation; no sensitive paths."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def inspect(path):
    """Returns (size, base_count, selected_update_count, package_count)."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise NupInvalid("file_type")
    with path.open("rb") as src:
        meta = os.fstat(src.fileno())
        size = meta.st_size
        if not stat.S_ISREG(meta.st_mode):
            raise NupInvalid("file_type")
        if not MIN_BYTES < size <= MAX_BYTES:
            raise NupInvalid("size")
        h = src.read(SUPER.size)
        if len(h) != SUPER.size:
            raise NupInvalid("header")
        magic, hsize, reserved, toc_off, toc_size, digest, blob, declared, count, flags, _, trailer = SUPER.unpack(h)
        if magic != b"NUP\x01" or reserved or flags or declared != size:
            raise NupInvalid("header")
        if hsize < SUPER.size or toc_off != hsize or not 0 < toc_size <= MAX_TOC:
            raise NupInvalid("toc")
        if blob < toc_off + toc_size or blob % 16 or blob > size:
            raise NupInvalid("toc")
        if not 1 <= count <= MAX_PACKAGES:
            raise NupInvalid("count")
        src.seek(toc_off)
        toc = src.read(toc_size)
        if len(toc) != toc_size or hashlib.sha256(toc).digest() != digest:
            raise NupInvalid("toc")
    if len(toc) < TOC.size:
        raise NupInvalid("toc")
    tmagic, num_pkg, num_dirs, num_files, pool_offset, pool_size, _ = TOC.unpack_from(toc)
    needed = TOC.size + count * PKG.size + num_dirs * DIR.size + num_files * FILE.size
    if (tmagic != b"TOC\x01" or num_pkg != count or num_files > MAX_FILES
            or needed > len(toc) or pool_offset < needed
            or pool_offset + pool_size > len(toc)):
        raise NupInvalid("toc")
    packages = [PKG.unpack_from(toc, TOC.size + i * PKG.size) for i in range(count)]
    bases = [rec for rec in packages if rec[5] == 0]
    updates = [rec for rec in packages if rec[5] == 1]
    if len(bases) != 1:
        raise NupInvalid("base")
    if bases[0][0] != TITLE or bases[0][4] != 0:
        raise NupInvalid("title_id")
    if any(rec[5] not in (0, 1, 2, 3, 4) for rec in packages):
        raise NupInvalid("role")
    if not any(rec[4] == VERSION for rec in updates):
        raise NupInvalid("version")
    if len({rec[4] for rec in updates}) != len(updates):
        raise NupInvalid("version")
    # Header and TOC validation is NOT payload verification or proof of game
    # completeness; nxnative's NUP parser checks this after private transfer.
    return size, len(bases), sum(rec[4] == VERSION for rec in updates), count


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    args = parser.parse_args()
    try:
        size, base, selected, count = inspect(args.path)
    except (NupInvalid, OSError) as exc:
        reason = exc.reason if isinstance(exc, NupInvalid) else "source"
        print(f"OOT2_NUP_V1 status=fail reason={reason}")
        raise SystemExit(1)
    print(f"OOT2_NUP_V1 status=ok base={base} update_v131072={selected} packages={count} bytes={size}")


if __name__ == "__main__":
    main()
