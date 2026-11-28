"""Reject stale registered and generated shader tables."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from security.oot2_v16_profile import validate_shader_map, verify_profile


class V16ProfileTests(unittest.TestCase):
    def fixture(self, root):
        profile = root / 'dm/games/0400486024DEC000'
        profile.mkdir(parents=True)
        data = {'pso_manifest.tsv': 'R\tsynthetic\n',
                'game.tsv': 'mem_reserve\t0x420000000\nmem_alias\t0x200000000\n'}
        for name, text in data.items():
            (profile / name).write_text(text)
        expected = {name: hashlib.sha256(text.encode()).hexdigest() for name, text in data.items()}
        return profile, expected

    def test_registered_profile_leaves_tables_to_the_split(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile, expected = self.fixture(root)
            verify_profile(root, expected)
            (profile / 'shader_map.tsv').write_text('stale')
            with self.assertRaisesRegex(ValueError, 'generated table'):
                verify_profile(root, expected)

    def test_unsupported_memory_profile_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile, expected = self.fixture(root)
            path = profile / 'game.tsv'
            path.write_text(path.read_text().replace('0x200000000', '0x100000000'))
            with self.assertRaisesRegex(ValueError, 'identity'):
                verify_profile(root, expected)
            expected[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'alias'):
                verify_profile(root, expected)

    def test_missing_or_stale_shader_is_rejected(self):
        rows = 'vs.bin\t0\tvertex\t1234567890abcdef\t/source\n'
        self.assertEqual(validate_shader_map(rows, 1), {'1234567890abcdef'})
        for content, count, reason in [
            (rows, 2, 'count'),
            (rows.replace('1234567890abcdef','ce0eba6c3584814d'), 1, 'sequence'),
            (rows * 2, 2, 'sequence'),
        ]:
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                validate_shader_map(content, count)
