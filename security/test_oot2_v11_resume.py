"""A resume must match the actual snapshot, chain-specific indices and recipe."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from security import oot2_v11_resume as resume


class ResumeTests(unittest.TestCase):
    def test_snapshot_inventory_and_corruption_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'snapshot';p.write_bytes(b'cache')
            spec={'compressed_bytes':5,'sqlite_bytes':100,'entries':7,'sha256':hashlib.sha256(b'cache').hexdigest()}
            resume.verify_info('OOT2_METAL_SNAPSHOT_V1',5,100,7,spec)
            resume.verify_archive(p,spec)
            with self.assertRaises(ValueError):resume.verify_info('OOT2_METAL_SNAPSHOT_V1',5,100,6,spec)
            p.write_bytes(b'wrong')
            with self.assertRaises(ValueError):resume.verify_archive(p,spec)

    def test_old_fingerprint_or_incomplete_snapshot_cannot_be_used(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'cas.db'
            with sqlite3.connect(p) as db:
                db.execute('CREATE TABLE blob(id INTEGER PRIMARY KEY,data BLOB)')
                db.execute('CREATE TABLE entry(name TEXT,blob INTEGER)')
                db.execute('INSERT INTO blob VALUES(1,?)',(json.dumps({'code_fp':'current'}),))
                db.execute("INSERT INTO entry VALUES('index/key.json',1)")
            resume.verify_indices(p,{'code_fp':'current','indices':1})
            for spec in ({'code_fp':'old','indices':1},{'code_fp':'current','indices':2}):
                with self.assertRaises(ValueError):resume.verify_indices(p,spec)

    def test_v11_transfer_is_scoped_to_cache_and_gate_is_still_strict(self):
        from security import oot2_transfer as t,oot2_gateway as g
        self.assertEqual(t.ROUTES['resume-v11'],'oot2-read-resume-v11')
        self.assertEqual(t.DESTINATIONS['resume-v11'],('oot2-shader-cas','metal-snapshot.zst'))
        self.assertIn('oot2-resume-v11-info',g.ROUTES)
        self.assertIn('oot2-read-resume-v11',g.ROUTES)

    def test_workflow_restores_before_nup_and_never_initializes_empty_cas(self):
        p=Path(__file__).resolve().parents[1]/'.github/workflows/build-oot2-v11.yml'
        text=p.read_text()
        self.assertLess(text.index('oot2_v11_resume.py archive'),text.index('security/oot2_transfer.py nup'))
        self.assertIn('oot2_v11_resume.py indices',text)
        self.assertIn('post-cache extraction disk',text)
        self.assertNotIn('oot2_sqlite_cas.py prepare',text)
