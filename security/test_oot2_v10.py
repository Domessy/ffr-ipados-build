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
    def test_complete_top_level_delivery_assembles_original_romfs(self):
        import shutil
        from security.oot2_local_bundle import identity
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();out=root/'out';out.mkdir();source=self.fixture(root)
            image=root/'local-bundle-v6/extract/v131072/RomFS.img';image.parent.mkdir(parents=True)
            image.write_bytes(struct.pack('<8sQQQ',b'DMROMFS1',36,5,1)+b'body'+b'index')
            ident=identity(image);meta=root/'local-bundle-v6/romfs-manifest.json'
            meta.write_text(json.dumps({'bytes':image.stat().st_size,'identity':ident,'sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'source_identity':'fixture'}))
            with zipfile.ZipFile(source,'a') as z:z.writestr('Payload/Game.app/romfs.id',f'DMROMFSID1 title={o.TITLE} size={ident[0]} index={ident[1]}')
            stable=out/'ZeldaOcarinaOfTime-ipad-v9-fullwarm-livecontainer.ipa';stable.write_bytes(b'v9 retained')
            parent=SimpleNamespace(CACHE=root/'cache',CONFLICTS=root/'conflicts',OUTPUT=out)
            parent.receive_file=lambda name,limit:shutil.copyfile(source,parent.OUTPUT/name)
            with patch.object(gate,'ROOT',root),patch.object(gate,'OUTPUT',out):
                self.assertEqual(gate.dispatch('oot2-write-slim-v10',parent),0)
            final=out/'ZeldaOcarinaOfTime-ipad-v10-fullwarm-livecontainer.ipa'
            with zipfile.ZipFile(final) as z:
                self.assertIsNone(z.testzip());self.assertEqual(z.read('Payload/Game.app/romfs.img'),image.read_bytes())
            self.assertEqual(o.validate_delivery(final)['chain'],CHAIN)
            self.assertEqual(stable.read_bytes(),b'v9 retained')
    def test_native_index_copy_requires_complete_nonempty_content(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);src=root/'scripts';out=root/'out';src.mkdir();out.mkdir()
            archive=out/(o.GPU+'-prewarm-00000.mtl4a');archive.write_bytes(b'archive')
            index=src/'prewarm-00000.keys'
            for raw in (b'',b'DMPSOIX2'+struct.pack('<IIQ',0,1,1),b'DMPSOIX2'+struct.pack('<II',1,0)):
                index.write_bytes(raw)
                with self.assertRaises(ValueError):o.install_indexes(src,out)
            raw=b'DMPSOIX2'+struct.pack('<IIQ',1,1,123);index.write_bytes(raw)
            o.install_indexes(src,out);self.assertEqual(archive.with_suffix('.keys').read_bytes(),raw)
    def test_metadata_coverage_cannot_silently_omit_or_misclassify_rows(self):
        seed={'R':7138,'M':164}
        coverage={'render_rows':7138,'emitted_render':7125,'device_render_rows':13,'device_render_reason':'metal4_requires_fragment','mesh_rows':164,'emitted_mesh':164,'failed_tasks':0,'periods':1,'pipeline_creation_used':False,'new_shaders_compiled':False}
        report={'chain':CHAIN,'gpu':o.GPU,'platform':'ios','coverage':coverage,'archives':{'a':{}}}
        o.metadata_coverage(report,seed,['a'])
        for key,value in [('render_rows',7137),('emitted_mesh',163),('failed_tasks',1),('pipeline_creation_used',True),('stale_keys',1)]:
            with self.subTest(key=key):
                changed=dict(coverage);changed[key]=value
                with self.assertRaises(ValueError):o.metadata_coverage(dict(report,coverage=changed),seed,['a'])
    def test_metadata_final_receipt_checks_all_indexed_rows(self):
        for count in (7289,7288):
            with tempfile.TemporaryDirectory() as d:
                root=Path(d);source=self.fixture(root);target=root/'metadata.ipa';pre='Payload/Game.app/pso/'
                with zipfile.ZipFile(source) as z:files={i.filename:z.read(i) for i in z.infolist()}
                report=json.loads(files[pre+'oot2-v10.json']);archive=o.GPU+'-prewarm-00.mtl4a'
                coverage={'render_rows':7138,'emitted_render':7125,'device_render_rows':13,'device_render_reason':'metal4_requires_fragment','mesh_rows':164,'emitted_mesh':164,'failed_tasks':0,'periods':1,'pipeline_creation_used':False,'new_shaders_compiled':False}
                metadata={'chain':CHAIN,'gpu':o.GPU,'platform':'ios','coverage':coverage,'archives':{archive:report['resources'][archive]}}
                files[pre+'fullwarm.json']=json.dumps(metadata).encode()
                files[pre+archive[:-6]+'.keys']=b'DMPSOIX2'+struct.pack('<II',1,count)+struct.pack('<Q',123)*count
                for n,b in files.items():
                    if n.startswith(pre) and n!=pre+'oot2-v10.json':report['resources'][n[len(pre):]]={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
                files[pre+'oot2-v10.json']=json.dumps(report).encode()
                with zipfile.ZipFile(target,'w') as z:
                    for n,b in files.items():z.writestr(n,b)
                if count==7289:self.assertEqual(o.validate_delivery(target)['prewarm_files'],1)
                else:
                    with self.assertRaisesRegex(ValueError,'index coverage'):o.validate_delivery(target)
    def test_wrong_resource_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            source=self.fixture(Path(d));target=Path(d)/'corrupt.ipa'
            with zipfile.ZipFile(source) as src,zipfile.ZipFile(target,'w') as dst:
                for i in src.infolist():dst.writestr(i,b'tampered' if i.filename.endswith('prewarm-00.mtl4a') else src.read(i))
            with self.assertRaisesRegex(ValueError,'resource hash'):o.validate_delivery(target)

if __name__=='__main__':unittest.main()
