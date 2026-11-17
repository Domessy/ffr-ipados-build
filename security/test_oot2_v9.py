import hashlib
import json
from pathlib import Path
import plistlib
import tempfile
import unittest
import zipfile
from security import oot2_v9_gateway as g
from security import oot2_prepare_ipad_v9 as prep

class V9ReceiptTests(unittest.TestCase):
    def fixture(self,folder,chain=None,host=b'host',tamper_host=False):
        chain=chain or prep.CHAIN;p=Path(folder)/'fixture.ipa';pre='Payload/Game.app/'
        archive=b'archive bytes'*8;name=g.GPU+'-prewarm-00000.mtl4a'
        manifest=json.loads(Path(prep.__file__).with_name('oot2_ipad_v9_manifest.json').read_text())
        report={'chain':prep.CHAIN,'gpu':g.GPU,'platform':'ios','coverage':{'render_rows':1,'emitted_render':1,'device_render_rows':0,'mesh_rows':1,'emitted_mesh':1,'failed_tasks':0,'stale_keys':0,'periods':1},'archives':{name:{'bytes':len(archive),'sha256':hashlib.sha256(archive).hexdigest()}},'host':{'source':prep.PIN,'chain':prep.CHAIN,'sha256':hashlib.sha256(host).hexdigest(),'host_v9':{'base':prep.PIN,'chain':prep.CHAIN,'patch_sha256':manifest['patch_sha256']}}}
        with zipfile.ZipFile(p,'w') as z:
            z.writestr(pre+'Info.plist',plistlib.dumps({'CFBundleIdentifier':'org.nxnative.0400486024dec000','CFBundleExecutable':'Game'}))
            z.writestr(pre+'Game',b'tampered' if tamper_host else host)
            z.writestr(pre+f'msl/b-{chain}.img',b'synthetic shader image')
            z.writestr(pre+'pso/fullwarm.json',json.dumps(report))
            z.writestr(pre+'pso/'+name,archive)
            z.writestr(pre+'pso/'+g.GPU+'.mtl4a',b'base')
            z.writestr(pre+'pso/prebuilt.tsv','chain\t'+prep.CHAIN+'\n')
        return p
    def test_new_chain_with_bound_host_and_archives(self):
        with tempfile.TemporaryDirectory() as d:self.assertEqual(g.validate_slim(self.fixture(d))['chain'],prep.CHAIN)
    def test_old_v8_shaders_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'genuine shader chain'):g.validate_slim(self.fixture(d,chain='d24f05cf9d78'))
    def test_tampered_host_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'host hash'):g.validate_slim(self.fixture(d,tamper_host=True))
    def test_previous_output_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d).resolve()/'v9.ipa';p.write_bytes(b'previous');g.preserve(p)
            self.assertFalse(p.exists());self.assertEqual(len(list(Path(d).glob('*.previous'))),1)
            p.write_bytes(b'previous');g.preserve(p);self.assertEqual(len(list(Path(d).glob('*.previous'))),1)
    def test_complete_receipt_and_romfs_assembly(self):
        import struct, shutil
        from types import SimpleNamespace
        from security.oot2_local_bundle import identity
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();out=root/'resultats';out.mkdir();source=root/'source';source.mkdir()
            image=root/'local-bundle-v6/extract/v131072/RomFS.img';image.parent.mkdir(parents=True)
            body=b'body';index=b'index';image.write_bytes(struct.pack('<8sQQQ',b'DMROMFS1',32+len(body),len(index),1)+body+index)
            ident=identity(image);meta=root/'local-bundle-v6/romfs-manifest.json'
            meta.write_text(json.dumps({'bytes':image.stat().st_size,'identity':ident,'sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'source_identity':'test'}))
            ipa=self.fixture(source)
            with zipfile.ZipFile(ipa,'a') as z:z.writestr('Payload/Game.app/romfs.id',f'DMROMFSID1 title=0400486024DEC000 size={ident[0]} index={ident[1]}')
            parent=SimpleNamespace(OUTPUT=root/'unused')
            parent.receive_file=lambda name,limit:shutil.copyfile(ipa,parent.OUTPUT/name)
            self.assertEqual(g.dispatch('oot2-write-slim-v9',parent,root,out,lambda:'test'),0)
            self.assertEqual(parent.OUTPUT,root/'unused')
            with zipfile.ZipFile(out/'ZeldaOcarinaOfTime-ipad-v9-fullwarm-livecontainer.ipa') as z:
                self.assertIsNone(z.testzip());self.assertEqual(z.read('Payload/Game.app/romfs.img'),image.read_bytes())
    def test_unknown_command_rejected(self):
        self.assertEqual(g.dispatch('oot2-write-slim-v8',None,None,None,None),126)

if __name__=='__main__':unittest.main()
