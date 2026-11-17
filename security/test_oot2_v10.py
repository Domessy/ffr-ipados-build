"""Synthetic v10 receipts: exact chain, official complete indexes, no stale delivery."""
import hashlib,json,plistlib,struct,tempfile,unittest,zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from security import oot2_v10_official as o,oot2_v10_gateway as v,oot2_gateway as gate
from security.oot2_prepare_ipad_v10 import PIN,CHAIN,recipe

class V10Tests(unittest.TestCase):
    def fixture(self,root,chain=CHAIN,incomplete=False):
        pre='Payload/Game.app/';p=root/'fixture.ipa';host=bytes.fromhex('cffaedfe0c000001')+b'host'
        seed={'S':16818,'C':1043,'R':7138,'M':164};manifest=''.join(f'{k}\t{i}\n' for k,n in seed.items() for i in range(n))
        archive=o.GPU+'-prewarm-00.mtl4a'
        files={o.GPU+'.mtl4a':b'base',archive:b'full',archive[:-6]+'.keys':b'DMPSOIX2'+struct.pack('<IIQ',0 if incomplete else 1,1,123),'prewarm.tsv':f'chain\t{CHAIN}\nfiles\t1\nlines\t7302\n'.encode(),'prebuilt.tsv':f'chain\t{CHAIN}\n'.encode(),'archive.tsv':b'prewarm\t1 files (1 MB) from 7302 rows, 0 pipelines left out\n'}
        report={'chain':CHAIN,'source':PIN,'recipe_sha256':recipe(),'gpu':o.GPU,'platform':'ios','host_sha256':hashlib.sha256(host).hexdigest(),'seed_counts':seed,'prewarm_files':1,'resources':{n:{'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in files.items()}}
        with zipfile.ZipFile(p,'w') as z:
            z.writestr(pre+'Info.plist',plistlib.dumps({'CFBundleIdentifier':'org.nxnative.0400486024dec000','CFBundleExecutable':'Game'}));z.writestr(pre+'Game',host);z.writestr(pre+f'msl/b-{chain}.img',b'synthetic library')
            for n in ('shader_map.tsv','shader_pairs.tsv','pso_pairs.tsv'):z.writestr(pre+'dm/'+n,b'fixture')
            z.writestr(pre+'dm/pso_manifest.tsv',manifest)
            for n,b in files.items():z.writestr(pre+'pso/'+n,b)
            z.writestr(pre+'pso/oot2-v10.json',json.dumps(report))
        return p
    def test_official_receipt_validates_expanded_manifest_and_all_hashes(self):
        with tempfile.TemporaryDirectory() as d:self.assertEqual(o.validate_delivery(self.fixture(Path(d)))['seed_counts']['R'],7138)
    def test_old_chain_and_incomplete_index_are_rejected(self):
        for chain,bad in [('9eecb8412308',False),(CHAIN,True)]:
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(ValueError):o.validate_delivery(self.fixture(Path(d),chain,bad))
    def test_top_gateway_checkpoint_round_trip_and_preserves_v9(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();out=root/'out';out.mkdir();source=self.fixture(root)
            stable=out/'ZeldaOcarinaOfTime-v9-unwarmed-checkpoint.ipa';stable.write_bytes(b'preserve v9')
            parent=SimpleNamespace(CACHE=root/'cache',CONFLICTS=root/'conflicts',OUTPUT=out)
            import shutil
            parent.receive_file=lambda name,limit:shutil.copyfile(source,parent.OUTPUT/name)
            # A checkpoint may contain archives, but is not published as a final IPA.
            with patch.object(gate,'ROOT',root),patch.object(gate,'OUTPUT',out):
                self.assertEqual(gate.dispatch('oot2-write-checkpoint-v10',parent),0)
                self.assertEqual(gate.dispatch('oot2-checkpoint-v10-info',parent),0)
            self.assertEqual(stable.read_bytes(),b'preserve v9')
            self.assertFalse((out/'ZeldaOcarinaOfTime-ipad-v10-fullwarm-livecontainer.ipa').exists())
    def test_wrong_resource_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            source=self.fixture(Path(d));target=Path(d)/'corrupt.ipa'
            with zipfile.ZipFile(source) as src,zipfile.ZipFile(target,'w') as dst:
                for i in src.infolist():dst.writestr(i,b'tampered' if i.filename.endswith('prewarm-00.mtl4a') else src.read(i))
            with self.assertRaisesRegex(ValueError,'resource hash'):o.validate_delivery(target)

if __name__=='__main__':unittest.main()
