#!/usr/bin/env python3
"""NUP v1 metadata regression fixtures with sparse dummy files, no game data."""
import hashlib
import struct
from pathlib import Path
import tempfile
import unittest
from security import oot2_nup_info as n

SIZE = 200 * 1024**2
TITLE = n.TITLE


def fake_nup(path, *, version=n.VERSION, base=True, title=TITLE,
             broken_toc=False, standalone=False, reserved=0,
             update_romfs=None, romfs_file_bytes=0, base_version=0):
    """A synthetic metadata-only NUP, never a valid game image."""
    recs = []
    if base:
        recs.append(n.PKG.pack(title, 0, n.NO_DIR if hasattr(n, "NO_DIR") else 0xFFFFFFFF,
                               0xFFFFFFFF, base_version, 0, 0, 0, 0, 0, 0))
    ndirs = 3 if standalone else 1
    exefs = 1 if standalone else 0xFFFFFFFF
    romfs = (2 if standalone else 0xFFFFFFFF) if update_romfs is None else update_romfs
    recs.append(n.PKG.pack(title, 0, exefs, romfs,
                           version, 1, int(standalone), 0, 0, 0, 0))
    count = len(recs)
    file_count = int(bool(romfs_file_bytes))
    if romfs_file_bytes and not standalone:
        raise ValueError("synthetic RomFS file requires standalone layout")
    directories = [n.DIR.pack(0, 0, 0, 0, 0) for _ in range(ndirs)]
    slots = b""
    file_records = b""
    if file_count:
        # Slot index points to the first file (after the directory indices).
        directories[2] = n.DIR.pack(0, 0, 0, 1, 0)
        slots = struct.pack("<I", ndirs)
        file_records = n.FILE.pack(0, 0, romfs_file_bytes, 0, 0,
                                  b"\x00" * 32, 0, 0, 0)
    pool_at = (n.TOC.size + count * n.PKG.size + ndirs * n.DIR.size
               + len(file_records) + len(slots))
    toc = (n.TOC.pack(b"TOC\x01", count, ndirs, file_count, pool_at, 0, 0)
           + b"".join(recs) + b"".join(directories) + file_records + slots)
    dig = hashlib.sha256(toc).digest() if not broken_toc else b"x" * 32
    blob = (n.SUPER.size + len(toc) + 15) & ~15
    header = n.SUPER.pack(
        b"NUP\x01", n.SUPER.size, reserved, n.SUPER.size, len(toc),
        dig, blob, SIZE, count, 0, b"\x00" * 16, b"\x00" * 32)
    with Path(path).open("wb") as stream:
        stream.write(header)
        stream.write(toc)
        stream.truncate(SIZE)


class NupInfoTests(unittest.TestCase):
    def test_metadata_valid_for_base_plus_registered_patch(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "anything.nup"
            fake_nup(p)
            self.assertEqual(n.inspect(p), (SIZE, 1, 1, 2))

    def test_real_world_standalone_update_with_reserved_one(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "standalone.nup"
            fake_nup(p, base=False, standalone=True, reserved=1)
            self.assertEqual(n.inspect(p), (SIZE, 0, 1, 1))

    def test_base_version_label_does_not_override_selected_update(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "replacement.nup"
            fake_nup(p, base_version=65536)
            self.assertEqual(n.inspect(p), (SIZE, 1, 1, 2))
            fake_nup(p, base_version=65536, version=196608)
            with self.assertRaisesRegex(n.NupInvalid, "version"):
                n.inspect(p)

    def test_space_estimate_from_selected_romfs(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "standalone.nup"
            fake_nup(p, base=False, standalone=True, reserved=1,
                     romfs_file_bytes=25000000)
            self.assertEqual(n.selected_romfs_bytes(p), 25000000)
            fake_nup(p, base=False, standalone=True, reserved=1,
                     update_romfs=0xFFFFFFFF)
            with self.assertRaisesRegex(n.NupInvalid, "standalone"):
                n.selected_romfs_bytes(p)

    def test_standalone_without_complete_metadata_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "standalone.nup"
            fake_nup(p, base=False, standalone=True, update_romfs=0xFFFFFFFF)
            with self.assertRaisesRegex(n.NupInvalid, "standalone"):
                n.inspect(p)
            fake_nup(p, base=False, standalone=False)
            with self.assertRaisesRegex(n.NupInvalid, "standalone"):
                n.inspect(p)

    def test_bad_title_or_update_version_rejected_without_data_reads(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "test.nup"
            for bad in (
                dict(title=0x0400486024DED000),
                dict(version=196608),
                dict(version=0),
                dict(base=False),
                dict(broken_toc=True),
            ):
                fake_nup(p, **bad)
                with self.assertRaises(n.NupInvalid):
                    n.inspect(p)

    def test_header_mismatch_and_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "test.nup"
            fake_nup(p)
            alias = Path(d) / "alias.nup"
            alias.symlink_to(p)
            with self.assertRaisesRegex(n.NupInvalid, "file_type"):
                n.inspect(alias)
            with p.open("r+b") as stream:
                stream.write(b"FAIL")
            with self.assertRaisesRegex(n.NupInvalid, "header"):
                n.inspect(p)

    def test_directory_and_small_files_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(n.NupInvalid):
                n.inspect(d)
            p = Path(d) / "short.nup"
            p.write_bytes(b"NUP\x01")
            with self.assertRaisesRegex(n.NupInvalid, "size"):
                n.inspect(p)


if __name__ == "__main__":
    unittest.main()
