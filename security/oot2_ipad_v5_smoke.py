#!/usr/bin/env python3
"""Public-source preparation and rollback checks for the iPad candidate."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

import oot2_prepare_ipad_v5 as candidate


def run(source):
    manifest = json.loads((candidate.HERE / 'oot2_ipad_v5_manifest.json').read_text())
    with tempfile.TemporaryDirectory(prefix='oot2-ipad-v5-smoke-') as temp:
        root = Path(temp).resolve()
        subprocess.run(['git', 'clone', '-q', '--shared', str(source), str(root)], check=True)
        subprocess.run(['git', '-C', str(root), 'checkout', '-q', '--detach', candidate.PIN], check=True)
        originals = {name: (root / name).read_bytes() if (root / name).exists() else None
                     for name in manifest['files']}
        script = root / 'scripts/build_ipa_from_nsp.py'
        script.write_bytes(originals['scripts/build_ipa_from_nsp.py'] + b'\n# tamper\n')
        try:
            candidate.prepare(root)
        except ValueError:
            pass
        else:
            raise AssertionError('source tampering accepted')
        script.write_bytes(originals['scripts/build_ipa_from_nsp.py'])
        def interrupted(path):
            path.write_text('interrupted release helper')
            raise OSError('synthetic interruption')
        with patch.object(candidate, 'release_nup', interrupted):
            try:
                candidate.prepare(root)
            except OSError:
                pass
            else:
                raise AssertionError('interrupted preparation accepted')
        assert originals == {n: (root / n).read_bytes() if (root / n).exists() else None for n in originals}
        candidate.prepare(root)
        actual = subprocess.check_output(['python3', str(root / 'dm/gfx/tools/dmsh_chain.py')], text=True).strip()
        assert actual == candidate.CHAIN
        code = script.read_text()
        compile(code, str(script), 'exec')
        assert code.index('aoc = extract_aoc(') < code.index('# OOT2_RUNNER_NUP_RELEASE_V1') < code.index('dlc_roms = sorted(')
        assert (root / 'dm/gfx/nvn/nvn_mtl.m').read_text().count('[oot2-mem] sample=') == 1
        assert 'frag_z_snap' in (root / 'dm/gfx/tools/dmsh_build.py').read_text()
        assert (root / 'dm/gfx/tests/test_dmsh_extended_multiply.py').exists()
        try:
            candidate.prepare(root)
        except ValueError:
            pass
        else:
            raise AssertionError('duplicate preparation accepted')
        tree = subprocess.check_output(['git', '-C', str(root), 'mktree'], input='', text=True).strip()
        other = subprocess.check_output(['git', '-C', str(root), '-c', 'user.name=OOT2 Test',
                                         '-c', 'user.email=oot2-test@example.invalid', 'commit-tree', tree],
                                        input='synthetic wrong revision\n', text=True).strip()
        subprocess.run(['git', '-C', str(root), 'update-ref', 'HEAD', other], check=True)
        try:
            candidate.prepare(root)
        except ValueError:
            pass
        else:
            raise AssertionError('wrong pin accepted')
    print('ipad-v5: exact revision, input/output hashes, rollback, tamper/duplicate/revision rejection, shader chain and release order passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkout', type=Path)
    run(parser.parse_args().checkout)
