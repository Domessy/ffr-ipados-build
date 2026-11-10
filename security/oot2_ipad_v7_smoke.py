#!/usr/bin/env python3
"""Exercise ipad-v7 preparation on public source only, never game inputs."""
import argparse
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

import oot2_prepare_ipad_v7 as candidate


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
        assert 'fps_hold\toff' in (root / 'dm/games/0400486024DEC000/game.tsv').read_text()
        # The PR's new regression cases fail with the official baseline header.
        # This verifies the pacing bug, not just that the patch text applied.
        import shutil
        cc = shutil.which('cc')
        if cc is None: raise AssertionError('C compiler required for pacing validation')
        subprocess.run([cc, '-O1', '-Wall', str(root/'dm/gfx/tests/t_fstep.c'), '-o', str(root/'candidate-fstep'), '-lm'], check=True)
        good = subprocess.run([str(root/'candidate-fstep')], capture_output=True, text=True)
        assert good.returncode == 0, good.stdout + good.stderr
        control = root/'control/dm/gfx'
        (control/'tests').mkdir(parents=True); (control/'nvn').mkdir()
        (control/'tests/t_fstep.c').write_bytes((root/'dm/gfx/tests/t_fstep.c').read_bytes())
        # Compatibility fields only; original controller ignores both inputs.
        baseline_header = originals['dm/gfx/nvn/nvn_fstep.h'].decode().replace('typedef struct {', 'typedef struct { int gpu_on; double gpu;', 1)
        (control/'nvn/nvn_fstep.h').write_text(baseline_header)
        subprocess.run([cc, '-O1', '-Wall', str(control/'tests/t_fstep.c'), '-o', str(root/'baseline-fstep'), '-lm'], check=True)
        bad = subprocess.run([str(root/'baseline-fstep')], capture_output=True, text=True)
        assert bad.returncode != 0, 'new cases must expose original pacing failure'
        print('Frame pacing: candidate passes; new cases fail against baseline header')

        try:
            candidate.prepare(root)
        except ValueError:
            pass
        else:
            raise AssertionError('duplicate preparation must fail')
        # A shallow CI clone need not contain the old pin. Make an unrelated
        # public synthetic revision locally so this rejection test is complete
        # without depending on dangling objects surviving a clone.
        tree = subprocess.check_output(['git', '-C', temp, 'mktree'], input='', text=True).strip()
        other = subprocess.check_output(
            ['git', '-C', temp, '-c', 'user.name=OOT2 Test', '-c',
             'user.email=oot2-test@example.invalid', 'commit-tree', tree],
            input='synthetic revision rejection fixture\n', text=True).strip()
        subprocess.run(['git', '-C', temp, 'update-ref', 'HEAD', other], check=True)
        try:
            candidate.prepare(root)
        except ValueError:
            pass
        else:
            raise AssertionError('old revision must be rejected')
    print('ipad-v7: exact source, tamper/duplicate/revision rejection, rollback, syntax and release order passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkout', type=Path)
    run(parser.parse_args().checkout)
