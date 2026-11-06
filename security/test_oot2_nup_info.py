#!/usr/bin/env python3
"""NUP v1 metadata regression fixtures with sparse dummy files, no game data."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from security import oot2_nup_info as n

SIZE = 200 * 1024**2
TITLE = n.TITLE


def fake_nup(path, *, version=n.VERSION, base=True, title=TITLE,
             broken_toc=False, standalone=False, reserved=0,
             update_romfs=None):
    """A synthetic metadata-only NUP, never a valid game image."""
    recs = []
    if base:
        recs.append(n.PKG.pack(title, 0, n.NO_DIR if hasattr(n, "NO_DIR") else 0xFFFFFFFF,
                               0xFFFFFFFF, 0, 0, 0, 0, 0, 0, 0))
    ndirs = 3 if standalone else 1
    exefs = 1 if standalone else 0xFFFFFFFF
    romfs = (2 if standalone else 0xFFFFFFFF) if update_romfs is None else update_romfs
    recs.append(n.PKG.pack(title, 0, exefs, romfs,
                           version, 1, int(standalone), 0, 0, 0, 0))
    count = len(recs)
    pool_at = n.TOC.size + count * n.PKG.size + ndirs * n.DIR.size
    toc = (n.TOC.pack(b"TOC\x01", count, ndirs, 0, pool_at, 0, 0)
           + b"".join(recs) + n.DIR.pack(0, 0, 0, 0, 0) * ndirs)
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

    def test_space_estimate_from_selected_romfs(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "standalone.nup"
            fake_nup(p, base=False, standalone=True, reserved=1)
            self.assertEqual(n.selected_romfs_bytes(p), 0)
            fake_nup(p, base=False, standalone=True, reserved=1,
                     update_romfs=0xFFFFFFFF)
            with self.assertRaisesRegex(n.NupInvalid, "romfs"):
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
