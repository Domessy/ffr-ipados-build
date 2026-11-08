"""Synthetic cache transfer tests: exact bytes, dedup, corruption and bounds."""
from pathlib import Path
from contextlib import closing
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from security import oot2_cache_snapshot as snap
from security import oot2_gateway as gw
from security import ffr_ssh_gate as gate


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        # macOS tempfile may spell /private/var as /var. Resolve this trusted
        # fixture root; the exporter must still reject cache-owned symlinks.
        self.root = Path(t.name).resolve()
        self.cache = self.root / 'cache'
        self.out = self.root / 'transfer'
        for n, data in {'metallib/ios/a.metallib': b'compiled bytes',
                        'metallib/ios/b.metallib': b'compiled bytes',
                        'shader/old/ios/a.metal': b'old chain translation',
                        'index/a.json': b'old index'}.items():
            p = self.cache / n
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)

    def create(self):
        # Test the database independent of an installed compressor. The real
        # zstd transfer is checked separately below and on CachyOS before use.
        def compression(argv, **_):
            shutil.copyfile(argv[4], argv[6])
        with patch.object(snap.subprocess, 'run', side_effect=compression):
            return snap.snapshot(self.cache, self.out)

    def restore(self, archive):
        runner = self.root / 'runner'
        runner.mkdir()
        shutil.copyfile(archive, runner / 'cas.db.partial')
        return runner

    def test_compiled_only_snapshot_deduplicates_and_preserves_exact_bytes(self):
        archive, meta = self.create()
        self.assertEqual((meta['entries'], meta['blobs']), (2, 1))
        runner = self.restore(archive)
        snap.accept(runner)
        with closing(sqlite3.connect(runner / 'cas.db')) as db:
            rows = db.execute('SELECT e.name,b.data FROM entry e JOIN blob b ON b.id=e.blob ORDER BY e.name').fetchall()
        self.assertEqual(rows, [('metallib/ios/a.metallib', b'compiled bytes'),
                                ('metallib/ios/b.metallib', b'compiled bytes')])
        self.assertTrue((self.cache / 'shader/old/ios/a.metal').exists())

    def test_reuse_then_new_immutable_entry_rebuilds_snapshot(self):
        archive, meta = self.create()
        original = archive.stat().st_mtime_ns
        with patch.object(snap.subprocess, 'run', side_effect=AssertionError('must reuse')):
            _, same = snap.snapshot(self.cache, self.out)
        self.assertEqual(meta, same)
        self.assertEqual(original, archive.stat().st_mtime_ns)
        (self.cache / 'metallib/ios/c.metallib').write_bytes(b'new compile')
        _, new = self.create()
        self.assertEqual(new['entries'], 3)
        self.assertNotEqual(new['fingerprint'], meta['fingerprint'])

    def test_symlinks_cannot_export_private_files(self):
        secret = self.root / 'not-cache'
        secret.write_bytes(b'synthetic secret')
        (self.cache / 'metallib/ios/link.metallib').symlink_to(secret)
        _, meta = self.create()
        self.assertEqual(meta['entries'], 2)
        redirected = self.root / 'redirected'
        redirected.symlink_to(self.cache, target_is_directory=True)
        with self.assertRaises(ValueError):
            snap.snapshot(redirected, self.out)

    def test_corrupt_blob_never_publishes_database(self):
        archive, _ = self.create()
        runner = self.restore(archive)
        with closing(sqlite3.connect(runner / 'cas.db.partial')) as db:
            db.execute('UPDATE blob SET data=?', (b'damaged',))
            db.commit()
        with self.assertRaisesRegex(ValueError, 'checksum'):
            snap.accept(runner)
        self.assertFalse((runner / 'cas.db').exists())

    def test_truncated_sqlite_is_rejected(self):
        archive, _ = self.create()
        runner = self.restore(archive)
        (runner / 'cas.db.partial').write_bytes(b'SQLite format 3\0')
        with self.assertRaises((ValueError, sqlite3.DatabaseError)):
            snap.accept(runner)
        self.assertFalse((runner / 'cas.db').exists())

    def test_existing_database_is_never_overwritten(self):
        archive, _ = self.create()
        runner = self.restore(archive)
        (runner / 'cas.db').write_bytes(b'existing')
        with self.assertRaises(ValueError):
            snap.accept(runner)
        self.assertEqual((runner / 'cas.db').read_bytes(), b'existing')

    def test_unexpected_namespace_or_view_is_rejected(self):
        archive, _ = self.create()
        runner = self.restore(archive)
        with closing(sqlite3.connect(runner / 'cas.db.partial')) as db:
            db.execute("UPDATE entry SET name='shader/not-allowed' WHERE name LIKE '%/a.metallib'")
            db.commit()
        with self.assertRaisesRegex(ValueError, 'entry'):
            snap.accept(runner)
        with closing(sqlite3.connect(runner / 'cas.db.partial')) as db:
            db.execute('CREATE VIEW unexpected AS SELECT * FROM blob')
            db.commit()
        with self.assertRaisesRegex(ValueError, 'schema'):
            snap.accept(runner)
        self.assertFalse((runner / 'cas.db').exists())

    def test_snapshot_bounds_and_fixed_route(self):
        with patch.object(snap, 'MAX_FILE', 2):
            with self.assertRaises(ValueError):
                self.create()
        archive = self.root / 'fixture.zst'
        archive.write_bytes(b'synthetic')
        with patch.object(gw, 'CACHE', self.cache), patch.object(gw, 'ROOT', self.root), \
             patch.object(snap, 'snapshot', return_value=(archive, {})) as build, \
             patch.object(gate, 'send_file') as send:
            self.assertEqual(gw.dispatch('oot2-read-metal-snapshot-v1', gate), 0)
            build.assert_called_once_with(self.cache, self.root / 'cache-transfer')
            send.assert_called_once_with(archive)
            self.assertEqual(gw.dispatch('oot2-read-metal-snapshot-v1 /etc/passwd', gate), 126)

    @unittest.skipUnless(shutil.which('zstd'), 'zstd unavailable; synthetic database tests still run')
    def test_real_zstd_roundtrip(self):
        archive, _ = snap.snapshot(self.cache, self.out)
        runner = self.root / 'zstd-runner'
        runner.mkdir()
        with (runner / 'cas.db.partial').open('wb') as f:
            subprocess.run(['zstd', '-q', '-d', '-c', str(archive)], stdout=f, check=True)
        snap.accept(runner)
        self.assertTrue((runner / 'cas.db').is_file())
