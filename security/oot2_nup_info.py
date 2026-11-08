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
        magic, hsize, _reserved, toc_off, toc_size, digest, blob, declared, count, flags, _, trailer = SUPER.unpack(h)
        if magic != b"NUP\x01" or flags or declared != size:
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
    if len(bases) > 1:
        raise NupInvalid("base")
    if bases:
        # Some producers label the base record with its dump's version
        # (our verified replacement uses 65536). Upstream scan() identifies
        # the base by kind, not this label; the selected update remains exact.
        if bases[0][0] != TITLE:
            raise NupInvalid("title_id")
    else:
        # nxnative accepts a NUP without a base when every update is
        # marked standalone_update. This flag does not prove completeness.
        if not updates or any(not (rec[6] & 1) or rec[6] & ~1 for rec in updates):
            raise NupInvalid("standalone")
        selected = [rec for rec in updates if rec[4] == VERSION]
        if selected and (selected[0][0] != TITLE
                         or any(selected[0][i] >= num_dirs for i in (1, 2, 3))):
            # The chosen update must reference a root, ExeFS and RomFS tree.
            # The upstream parser still validates actual file contents.
            raise NupInvalid("standalone")
    if any(rec[5] not in (0, 1, 2, 3, 4) for rec in packages):
        raise NupInvalid("role")
    if not any(rec[4] == VERSION for rec in updates):
        raise NupInvalid("version")
    if len({rec[4] for rec in updates}) != len(updates):
        raise NupInvalid("version")
    # Header and TOC validation is NOT payload verification or proof of game
    # completeness; nxnative's NUP parser checks this after private transfer.
    return size, len(bases), sum(rec[4] == VERSION for rec in updates), count



def release_identity(path):
    """Bind runner-copy cleanup to verified metadata, before any transfer.

    Both standalone updates and base+update containers are supported. Extra
    packages/versions are refused because cleanup only follows one extraction.
    """
    size, bases, updates, packages = inspect(path)
    if updates != 1 or packages != bases + 1 or selected_romfs_bytes(path) <= 0:
        raise NupInvalid("release_layout")
    with Path(path).open("rb") as stream:
        digest = SUPER.unpack(stream.read(SUPER.size))[5].hex()
    return f"{size}:{digest}"


def selected_romfs_bytes(path):
    """Read-only sum of the selected update's RomFS file sizes from the NUP TOC.

    This is the unpacked file payload estimate, not an exact RomFS.img or IPA
    size. nxnative still performs all payload checks on the private runner.
    """
    inspect(path)  # Verify signature, TOC digest, title and selected version.
    with Path(path).open("rb") as src:
        h = SUPER.unpack(src.read(SUPER.size))
        src.seek(h[3])
        toc = src.read(h[4])
    _magic, count, dirs, files, pool, _pool_size, _ = TOC.unpack_from(toc)
    p_off = TOC.size
    d_off = p_off + count * PKG.size
    f_off = d_off + dirs * DIR.size
    slot_off = f_off + files * FILE.size
    if pool < slot_off or (pool - slot_off) % 4:
        raise NupInvalid("toc")
    slot_count = (pool - slot_off) // 4
    packages = [PKG.unpack_from(toc, p_off + i * PKG.size)
                for i in range(count)]
    patches = [p for p in packages if p[5] == 1 and p[4] == VERSION]
    if len(patches) != 1:
        raise NupInvalid("version")
    root = patches[0][3]  # The selected update's RomFS directory.
    if root == 0xFFFFFFFF:
        bases = [p for p in packages if p[5] == 0]
        root = bases[0][3] if len(bases) == 1 else 0xFFFFFFFF
    if root >= dirs:
        raise NupInvalid("romfs")
    seen = set()
    stack = [root]
    total = 0
    while stack:
        index = stack.pop()
        if index in seen or index >= dirs:
            raise NupInvalid("tree")
        seen.add(index)
        _name, _size, first, number, _extra = DIR.unpack_from(
            toc, d_off + index * DIR.size)
        if first + number > slot_count:
            raise NupInvalid("tree")
        for slot_index in range(first, first + number):
            child = struct.unpack_from("<I", toc, slot_off + slot_index * 4)[0]
            if child < dirs:
                stack.append(child)
            else:
                file_index = child - dirs
                if file_index >= files:
                    raise NupInvalid("tree")
                record = FILE.unpack_from(toc, f_off + file_index * FILE.size)
                total += record[2]
                # Bound untrusted TOC quantities before GitHub shell arithmetic.
                if total > 512 * 1024**3:
                    raise NupInvalid("romfs_size")
    return total


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
