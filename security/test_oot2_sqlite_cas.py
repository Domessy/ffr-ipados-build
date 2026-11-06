#!/usr/bin/env python3
"""Synthetic regression tests for the SQLite <-> restricted SSH CAS bridge."""
import contextlib
import hashlib
import io
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest

from security import oot2_sqlite_cas as cas

SCRIPT = Path(cas.__file__).resolve()


def add(db_path, name, data, mtime):
    with sqlite3.connect(db_path) as db:
        digest = hashlib.blake2b(data, digest_size=16).digest()
        db.execute("INSERT OR IGNORE INTO blob(hash,data) VALUES(?,?)",
                   (digest, data))
        key = db.execute("SELECT id FROM blob WHERE hash=?",
                         (digest,)).fetchone()[0]
        db.execute("INSERT OR REPLACE INTO entry(name,blob,mtime) VALUES(?,?,?)",
                   (name, key, mtime))


def archive(root, since, before):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "export", str(root),
         str(since), str(before)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=40)
    return proc


class SQLiteCasTests(unittest.TestCase):
    def test_prepare_uses_one_sqlite_file_not_directory(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                cas.prepare(root)
            self.assertIn("OOT2_SQLITE_CAS_READY", out.getvalue())
            self.assertTrue((root / "cas.db").is_file())
            with sqlite3.connect(root / "cas.db") as db:
                self.assertEqual(db.execute("PRAGMA quick_check").fetchone()[0],
                                 "ok")
                self.assertEqual(db.execute("SELECT count(*) FROM entry").
                                 fetchone()[0], 0)

    def test_reject_directory_instead_of_database(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "cas.db").mkdir()
            with self.assertRaisesRegex(ValueError, "cache_file"):
                cas.prepare(root)

    def test_flat_cache_import_and_incremental_live_wal_export(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            key = "shader/" + "a" * 64 + "/ios/output.metallib"
            file = root / key
            file.parent.mkdir(parents=True)
            file.write_bytes(b"synthetic compiled shader")
            old = time.time() - 120
            os.utime(file, (old, old))
            with contextlib.redirect_stdout(io.StringIO()):
                cas.prepare(root)
            self.assertFalse((root / "shader").exists())
            with sqlite3.connect(root / "cas.db") as db:
                self.assertEqual(db.execute("SELECT count(*) FROM entry").
                                 fetchone()[0], 1)
            # The old restored entry must not be needlessly uploaded again.
            cutoff = time.time_ns() - 30 * 10**9
            start = archive(root, cutoff, time.time_ns())
            self.assertEqual(start.returncode, 0, start.stderr)
            with tarfile.open(fileobj=io.BytesIO(start.stdout), mode="r:gz") as tar:
                self.assertEqual(tar.getnames(), [])
            # A new committed entry, even in a database with WAL, is exported.
            fresh = "index/test-key.json"
            add(root / "cas.db", fresh, b'{"test":true}', time.time() - 4)
            output = archive(root, cutoff, time.time_ns())
            self.assertEqual(output.returncode, 0, output.stderr)
            with tarfile.open(fileobj=io.BytesIO(output.stdout), mode="r:gz") as tar:
                self.assertEqual(tar.getnames(), [fresh])
                self.assertEqual(tar.extractfile(fresh).read(), b'{"test":true}')

    def test_sqlite_tar_roundtrip_preserves_binary_cache_entries(self):
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            first, second = Path(one), Path(two)
            with contextlib.redirect_stdout(io.StringIO()):
                cas.prepare(first)
            data = b"\x00\xff\x01synthetic shader\x00"
            key = "metallib/ios/" + "f" * 64 + ".metallib"
            add(first / "cas.db", key, data, time.time() - 5)
            output = archive(first, 0, time.time_ns())
            self.assertEqual(output.returncode, 0, output.stderr)
            with tarfile.open(fileobj=io.BytesIO(output.stdout), mode="r:gz") as tar:
                for entry in tar:
                    self.assertTrue(cas.valid(entry.name))
                    dest = second / entry.name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(tar.extractfile(entry).read())
            with contextlib.redirect_stdout(io.StringIO()):
                cas.prepare(second)
            with sqlite3.connect(second / "cas.db") as db:
                row = db.execute(
                    "SELECT b.data FROM entry e JOIN blob b ON b.id=e.blob "
                    "WHERE e.name=?", (key,)).fetchone()
                self.assertEqual(row[0], data)

    def test_invalid_cache_path_is_not_exported(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with contextlib.redirect_stdout(io.StringIO()):
                cas.prepare(root)
            add(root / "cas.db", "../bad-entry", b"fake", time.time() - 3)
            output = archive(root, 0, time.time_ns())
            self.assertNotEqual(output.returncode, 0)
            self.assertIn(b"OOT2_SQLITE_CAS status=fail", output.stderr)
            self.assertNotIn(b"bad-entry", output.stderr)


if __name__ == "__main__":
    unittest.main()
