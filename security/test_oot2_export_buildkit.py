"""Only synthetic rewritten modules and metadata, never a real game kit."""
from pathlib import Path
import os
import hashlib
import json
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from security import oot2_export_buildkit as kit
from security import oot2_gateway as gw
from security import ffr_ssh_gate as gate


class BuildkitTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.source = self.root / 'nxnative'
        self.gen = self.source / 'dm/ios/Gen'
        self.patched = self.root / 'oot2-work/patched_v131072'
        files = {'oot2-work/patched_v131072/main.patched.bin': b'synthetic rewritten code',
                 'oot2-work/patched_v131072/main.fixups.tsv': b'synthetic relocations',
                 'oot2-work/patched_v131072/prod.keys': b'NEVER export this fixture',
                 'oot2-work/extract/v131072/RomFS.img': b'NEVER export this fixture',
                 'nxnative/dm/gfx/nvn/dmsh_chain.h': f'#define DMSH_CHAIN "{kit.CHAIN}"'.encode(),
                 'nxnative/dm/ios/Gen/dm/c1_full.tsv': b'c1 stamp',
                 'nxnative/dm/ios/Gen/dm/env.txt': b'DM_GUEST_FILE=1\n',
                 'nxnative/dm/ios/Gen/Info.plist': b'synthetic app metadata',
                 f'nxnative/dm/games/{kit.TITLE}/game.tsv': b'synthetic profile',
                 f'nxnative/dm/games/{kit.TITLE}/c1_full.tsv': b'c1 stamp',
                 f'nxnative/dm/host/gen/{kit.TITLE}/game_profile.h': b'synthetic header'}
        for name, data in files.items():
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)

    def test_capture_selects_only_rebuild_inputs_and_no_keys_or_romfs(self):
        with patch.object(kit.subprocess, 'check_output', return_value=kit.PIN):
            files = kit.collect(self.root)
        self.assertIn('patched/main.patched.bin', files)
        self.assertIn('Gen/dm/env.txt', files)
        self.assertFalse(any('prod.keys' in n or 'RomFS' in n for n in files))

    def test_wrong_revision_and_incomplete_profile_fail_before_export(self):
        with patch.object(kit.subprocess, 'check_output', return_value='0' * 40):
            with self.assertRaises(ValueError):
                kit.collect(self.root)
        (self.gen / 'dm/c1_full.tsv').write_bytes(b'another build')
        with patch.object(kit.subprocess, 'check_output', return_value=kit.PIN):
            with self.assertRaisesRegex(ValueError, 'profile'):
                kit.collect(self.root)

    def test_symlink_and_total_bound_fail_closed(self):
        (self.gen / 'dm/link.txt').symlink_to(self.root / 'oot2-work/extract/v131072/RomFS.img')
        with patch.object(kit.subprocess, 'check_output', return_value=kit.PIN):
            with self.assertRaisesRegex(ValueError, 'symlink'):
                kit.collect(self.root)
        (self.gen / 'dm/link.txt').unlink()
        with patch.object(kit.subprocess, 'check_output', return_value=kit.PIN), patch.object(kit, 'LIMIT', 1):
            with self.assertRaises(ValueError):
                kit.collect(self.root)

    def test_fixed_upload_route_preserves_other_destinations(self):
        old = gate.OUTPUT
        with patch.object(gate, 'receive_file') as receive:
            self.assertEqual(gw.dispatch('oot2-write-host-kit-v1', gate), 0)
            receive.assert_called_once_with('OOT2HostKit-v4.tar.zst', 1 << 30)
            self.assertEqual(gw.dispatch('oot2-write-host-kit-v1 /tmp/x', gate), 126)
            receive.reset_mock()
            self.assertEqual(gw.dispatch('oot2-write-host-kit-v5', gate), 0)
            receive.assert_called_once_with('OOT2HostKit-v5.tar.zst', 1 << 30)
        self.assertEqual(gate.OUTPUT, old)

    def test_ipad_v5_kit_is_bound_to_its_shader_chain_and_recipe(self):
        with patch.dict(os.environ, {'OOT2_RUNTIME_VARIANT': 'ipad-v5'}):
            pin, chain, recipe = kit.build_identity()
            self.assertEqual(len(recipe), 64)
            header = self.source / 'dm/gfx/nvn/dmsh_chain.h'
            with patch.object(kit.subprocess, 'check_output', return_value=pin):
                with self.assertRaisesRegex(ValueError, 'revision/chain'):
                    kit.collect(self.root)
                header.write_text(f'#define DMSH_CHAIN "{chain}"')
                self.assertIn('patched/main.fixups.tsv', kit.collect(self.root))

    @unittest.skipUnless(shutil.which('zstd'), 'zstd unavailable; input filtering tests still run')
    def test_real_archive_contains_checked_manifest_and_exact_bytes(self):
        out = self.root / 'kit.tar.zst'
        with patch.object(kit.subprocess, 'check_output', return_value=kit.PIN):
            kit.export(self.root, out)
        proc = subprocess.Popen(['zstd', '-q', '-d', '-c', str(out)], stdout=subprocess.PIPE)
        try:
            with tarfile.open(fileobj=proc.stdout, mode='r|') as archive:
                data = {m.name: archive.extractfile(m).read() for m in archive}
        finally:
            proc.stdout.close()
            self.assertEqual(proc.wait(), 0)
        manifest = json.loads(data.pop('manifest.json'))
        self.assertFalse(manifest['host_only_rebuild_validated'])
        self.assertEqual(set(data), set(manifest['files']))
        for name, content in data.items():
            self.assertEqual(hashlib.sha256(content).hexdigest(), manifest['files'][name]['sha256'])
        with self.assertRaises(ValueError):
            kit.export(self.root, out)
