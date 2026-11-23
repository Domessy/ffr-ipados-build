"""Reject changed official profiles before patching or transferring game inputs."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from security.oot2_v14_profile import verify_profile


class V14ProfileTests(unittest.TestCase):
    def fixture(self, root):
        profile = root / 'dm/games/0400486024DEC000'
        profile.mkdir(parents=True)
        data = {'shader_map.tsv': ''.join(f'vs_shader.bin\t{i}\tvertex\t{i:016x}\t/source\n'
                                          for i in range(42847)),
                'game.tsv': 'mem_reserve\t0x420000000\nmem_alias\t0x200000000\n'}
        for name, text in data.items():
            (profile / name).write_text(text)
        return profile, {name: hashlib.sha256(text.encode()).hexdigest() for name, text in data.items()}

    def test_official_table_is_verified_without_rewriting_it(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); profile, spec = self.fixture(root)
            before = (profile / 'shader_map.tsv').read_bytes()
            self.assertEqual(verify_profile(root, spec), 42847)
            self.assertEqual((profile / 'shader_map.tsv').read_bytes(), before)

    def test_stale_profile_cannot_pass_pinned_digest(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); profile, spec = self.fixture(root)
            (profile / 'game.tsv').write_text('mem_alias\t0x100000000\n')
            with self.assertRaisesRegex(ValueError, 'identity'):
                verify_profile(root, spec)

    def test_old_alias_or_missing_shader_is_rejected_even_with_matching_hash(self):
        for name, mutation, message in [
            ('game.tsv', lambda s: s.replace('0x200000000', '0x100000000'), 'alias'),
            ('shader_map.tsv', lambda s: s.rsplit('\n', 2)[0] + '\n', 'count'),
            ('shader_map.tsv', lambda s: s.replace('\t0000000000000000\t', '\tce0eba6c3584814d\t'), 'sequence'),
        ]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as d:
                root = Path(d); profile, spec = self.fixture(root)
                p = profile / name; p.write_text(mutation(p.read_text()))
                spec[name] = hashlib.sha256(p.read_bytes()).hexdigest()
                with self.assertRaisesRegex(ValueError, message):
                    verify_profile(root, spec)
