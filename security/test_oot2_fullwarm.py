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

    def test_untrusted_script_library_path_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); _, cfg = self.fixture(root); cfg['libraries'][0]['path'] = '../escape.metallib'
            (root/'prewarm-00000.mtl4-json').write_text(json.dumps(cfg))
            with self.assertRaisesRegex(ValueError, 'library path'): fw.validate_export(root)


if __name__ == '__main__': unittest.main()
