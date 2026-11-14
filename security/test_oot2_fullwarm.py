"""Full-list archives must cover all native rows and be keyed by actual inputs."""
import json
from pathlib import Path
import tempfile
import unittest
from security import oot2_fullwarm as fw
from security import oot2_fullwarm_sdk as sdk


class FullwarmTests(unittest.TestCase):
    def test_sdk_enum_extraction_uses_evaluated_expressions_and_implicit_values(self):
        node = {'kind': 'EnumDecl', 'name': 'MTLTest', 'inner': [
            {'kind': 'EnumConstantDecl', 'name': 'MTLTestZero', 'inner': [{'kind': 'ConstantExpr', 'value': '0'}]},
            {'kind': 'EnumConstantDecl', 'name': 'MTLTestOne'},
            {'kind': 'EnumConstantDecl', 'name': 'MTLTestFlags', 'inner': [{'kind': 'ConstantExpr', 'value': '12'}]},
        ]}
        self.assertEqual(sdk.constants(node, 'MTLTest'), {0: 'Zero', 1: 'One', 12: 'Flags'})
        self.assertEqual(list(sdk.objects('{}\n {"id": 1}')), [{}, {'id': 1}])

    def test_cache_key_survives_relocation_but_changes_for_bytes_state_and_compiler(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); a = root/'a.metallib'; b = root/'b.metallib'; a.write_bytes(b'iOS IR'); b.write_bytes(a.read_bytes())
            cfg = {'libraries': [{'label': 'lib1', 'path': str(a)}], 'pipeline_descriptors': {'mesh_render_pipeline_descriptors': [{'payload_memory_length': 16}]}}
            first = fw.group_key(cfg, 'AppleTT1')
            cfg['libraries'][0]['path'] = str(b)
            self.assertEqual(first, fw.group_key(cfg, 'AppleTT1'))
            b.write_bytes(b'different iOS IR'); self.assertNotEqual(first, fw.group_key(cfg, 'AppleTT1'))
            b.write_bytes(a.read_bytes()); self.assertNotEqual(first, fw.group_key(cfg, 'AppleTT2'))
            cfg['pipeline_descriptors']['mesh_render_pipeline_descriptors'][0]['payload_memory_length'] = 32
            self.assertNotEqual(first, fw.group_key(cfg, 'AppleTT1'))

    def fixture(self, directory):
        coverage = {'chain': fw.CHAIN, 'render_rows': 1, 'mesh_rows': 1, 'emitted_render': 1, 'emitted_mesh': 1,
                    'periods': 1, 'failed_tasks': 0, 'pipeline_creation_used': False, 'new_shaders_compiled': False}
        cfg = {'libraries': [{'label': 'a', 'path': 'a_b.metallib'}], 'pipeline_descriptors': {'render_pipeline_descriptors': [{}], 'mesh_render_pipeline_descriptors': [{}]}}
        (directory/'coverage.json').write_text(json.dumps(coverage)); (directory/'prewarm-00000.mtl4-json').write_text(json.dumps(cfg))
        return coverage, cfg

    def test_missing_or_failed_mesh_never_counts_as_complete(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); coverage, cfg = self.fixture(root)
            self.assertEqual(fw.validate_export(root)['mesh_rows'], 1)
            cfg['pipeline_descriptors']['mesh_render_pipeline_descriptors'] = []
            (root/'prewarm-00000.mtl4-json').write_text(json.dumps(cfg))
            with self.assertRaisesRegex(ValueError, 'rows missing'): fw.validate_export(root)
            coverage['failed_tasks'] = 1; (root/'coverage.json').write_text(json.dumps(coverage))
            with self.assertRaisesRegex(ValueError, 'coverage'): fw.validate_export(root)

    def test_depth_only_rows_are_accounted_without_weakening_other_coverage(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); coverage, _ = self.fixture(root)
            coverage.update(render_rows=3, device_render_rows=2,
                            device_render_reason='metal4_requires_fragment')
            def save(): (root/'coverage.json').write_text(json.dumps(coverage))
            save(); self.assertEqual(fw.validate_export(root)['device_render_rows'], 2)
            for change in ({'device_render_rows': 1}, {'device_render_rows': -1},
                           {'device_render_rows': True}, {'device_render_reason': 'unknown'}):
                original = coverage.copy(); coverage.update(change); save()
                with self.assertRaises(ValueError): fw.validate_export(root)
                coverage = original
            coverage['failed_tasks'] = 1; save()
            with self.assertRaises(ValueError): fw.validate_export(root)

    def test_untrusted_script_library_path_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); _, cfg = self.fixture(root); cfg['libraries'][0]['path'] = '../escape.metallib'
            (root/'prewarm-00000.mtl4-json').write_text(json.dumps(cfg))
            with self.assertRaisesRegex(ValueError, 'library path'): fw.validate_export(root)



class FullwarmPackagingTests(unittest.TestCase):
    def test_rebuilt_host_is_only_changed_original_and_corrupt_archive_is_rejected(self):
        import struct, zipfile
        from security.test_oot2_ipad_aot import AotTests
        from security.oot2_fullwarm_pack import repack
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);slim,base,prefix=AotTests().fixture(root)
            full=root/'full';full.mkdir();name=fw.GPU+'-prewarm-00000.mtl4a'
            binary=full/name;binary.write_bytes(b'compiled mesh/render archive'*8)
            report={'chain':fw.CHAIN,'gpu':fw.GPU,'platform':'ios','coverage':{
                'failed_tasks':0,'render_rows':2,'emitted_render':1,'device_render_rows':1,
                'device_render_reason':'metal4_requires_fragment','mesh_rows':1,'emitted_mesh':1,'periods':1},
                'archives':{name:{'bytes':binary.stat().st_size,'sha256':fw.digest(binary)}}}
            (full/'fullwarm.json').write_text(json.dumps(report));(full/'prewarm.tsv').write_text('full fixture\n')
            host=root/'host';host.write_bytes(struct.pack('<IIII',0xfeedfacf,0x100000c,0,2)+bytes(64))
            out=root/'out.ipa'
            from unittest.mock import patch
            from types import SimpleNamespace
            with patch('security.oot2_fullwarm_pack.shutil.disk_usage', return_value=SimpleNamespace(free=1)):
                with self.assertRaisesRegex(ValueError, 'insufficient disk'):
                    repack(slim,base,full,host,out)
            self.assertFalse(out.exists())
            self.assertFalse(list(root.glob('.oot2-fullwarm-*')))
            repack(slim,base,full,host,out)
            with zipfile.ZipFile(slim) as before,zipfile.ZipFile(out) as after:
                for name in before.namelist():
                    self.assertEqual(after.read(name),host.read_bytes() if name==prefix+'Game' else before.read(name))
                self.assertFalse(any('staging-only' in name for name in after.namelist()))
            binary.write_bytes(b'corruption'*32)
            with self.assertRaisesRegex(ValueError,'archive identity'):repack(slim,base,full,host,root/'bad.ipa')
            self.assertFalse((root/'bad.ipa').exists())

    def test_base_resource_set_tracks_optional_rest_and_rejects_missing_required_inputs(self):
        from security.oot2_fullwarm_pack import base_resources
        from security.test_oot2_ipad_aot import AotTests
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); _,base,_=AotTests().fixture(root)
            self.assertEqual(len(base_resources(base)),3)
            meta=base/'archive.tsv'; original=meta.read_text();meta.write_text(original.replace('rest\t0','rest\t1'))
            with self.assertRaisesRegex(ValueError,'remaining pipeline pairs missing'): base_resources(base)
            (base/'rest_pairs.tsv').write_text('v\tf\n')
            self.assertEqual(len(base_resources(base)),4)
            meta.write_text(original);(base/'prebuilt.tsv').unlink()
            with self.assertRaisesRegex(ValueError,'resource set'): base_resources(base)

    def test_hostkit_rejects_path_escape_before_writing(self):
        import io,tarfile,subprocess
        from security.oot2_fullwarm_host import unpack,PIN,TITLE
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);data=b'evil';manifest={'format':1,'title':TITLE,'package':'v131072','source_revision':PIN,
                'shader_chain':fw.CHAIN,'optimization_recipe_sha256':fw.digest(Path(__file__).with_name('oot2_ipad_v8_manifest.json')),
                'files':{'../escape':{'bytes':len(data),'sha256':__import__('hashlib').sha256(data).hexdigest()}}}
            tarpath=root/'input.tar'
            with tarfile.open(tarpath,'w') as tar:
                for name,raw in [('manifest.json',json.dumps(manifest).encode()),('../escape',data)]:
                    member=tarfile.TarInfo(name);member.size=len(raw);tar.addfile(member,io.BytesIO(raw))
            subprocess.run(['zstd','-q',str(tarpath)],check=True)
            with self.assertRaisesRegex(ValueError,'host kit member'):unpack(str(tarpath)+'.zst',root/'unpacked')
            self.assertFalse((root/'escape').exists());self.assertFalse((root/'unpacked').exists())

class FullwarmFailFastTests(unittest.TestCase):
    def test_host_failure_never_starts_private_archive_compilation(self):
        from unittest.mock import patch
        from security import oot2_fullwarm_build as driver
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'base/inputs').mkdir(parents=True);(root/'output').mkdir()
            with patch.object(driver,'export'),patch.object(driver,'rebuild',side_effect=RuntimeError('link failed')),patch.object(driver,'compile_lists') as compile_,patch.object(driver,'repack') as pack:
                with self.assertRaisesRegex(RuntimeError,'link failed'):
                    driver.build(root/'native',root/'input.ipa',root/'kit',root/'base',root/'output')
                compile_.assert_not_called();pack.assert_not_called()


if __name__ == '__main__': unittest.main()
