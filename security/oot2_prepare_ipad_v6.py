#!/usr/bin/env python3
"""Prepare the official OOT2 ipad-v6 revision, without game data or builds.

The old pinned variants keep their own patches. Never apply those backports
on current upstream, which already contains their fixes.
"""
import argparse
import hashlib
from pathlib import Path
import subprocess

from oot2_patch_nup_release import patch as release_nup

PIN = '8d5d4f1b04610fef5a96521c72a4263d68794959'
CHAIN = '0c434f1b68df'
ORIGINALS = {
    'dm/gfx/nvn/nvn_mtl.m': '1fce2702a55e8dc311b9e12bf1b354ec5874592dea10096607b1f411e75ef9b5',
    'dm/gfx/nvn/dmsh_chain.h': '3821c5387e36fbac9e4eb4f75724d14fa8c16d1fb36aac69e6ec63cdca4c3ca0',
    'scripts/build_ipa_from_nsp.py': '356e255fc710b8b9f0b06b015ef56599cd346f7908030b17e0e00f3d352d8e29',
}


def prepare(root):
    root = Path(root).resolve()
    head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if head != PIN:
        raise ValueError('ipad-v6 requires its exact 40-digit revision')
    for name, expected in ORIGINALS.items():
        p = root / name
        if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            raise ValueError('ipad-v6 source differs or was already prepared: ' + name)
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
    print(f'OOT2 ipad-v6 prepared: {PIN}, original shader chain {CHAIN}; telemetry and runner NUP release only')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('checkout', type=Path)
    prepare(p.parse_args().checkout)
