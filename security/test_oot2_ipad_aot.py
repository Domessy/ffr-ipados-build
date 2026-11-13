"""AOT repacking cannot change the executable/shaders or trust a foreign cache."""
import io
import plistlib
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile
from unittest.mock import Mock, patch
from security import oot2_ipad_aot as aot
from security import oot2_gateway as gw
from security import ffr_ssh_gate as gate


class AotTests(unittest.TestCase):
    def test_cache_only_mode_never_builds_an_intermediate_ipa(self):
        with patch('sys.argv', ['oot2_ipad_aot.py', 'build-cache', '/native', '/input.ipa', '/work']), \
             patch.object(aot, 'compile_archive', return_value=Path('/cache/bundle')) as compile_cache, \
             patch.object(aot, 'repack') as repack:
            aot.main()
            compile_cache.assert_called_once_with(Path('/native'), Path('/input.ipa'), Path('/work'))
            repack.assert_not_called()

    def fixture(self, root):
        slim = root / 'input.ipa'; prefix = 'Payload/Game.app/'
        with zipfile.ZipFile(slim, 'w') as z:
            z.writestr(prefix + 'Info.plist', plistlib.dumps({'CFBundleIdentifier': 'org.nxnative.0400486024dec000', 'CFBundleExecutable': 'Game'}))
            z.writestr(prefix + 'Game', b'unchanged executable')
            z.writestr(prefix + f'msl/b-{aot.CHAIN}.img', b'unchanged compiled shaders')
            z.writestr(prefix + 'dm/env.txt', b'DM_GUEST_FILE=1\n')
            for table in aot.TABLES: z.writestr(prefix + 'dm/' + table, b'# synthetic\n')
        bundle = root / 'bundle'; bundle.mkdir()
        (bundle / (aot.GPU + '.mtl4a')).write_bytes(b'archive fixture' * 8)
        (bundle / 'archive.tsv').write_text(f'platform\tios\t27.0\narch\t{aot.GPU}\nbases\t1\n')
        (bundle / 'prebuilt.tsv').write_text(f'chain\t{aot.CHAIN}\n')
        return slim, bundle, prefix

    def test_repack_preserves_every_original_and_passes_zip64(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); slim, bundle, prefix = self.fixture(root); out = root / 'output.ipa'
            result = aot.repack(slim, bundle, out)
            with zipfile.ZipFile(slim) as before, zipfile.ZipFile(out) as after:
                for name in before.namelist(): self.assertEqual(before.read(name), after.read(name))
                self.assertIn(prefix + 'pso/' + aot.GPU + '.mtl4a', after.namelist())
            self.assertEqual(result['original_resources_verified'], 8)
            with self.assertRaisesRegex(ValueError, 'already exists'): aot.repack(slim, bundle, out)

    def test_mac_archive_or_wrong_chain_not_published(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); slim, bundle, _ = self.fixture(root)
            meta = bundle / 'archive.tsv'; original = meta.read_text(); meta.write_text(original.replace('ios', 'macos'))
            with self.assertRaisesRegex(ValueError, 'platform'): aot.repack(slim, bundle, root / 'output.ipa')
            self.assertFalse((root / 'output.ipa').exists()); meta.write_text(original)
            (bundle / 'prebuilt.tsv').write_text('chain\twrong\n')
            with self.assertRaisesRegex(ValueError, 'chain'): aot.check_bundle(bundle)

    def test_compiler_uses_packed_pair_tables_and_ios_target(self):
        cmd = aot.compiler_command('/native', '/inputs', '/cache')
        self.assertEqual(cmd[cmd.index('--platform') + 1], 'ios')
        self.assertEqual(cmd[cmd.index('--gpu') + 1], aot.GPU)
        self.assertIn('/inputs/dm/pso_pairs.tsv', cmd)
        self.assertNotIn('--no-compute', cmd)
        self.assertEqual(cmd[cmd.index('--jobs') + 1], '2')

    def test_cache_roundtrip_keeps_compiled_keys_without_shader_scratch(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); cache = root / 'cache'; (cache / 'work/libraries').mkdir(parents=True)
            (cache / 'work/key.g17g').write_text('key'); (cache / 'work/libraries/private.metallib').write_bytes(b'scratch')
            (cache / 'work/batch.mtl4a').write_bytes(b'compiled')
            archive = root / 'cache.tar.gz'; aot.save_cache(cache, archive); aot.restore_cache(archive, root / 'restored')
            self.assertEqual((root / 'restored/work/batch.mtl4a').read_bytes(), b'compiled')
            self.assertFalse((root / 'restored/work/libraries').exists())

    def test_cache_traversal_and_links_rejected_before_extraction(self):
        for name, kind in [('../escape', tarfile.REGTYPE), ('work/link', tarfile.SYMTYPE), ('/absolute', tarfile.REGTYPE), ('wrong/file', tarfile.REGTYPE)]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as d:
                root = Path(d); archive = root / 'bad.tar.gz'
                with tarfile.open(archive, 'w:gz') as z:
                    item = tarfile.TarInfo(name); item.type = kind; item.size = 1 if kind == tarfile.REGTYPE else 0
                    z.addfile(item, io.BytesIO(b'x') if item.size else None)
                with self.assertRaisesRegex(ValueError, 'cache'): aot.restore_cache(archive, root / 'out')
                self.assertFalse((root / 'escape').exists())

    def test_live_checkpoint_omits_uncommitted_groups(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); cache = root / 'cache'
            ready = cache / 'work/batches.applegpu_g17g/00001'; ready.mkdir(parents=True)
            (ready / 'applegpu_g17g.mtl4a').write_bytes(b'completed')
            (ready / 'key.applegpu_g17g').write_text('stable key')
            busy = cache / 'work/batches.applegpu_g17g/00002'; busy.mkdir()
            (busy / 'applegpu_g17g.mtl4a').write_bytes(b'previous binary with key removed')
            checkpoint = root / 'checkpoint.tar.gz'; aot.save_completed_cache(cache, checkpoint)
            aot.restore_cache(checkpoint, root / 'restored')
            self.assertEqual((root / 'restored/work/batches.applegpu_g17g/00001/applegpu_g17g.mtl4a').read_bytes(), b'completed')
            self.assertFalse((root / 'restored/work/batches.applegpu_g17g/00002').exists())

    def test_public_progress_is_numeric_and_private_diagnostic_keeps_nested_errors(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root / 'work/cache/work/batches.g17g/00001').mkdir(parents=True)
            (root / 'work/aot-private.log').write_text('pso_offline: 34649 pairs: 33365 bases, 0 left\npso_offline: 4125 compute shaders: 4125 compute pipelines,\nPRIVATE_SHADER_NAME')
            (root / 'work/cache/work/batches.g17g/00001/key.g17g').write_text('key')
            (root / 'work/cache/work/metal-tt.g17g.log').write_text('synthetic private compiler error')
            progress = aot.public_progress(root / 'work')
            self.assertEqual(progress['total_batches'], 292)
            self.assertEqual(progress['completed_batches'], 1)
            self.assertNotIn('PRIVATE_SHADER_NAME', str(progress))
            self.assertIn(b'synthetic private compiler error', aot.private_diagnostic(root))

    def test_gateway_reads_only_fixed_aot_input_and_rejects_arguments(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            with patch.object(gw, 'OUTPUT', out), patch.object(gate, 'send_file') as send:
                self.assertEqual(gw.dispatch('oot2-aot-v8-read-input', gate), 0)
                send.assert_called_once_with(out / 'ZeldaOcarinaOfTime-v8-aot-input.ipa')
                self.assertEqual(gw.dispatch('oot2-aot-v8-read-input /arbitrary', gate), 126)

    def test_gateway_delivery_uses_distinct_full_ipa_and_requires_archive(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); slim, bundle, prefix = self.fixture(root)
            target = root / 'ZeldaOcarinaOfTime-v8-aot-slim.ipa'; aot.repack(slim, bundle, target)
            with patch.object(gw, 'ROOT', root), patch.object(gw, 'OUTPUT', root), patch.object(gate, 'receive_file') as receive, patch('security.oot2_local_bundle.bundle', return_value={'ipa_bytes': 123}) as complete:
                self.assertEqual(gw.dispatch('oot2-aot-v8-write-slim', gate), 0)
                self.assertEqual(complete.call_args.args[-1], root / 'ZeldaOcarinaOfTime-ipad-v8-aot-livecontainer.ipa')
                self.assertEqual(complete.call_args.kwargs['expected_chain'], aot.CHAIN)


if __name__ == '__main__': unittest.main()
