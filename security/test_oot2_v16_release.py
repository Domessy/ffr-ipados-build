"""The new upstream external-DLC branch must never release an unrelated NUP."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from security.oot2_prepare_ipad_v16 import ANCHOR, nup_release_source
from security.test_oot2_patch_nup_release import FIXTURE


class V16ReleaseTests(unittest.TestCase):
    def fixture(self, siblings, external):
        code = FIXTURE.replace('    aoc = extract_aoc(nx, keys, repo, work, app, fam, logs)\n', ANCHOR)
        code = code.replace('    platform = "ios"', f'    aoc_dir = {external!r}\n    platform = "ios"')
        code = code.replace('        toc_sha =', f'        siblings = {siblings!r}\n        toc_sha =')
        code = code.replace('def main(args=None):', 'def stage_external_dlc(work, directory): return None\n\ndef main(args=None):')
        return nup_release_source(code)

    def test_only_the_verified_single_container_without_external_dlc_is_released(self):
        for siblings, external in [([], None), (['other.nup'], None), ([], '/external/dlc')]:
            with self.subTest(siblings=siblings, external=external), tempfile.TemporaryDirectory() as d:
                root = Path(d); nup = root / 'oot2-nup/OcarinaOfTime.nup'
                nup.parent.mkdir(); nup.write_bytes(b'synthetic runner input')
                original = root / 'original.nup'; original.write_bytes(b'preserve original')
                romfs = root / 'oot2-work/extract/v131072/RomFS.img'
                romfs.parent.mkdir(parents=True); romfs.write_bytes(b'extracted')
                env = {'RUNNER_TEMP': str(root), 'OOT2_RELEASE_EPHEMERAL_NUP': str(nup),
                       'OOT2_RELEASE_EPHEMERAL_NUP_ID': f"{nup.stat().st_size}:{'ab'*32}"}
                namespace = {'__name__': 'synthetic'}
                with patch.dict(os.environ, env):
                    exec(self.fixture(siblings, external), namespace)
                    if not siblings and external is None:
                        self.assertTrue(namespace['main']())
                        self.assertFalse(nup.exists())
                    else:
                        with self.assertRaisesRegex(ValueError, 'safety conditions'):
                            namespace['main']()
                        self.assertTrue(nup.is_file())
                self.assertEqual(original.read_bytes(), b'preserve original')
                self.assertTrue(romfs.is_file())

    def test_changed_or_already_injected_anchor_is_rejected(self):
        with self.assertRaises(ValueError):
            nup_release_source(FIXTURE)
        with self.assertRaises(ValueError):
            nup_release_source(self.fixture([], None))
