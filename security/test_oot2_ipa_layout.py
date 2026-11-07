"""Exercise the real build wrapper with synthetic paths, no SSH or game data."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


class IpaLayoutTests(unittest.TestCase):
    def exercise(self, layout):
        with tempfile.TemporaryDirectory() as temp:
            values = {'RUNNER_TEMP': temp, 'GITHUB_WORKSPACE': str(ROOT)}
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
                mod.NUP.write_bytes(b'synthetic')
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

    def test_separate_obeys_upstream_keep_requirement(self):
        rc, call, _ = self.exercise('separate')
        self.assertEqual(rc, 0)
        argv = call.args[0]
        self.assertEqual(argv[argv.index('--romfs') + 1], 'separate')
        self.assertIn('--keep-extracted', argv)
        self.assertNotIn('--no-keep-extracted', argv)
        self.assertEqual(call.kwargs['env']['DMSH_CAS'], str(Path(call.kwargs['cwd']).parent/'oot2-shader-cas/cas.db'))
        self.assertIn('OOT2_RELEASE_EPHEMERAL_NUP', call.kwargs['env'])

    def test_bad_layout_starts_no_builder(self):
        rc, _, count = self.exercise('unknown')
        self.assertEqual(rc, 1)
        self.assertEqual(count, 0)

    def test_workflow_requires_explicit_separate_choice(self):
        s = (ROOT/'.github/workflows/build-oot2.yml').read_text()
        self.assertIn('default: bundle', s)
        self.assertIn('OOT2_IPA_LAYOUT: ${{ inputs.ipa_layout }}', s)
