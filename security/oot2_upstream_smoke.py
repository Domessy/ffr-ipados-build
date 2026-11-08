#!/usr/bin/env python3
"""Exercise upstream-v4 preparation on public source only, never game inputs."""
import argparse
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

import oot2_prepare_upstream as candidate


def run(source):
    with tempfile.TemporaryDirectory(prefix='oot2-upstream-smoke-') as temp:
        root = Path(temp)
        subprocess.run(['git', 'clone', '-q', '--shared', '--no-checkout', str(source), temp], check=True)
        subprocess.run(['git', '-C', temp, 'update-ref', 'HEAD', candidate.PIN], check=True)
        originals = {}
        for name in candidate.ORIGINALS:
            data = subprocess.check_output(['git', '-C', str(source), 'show', f'{candidate.PIN}:{name}'])
            p = root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            originals[name] = data
        script = root / 'scripts/build_ipa_from_nsp.py'
        script.write_bytes(originals['scripts/build_ipa_from_nsp.py'] + b'\n# tamper\n')
        before = {n: (root / n).read_bytes() for n in originals}
        try:
            candidate.prepare(root)
        except ValueError:
            pass
        else:
            raise AssertionError('modified builder must be rejected before mutation')
        assert before == {n: (root / n).read_bytes() for n in originals}
        script.write_bytes(originals['scripts/build_ipa_from_nsp.py'])
        def interrupted_release(path):
            path.write_text('interrupted helper')
            raise OSError('synthetic interruption')
        with patch.object(candidate, 'release_nup', interrupted_release):
            try:
                candidate.prepare(root)
            except OSError:
                pass
            else:
                raise AssertionError('interrupted helper should fail')
        assert originals == {n: (root / n).read_bytes() for n in originals}
        candidate.prepare(root)
        code = script.read_text()
        compile(code, str(script), 'exec')
        marker = '# OOT2_RUNNER_NUP_RELEASE_V1'
        assert code.count(marker) == 1
        assert code.index('aoc = extract_aoc(') < code.index(marker) < code.index('dlc_roms = sorted(')
        assert code.index('fam["nup"].close()') < code.index('candidate.unlink()')
        assert (root / 'dm/gfx/nvn/nvn_mtl.m').read_text().count('[oot2-mem] sample=') == 1
        assert (root / 'dm/gfx/nvn/dmsh_chain.h').read_bytes() == originals['dm/gfx/nvn/dmsh_chain.h']
        try:
            candidate.prepare(root)
        except ValueError:
            pass
        else:
            raise AssertionError('duplicate preparation must fail')
        subprocess.run(['git', '-C', temp, 'update-ref', 'HEAD', 'c229bd7d52e30f072362e31c7b1e3206d107d4cd'], check=True)
        try:
            candidate.prepare(root)
        except ValueError:
            pass
        else:
            raise AssertionError('old revision must be rejected')
    print('upstream-v4: exact source, tamper/duplicate/revision rejection, rollback, syntax and release order passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkout', type=Path)
    run(parser.parse_args().checkout)
