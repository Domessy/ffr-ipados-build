"""A reader correction refreshes only a pinned map, never the packing gate."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from security.oot2_refresh_v11_profile import refreshed_map, refresh_profile


class ProfileRefreshTests(unittest.TestCase):
    def fixture(self):
        before = (b'package\tindex\tstage\tdm_ctl_sha16\tsource\n'
                  b'vs_shader.bin\t0\tvertex\tkeep1\t/a#BAHS@0x20\n'
                  b'vs_shader.bin\t1\tvertex\tstray\t/a#BAHS@0x44\n'
                  b'ps_shader.bin\t0\tpixel\tkeep2\t/a#BAHS@0x60\n'
                  b'vs_shader.bin\t2\tvertex\tkeep3\t/a#BAHS@0x80\n')
        after = before.replace(b'vs_shader.bin\t1\tvertex\tstray\t/a#BAHS@0x44\n', b'').replace(b'vs_shader.bin\t2', b'vs_shader.bin\t1')
        spec = {'removed_key': 'stray', 'input_sha256': hashlib.sha256(before).hexdigest(),
                'output_sha256': hashlib.sha256(after).hexdigest()}
        return before, after, spec

    def test_removes_only_stray_and_reindexes_each_package(self):
        before, after, spec = self.fixture()
        self.assertEqual(refreshed_map(before, spec), after)

    def test_unknown_input_or_output_identity_is_rejected(self):
        before, after, spec = self.fixture()
        for data, rule in [(before + b'\n', spec), (after, spec),
                           (before, dict(spec, output_sha256='0'*64))]:
            with self.assertRaises(ValueError):
                refreshed_map(data, rule)

    def test_preserved_table_mutation_or_reference_blocks_refresh(self):
        before, after, spec = self.fixture()
        names = ('shader_facts.tsv', 'shader_pairs.tsv', 'pso_pairs.tsv', 'pso_manifest.tsv')
        for payload in (b'changed', b'stray'):
            with tempfile.TemporaryDirectory() as d:
                root = Path(d); profile = root/'dm/games/0400486024DEC000'; profile.mkdir(parents=True)
                path = profile/'shader_map.tsv'; path.write_bytes(before)
                for name in names:
                    (profile/name).write_bytes(b'preserved')
                spec['preserved'] = {name: hashlib.sha256(b'preserved').hexdigest() for name in names}
                (profile/names[0]).write_bytes(payload)
                if payload == b'stray':
                    spec['preserved'][names[0]] = hashlib.sha256(payload).hexdigest()
                with self.assertRaises(ValueError):
                    refresh_profile(root, spec)
                self.assertEqual(path.read_bytes(), before)
