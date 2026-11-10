"""Exercise the real build wrapper with synthetic paths, no SSH or game data."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from security.test_oot2_nup_info import fake_nup
from security.oot2_nup_info import release_identity

ROOT = Path(__file__).resolve().parents[1]


class IpaLayoutTests(unittest.TestCase):
    def exercise(self, layout, variant='baseline', valid_identity=True):
        with tempfile.TemporaryDirectory() as temp:
            values = {'RUNNER_TEMP': temp, 'GITHUB_WORKSPACE': str(ROOT),
                      'OOT2_RUNTIME_VARIANT': variant}
            if layout is not None:
                values['OOT2_IPA_LAYOUT'] = layout
            with patch.dict(os.environ, values):
                if layout is None:
                    os.environ.pop('OOT2_IPA_LAYOUT', None)
                spec = importlib.util.spec_from_file_location('oot2_layout_fixture', ROOT/'security/run_oot2.py')
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                mod.CACHE.mkdir()
                mod.CAS_DB.write_bytes(b'synthetic')
                mod.NUP_FOLDER.mkdir()
                fake_nup(mod.NUP, standalone=True, romfs_file_bytes=8, base_version=65536)
                os.environ['OOT2_NUP_ID'] = release_identity(mod.NUP) if valid_identity else 'wrong'
                mod.OUTPUT.write_bytes(b'synthetic')
                proc = Mock()
                proc.poll.return_value = 0
                proc.wait.return_value = 0
                with patch.object(mod.subprocess, 'Popen', return_value=proc) as launch, \
                     patch.object(mod, 'checkpoint'), patch.object(mod, 'sync_private_diagnostic'):
                    rc = mod.compile_ipa()
                return rc, launch.call_args, launch.call_count

    def test_default_bundle_stays_compatible(self):
        rc, call, _ = self.exercise(None)
        self.assertEqual(rc, 0)
        self.assertIn('--no-keep-extracted', call.args[0])
        self.assertNotIn('--romfs', call.args[0])

    def test_changed_source_identity_starts_no_builder(self):
        rc, _, count = self.exercise('bundle', valid_identity=False)
        self.assertEqual(rc, 1)
        self.assertEqual(count, 0)

    def test_separate_obeys_upstream_keep_requirement(self):
        rc, call, _ = self.exercise('separate')
        self.assertEqual(rc, 0)
        argv = call.args[0]
        self.assertEqual(argv[argv.index('--romfs') + 1], 'separate')
        self.assertIn('--keep-extracted', argv)
        self.assertNotIn('--no-keep-extracted', argv)
        self.assertEqual(call.kwargs['env']['DMSH_CAS'], str(Path(call.kwargs['cwd']).parent/'oot2-shader-cas/cas.db'))
        self.assertIn('OOT2_RELEASE_EPHEMERAL_NUP', call.kwargs['env'])

    def test_local_bundle_v6_uses_slim_native_pack_and_v6_defaults(self):
        rc, call, _ = self.exercise('local-bundle', 'ipad-v6')
        self.assertEqual(rc, 0)
        argv = call.args[0]
        self.assertEqual(argv[argv.index('--romfs') + 1], 'separate')
        self.assertIn('--keep-extracted', argv)
        self.assertTrue(argv[argv.index('--env-file') + 1].endswith('oot2_ipad_v6_defaults.env'))

    def test_local_bundle_v7_keeps_native_separate_and_its_own_defaults(self):
        rc, call, _ = self.exercise('local-bundle', 'ipad-v7')
        self.assertEqual(rc, 0)
        argv = call.args[0]
        self.assertEqual(argv[argv.index('--romfs') + 1], 'separate')
        self.assertTrue(argv[argv.index('--env-file') + 1].endswith('oot2_ipad_v7_defaults.env'))

    def test_bad_layout_starts_no_builder(self):
        rc, _, count = self.exercise('unknown')
        self.assertEqual(rc, 1)
        self.assertEqual(count, 0)

    def test_workflow_requires_explicit_separate_choice(self):
        s = (ROOT/'.github/workflows/build-oot2.yml').read_text()
        self.assertIn('default: local-bundle', s)
        self.assertIn('IPA_ROUTE=oot2-write-slim-v6', s)
        self.assertIn('OOT2_IPA_LAYOUT: ${{ inputs.ipa_layout }}', s)

    def test_upstream_build_bakes_in_reinstall_safe_memory_default(self):
        rc, call, _ = self.exercise('bundle', 'upstream-v4')
        self.assertEqual(rc, 0)
        argv = call.args[0]
        defaults = Path(argv[argv.index('--env-file') + 1])
        self.assertEqual(defaults, ROOT/'security/oot2_ipados_defaults.env')
        self.assertEqual([l for l in defaults.read_text().splitlines()
                          if l and not l.startswith('#')], ['DM_GUEST_FILE=1'])

    def test_old_variants_keep_existing_memory_default(self):
        _, call, _ = self.exercise('bundle', 'terrain-v3')
        self.assertNotIn('--env-file', call.args[0])

    def test_ipad_v5_uses_explicit_optimization_defaults(self):
        rc, call, _ = self.exercise('bundle', 'ipad-v5')
        self.assertEqual(rc, 0)
        argv = call.args[0]
        defaults = Path(argv[argv.index('--env-file') + 1])
        values = dict(line.split('=', 1) for line in defaults.read_text().splitlines()
                      if line and not line.startswith('#'))
        self.assertEqual(values['DM_GUEST_FILE'], '1')
        self.assertEqual(values['DM_NVN_RT_RECYCLE'], '1')
        self.assertEqual(values['DM_NVN_SEG_POST'], '1')
        self.assertEqual(values['DM_NVN_SEG_RB'], '1')
        self.assertEqual(values['DM_NVN_MESH_CPRE'], '0')
        self.assertEqual(values['DM_NVN_MESH_CPRE_DEQ'], '8')
