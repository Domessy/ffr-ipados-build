"""Resume requires a durable correct-chain cache; a real failure never finishes."""
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from security import oot2_v13_restore as r,oot2_v13_gateway as g,oot2_gateway as top


class V13RestoreTests(unittest.TestCase):
    def test_only_correct_chain_and_bounded_inventory_are_accepted(self):
        self.assertIsNone(r.parse_info('OOT2_V13_CACHE_EMPTY'))
        valid=f'OOT2_V13_CACHE_V1 100 200 5 {r.CHAIN} '+ 'a'*64
        self.assertEqual(r.parse_info(valid)['entries'],5)
        for text in (valid.replace(r.CHAIN,'03a3ac831bfb'),valid.replace('100 200','0 200'),valid+' x',valid.replace('100 200',f'100 {121<<30}')):
            with self.assertRaises(ValueError):r.parse_info(text)

    def test_pause_is_exposed_only_after_durable_receipt_and_only_once(self):
        for rc,allow,receipt,state in [(0,'1',None,'ready'),(75,'1',{'entries':5},'paused'),(75,'1',None,None),(75,'0',{'entries':5},None),(1,'1',{'entries':5},None)]:
            with tempfile.TemporaryDirectory() as d:
                output=Path(d)/'outputs'
                with patch.dict(os.environ,{'GITHUB_OUTPUT':str(output),'OOT2_ALLOW_PAUSE':allow}),patch.object(r.subprocess,'call',return_value=rc),patch.object(r,'remote_info',return_value=receipt):
                    if state:
                        r.job();self.assertEqual(output.read_text(),'state='+state+'\n')
                    else:
                        with self.assertRaises((ValueError,SystemExit)):r.job()
                        self.assertFalse(output.exists())

    def test_current_chain_and_complete_outputs_are_required(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'cas.db';key='a'*16;digest='b'*64
            rows={'index/'+key+'.json':json.dumps({'digest':digest,'code_fp':'c'*64,'rule_fp':'d'*64}).encode()}
            for suffix in ('mac/'+key+'_b.json','mac/'+key+'_b.metal','ios/'+key+'_b.json','ios/'+key+'_b.metallib'):
                rows['shader/'+digest+'/'+suffix]=json.dumps({'chain':r.CHAIN}).encode() if suffix.endswith('.json') else b'payload'
            with sqlite3.connect(p) as db:
                db.execute('CREATE TABLE blob(id INTEGER PRIMARY KEY,data BLOB)');db.execute('CREATE TABLE entry(name TEXT PRIMARY KEY,blob INTEGER)')
                for i,(name,data) in enumerate(rows.items()):db.execute('INSERT INTO blob VALUES(?,?)',(i,data));db.execute('INSERT INTO entry VALUES(?,?)',(name,i))
            self.assertEqual(r.verify_indices(p),1)
            with sqlite3.connect(p) as db:
                db.execute("UPDATE blob SET data=? WHERE id=(SELECT blob FROM entry WHERE name=?)",(json.dumps({'chain':'03a3ac831bfb'}).encode(),'shader/'+digest+'/ios/'+key+'_b.json'))
            with self.assertRaisesRegex(ValueError,'chain'):r.verify_indices(p)
            with sqlite3.connect(p) as db:
                db.execute('DELETE FROM entry WHERE name=?',('shader/'+digest+'/mac/'+key+'_b.metal',))
            with self.assertRaisesRegex(ValueError,'incomplete'):r.verify_indices(p)

    def test_top_gateway_cache_is_separate_and_parent_state_is_restored(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();old=root/'shader-cache-v12';old.mkdir();(old/'preserve').write_bytes(b'v11')
            output=root/'resultats';output.mkdir()
            parent=SimpleNamespace(CACHE=old,CONFLICTS=root/'old-conflicts',OUTPUT=output)
            def receive():
                self.assertEqual(parent.CACHE,root/'shader-cache-v13')
                self.assertEqual(parent.CONFLICTS,root/'shader-cache-conflicts-v13')
                (parent.CACHE/'index').mkdir(parents=True);(parent.CACHE/'index/a.json').write_bytes(b'index')
            parent.receive_cache=receive
            with patch.object(top,'ROOT',root),patch.object(top,'OUTPUT',output):
                with redirect_stdout(io.StringIO()) as text:self.assertEqual(top.dispatch('oot2-cache-v13-info',parent),0)
                self.assertEqual(text.getvalue().strip(),'OOT2_V13_CACHE_EMPTY')
                self.assertEqual(top.dispatch('oot2-write-cache-v13',parent),0)
            self.assertEqual(parent.CACHE,old);self.assertEqual((old/'preserve').read_bytes(),b'v11')
            archive=root/'archive';archive.write_bytes(b'exact cache')
            with patch('security.oot2_cache_snapshot.snapshot',return_value=(archive,{'sqlite_bytes':200,'entries':5})) as snap:
                with redirect_stdout(io.StringIO()) as text:g.dispatch('oot2-cache-v13-info',parent,root,output,None)
                self.assertEqual(r.parse_info(text.getvalue())['sha256'],hashlib.sha256(archive.read_bytes()).hexdigest())
                snap.assert_called_once_with(root/'shader-cache-v13',root/'cache-transfer-v13',translations=True)

    @unittest.skipUnless(importlib.util.find_spec('yaml'), 'DAG check runs in the public venv with PyYAML')
    def test_workflow_only_continues_from_the_correct_job_outputs(self):
        import yaml
        root=Path(__file__).resolve().parents[1];p=root/'.github/workflows/build-oot2-v13.yml'
        text=p.read_text();jobs=yaml.safe_load(text)['jobs']
        self.assertEqual(jobs['resume']['needs'],['build'])
        self.assertIn("needs.build.outputs.state == 'paused'",jobs['resume']['if'])
        self.assertEqual(jobs['finish']['needs'],['build','resume'])
        self.assertIn("needs.resume.outputs.state == 'ready'",jobs['finish']['if'])
        self.assertIn("needs.build.outputs.state == 'ready'",jobs['finish']['if'])
        for name,allow in [('build','1'),('resume','0')]:
            steps=jobs[name]['steps'];compile_step=next(s for s in steps if s.get('id')=='compile')
            self.assertEqual(compile_step['env']['OOT2_ALLOW_PAUSE'],allow)
            checkpoint=next(s for s in steps if s['name']=='Save exact v13 compiled checkpoint and require receipt')
            self.assertEqual(checkpoint['if'],"steps.compile.outputs.state == 'ready'")
            restores=[i for i,s in enumerate(steps) if 'oot2_v13_restore.py restore' in s.get('run','')]
            nup=[i for i,s in enumerate(steps) if 'security/oot2_transfer.py nup' in s.get('run','')]
            self.assertLess(restores[0],nup[0])
