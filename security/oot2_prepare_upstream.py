#!/usr/bin/env python3
"""Prepare the opt-in OOT2 upstream-v4 revision, without game data or builds.

The old pinned variants keep their own patches. Never apply those backports
on current upstream, which already contains their fixes.
"""
import argparse
import hashlib
from pathlib import Path
import subprocess

from oot2_patch_nup_release import patch as release_nup

PIN = '1794a35a1a2462a75cb1730eee29d32fac81248c'
CHAIN = '579d06bf3932'
ORIGINALS = {
    'dm/gfx/nvn/nvn_mtl.m': '5339426f0ac8ca85044d4d5ac4703f9b1bdd4c87adb50451db2d61bef1ccf750',
    'dm/gfx/nvn/dmsh_chain.h': '4602c9c3ef8a0b4678c32d99d40d4ec94edb5794ec64d80497b187dbe1bb2ed4',
    'scripts/build_ipa_from_nsp.py': 'e39783c5949ba93aaf69ae438055aeb492ea0e8e875316cffeb398d4091fe22f',
}


def prepare(root):
    root = Path(root).resolve()
    head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if head != PIN:
        raise ValueError('upstream-v4 requires its exact 40-digit revision')
    for name, expected in ORIGINALS.items():
        p = root / name
        if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            raise ValueError('upstream-v4 source differs or was already prepared: ' + name)
    telemetry = Path(__file__).with_name('oot2_telemetry.patch')
    subprocess.run(['git', '-C', str(root), 'apply', '--check', str(telemetry)], check=True)
    # The script hash above proves the release helper's source contract. Restore
    # both inputs if an unexpected helper/IO failure interrupts preparation.
    originals = {n: (root / n).read_bytes() for n in ORIGINALS}
    try:
        release_nup(root / 'scripts/build_ipa_from_nsp.py')
        subprocess.run(['git', '-C', str(root), 'apply', str(telemetry)], check=True)
    except Exception:
        for n, data in originals.items():
            (root / n).write_bytes(data)
        raise
    assert f'"{CHAIN}"' in (root / 'dm/gfx/nvn/dmsh_chain.h').read_text()
    print(f'OOT2 upstream-v4 prepared: {PIN}, original shader chain {CHAIN}; telemetry and runner NUP release only')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('checkout', type=Path)
    prepare(p.parse_args().checkout)
