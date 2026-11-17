"""Recovery must retain exact shader identities and never publish a partial IPA."""
import hashlib
import json
from pathlib import Path
import plistlib
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile
from security import oot2_gateway as gateway, oot2_v9_gateway as v9
from security.oot2_ipad_aot import TABLES
from security.oot2_resume_cache import stage

class RecoveryTests(unittest.TestCase):
    def checkpoint(self, root, chain=v9.CHAIN, host=bytes.fromhex('cffaedfe0c000001')+b'fixture'):
        ipa=root/'synthetic.ipa';pre='Payload/Game.app/'
        with zipfile.ZipFile(ipa,'w') as z:
            z.writestr(pre+'Info.plist',plistlib.dumps({'CFBundleIdentifier':'org.nxnative.0400486024dec000','CFBundleExecutable':'Game'}))
            z.writestr(pre+'Game',host);z.writestr(pre+f'msl/b-{chain}.img',b'synthetic library')
            for table in TABLES:z.writestr(pre+'dm/'+table,b'fixture')
        return ipa
    def receive(self,root,source):
        out=root/'out';out.mkdir()
        parent=SimpleNamespace(OUTPUT=out)
        parent.receive_file=lambda name,limit:shutil.copyfile(source,parent.OUTPUT/name)
        return parent,out
    def test_checkpoint_works_through_the_actual_top_level_gateway(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();parent,out=self.receive(root,self.checkpoint(root))
            parent.CACHE=root/'cache';parent.CONFLICTS=root/'conflicts'
            with patch.object(gateway,'ROOT',root),patch.object(gateway,'OUTPUT',out):
                self.assertEqual(gateway.dispatch('oot2-write-checkpoint-v9',parent),0)
                self.assertTrue((out/'ZeldaOcarinaOfTime-v9-unwarmed-checkpoint.ipa').is_file())
                self.assertEqual(gateway.dispatch('oot2-checkpoint-v9-info',parent),0)
                parent.send_file=lambda p:self.assertEqual(p,out/'ZeldaOcarinaOfTime-v9-unwarmed-checkpoint.ipa')
                self.assertEqual(gateway.dispatch('oot2-read-checkpoint-v9',parent),0)
                (out/'ZeldaOcarinaOfTime-v9-unwarmed-checkpoint.ipa').write_bytes(b'tampered')
                with self.assertRaisesRegex(ValueError,'identity'):gateway.dispatch('oot2-read-checkpoint-v9',parent)
    def test_declared_but_unimplemented_route_fails_closed(self):
        parent=SimpleNamespace(CACHE=Path('/cache'),CONFLICTS=Path('/conflicts'),OUTPUT=Path('/output'))
        with patch.object(gateway,'ROUTES',gateway.ROUTES|{'oot2-unhandled-fixture'}):
            self.assertEqual(gateway.dispatch('oot2-unhandled-fixture',parent),126)
        self.assertEqual(parent.OUTPUT,Path('/output'))
    def test_raw_checkpoint_is_preserved_separately_without_claiming_prewarm(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();parent,out=self.receive(root,self.checkpoint(root))
            self.assertEqual(v9.dispatch('oot2-write-checkpoint-v9',parent,root,out,None),0)
            saved=out/'ZeldaOcarinaOfTime-v9-unwarmed-checkpoint.ipa';self.assertTrue(saved.is_file())
            self.assertFalse(json.loads((out/'v9-checkpoint.json').read_text())['fullwarm_validated'])
            self.assertFalse((out/'ZeldaOcarinaOfTime-ipad-v9-fullwarm-livecontainer.ipa').exists())
    def test_old_chain_and_invalid_host_cannot_replace_checkpoint(self):
        for chain,host in [('d24f05cf9d78',bytes.fromhex('cffaedfe0c000001')), (v9.CHAIN,b'wrong host')]:
            with self.subTest(chain=chain),tempfile.TemporaryDirectory() as d:
                root=Path(d).resolve();parent,out=self.receive(root,self.checkpoint(root,chain,host))
                saved=out/'ZeldaOcarinaOfTime-v9-unwarmed-checkpoint.ipa';saved.write_bytes(b'previous')
                with self.assertRaises((ValueError,KeyError)):v9.dispatch('oot2-write-checkpoint-v9',parent,root,out,None)
                self.assertEqual(saved.read_bytes(),b'previous')
    def test_v9_resume_route_uses_only_v9_view(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();archive=root/'snapshot';archive.write_bytes(b'compressed')
            stats={'sqlite_bytes':123,'entries':45}
            with patch.object(gateway,'ROOT',root),patch('security.oot2_cache_snapshot.snapshot',return_value=(archive,stats)) as make:
                self.assertEqual(gateway.dispatch('oot2-resume-v9-info',None),0)
                make.assert_called_once_with(root/'cache-resume-v9',root/'cache-transfer-resume-v9',translations=True)
    def test_exact_resume_selects_conflict_index_and_retains_original(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();cache=root/'cas';conflicts=root/'conflicts';out=root/'resume'
            (cache/'index').mkdir(parents=True);(conflicts/'index').mkdir(parents=True)
            fp='a'*64;key='0123456789abcdef';digest='b'*64
            old={'digest':'c'*64,'code_fp':'d'*64};new={'digest':digest,'code_fp':fp}
            original=cache/'index'/f'{key}.json';original.write_text(json.dumps(old))
            data=json.dumps(new).encode();h=hashlib.sha256(data).hexdigest()
            (conflicts/'index'/f'{key}.json.{h}.conflict').write_bytes(data)
            for suffix in ('mac/'+key+'_b.json','mac/'+key+'_b.metal','ios/'+key+'_b.json','ios/'+key+'_b.metallib'):
                p=cache/'shader'/digest/suffix;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'fixture')
            counts=stage(cache,conflicts,out,fp,include_metal=False)
            self.assertEqual(counts['indices'],1)
            self.assertEqual(json.loads((out/'index'/f'{key}.json').read_text()),new)
            self.assertEqual(json.loads(original.read_text()),old)
            self.assertFalse((out/'metallib').exists())

if __name__=='__main__':unittest.main()
