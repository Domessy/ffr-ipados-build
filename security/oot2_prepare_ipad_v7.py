#!/usr/bin/env python3
"""Prepare the official OOT2 ipad-v7 revision, without game data or builds.

The old pinned variants keep their own patches. Never apply those backports
on current upstream, which already contains their fixes.
"""
import argparse
import hashlib
from pathlib import Path
import subprocess

from oot2_patch_nup_release import patch as release_nup

PIN = '2f131edc1b4586f89dd20b0d3de8e4f92ac3f74b'
CHAIN = 'bc8830d4ba5a'
ORIGINALS = {
    "dm/gfx/nvn/nvn_mtl.m": "55e615251547a310c1f037d19287f7f8dd9b95566d27771ae1648296d35bbbf2",
    "dm/gfx/nvn/dmsh_chain.h": "bbf170c3bda0833353235e00202a35a4648aa6e0dc096d3d0b3d04d4bf2961e0",
    "scripts/build_ipa_from_nsp.py": "5f0cab4aa0fee8ca39962da47cb5de181571e2ef83bbd33c4494456da0645513",
    "dm/gfx/nvn/hle_nvn.c": "bac8bb302c5716195ab5c16088e6a7ad05ee04ac72eeb137228debb77c2a8019",
    "dm/gfx/nvn/nvn_fstep.h": "86c7a24a4668932c25188b266660567ed9c61fe65c1ca654e9d611fe1e4345cd",
    "dm/gfx/tests/t_fstep.c": "fc17fd12d85bc8a8bf215db63e44a78be4ef9a5f84c3be9fbe89ab56a02ebced",
    "dm/games/0400486024DEC000/game.tsv": "1cbfe60e31db3367ac678d28602c1e585ddcebaeda66d89815d29cbb7e43b2a8"
}


def prepare(root):
    root = Path(root).resolve()
    head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if head != PIN:
        raise ValueError('ipad-v7 requires its exact 40-digit revision')
    for name, expected in ORIGINALS.items():
        p = root / name
        if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            raise ValueError('ipad-v7 source differs or was already prepared: ' + name)
    telemetry = Path(__file__).with_name('oot2_telemetry.patch')
    host = Path(__file__).with_name('oot2_ipad_v7_host.patch')
    if hashlib.sha256(host.read_bytes()).hexdigest() != '9fe39423ab72399e2692edd404edce1dc4cef6095d3382ddfff95efe13037696':
        raise ValueError('v7 host patch digest')
    subprocess.run(['git', '-C', str(root), 'apply', '--check', str(host)], check=True)
    subprocess.run(['git', '-C', str(root), 'apply', '--check', str(telemetry)], check=True)
    # The script hash above proves the release helper's source contract. Restore
    # both inputs if an unexpected helper/IO failure interrupts preparation.
    originals = {n: (root / n).read_bytes() for n in ORIGINALS}
    try:
        release_nup(root / 'scripts/build_ipa_from_nsp.py')
        subprocess.run(['git', '-C', str(root), 'apply', str(telemetry)], check=True)
        subprocess.run(['git', '-C', str(root), 'apply', str(host)], check=True)
    except Exception:
        for n, data in originals.items():
            (root / n).write_bytes(data)
        raise
    assert f'"{CHAIN}"' in (root / 'dm/gfx/nvn/dmsh_chain.h').read_text()
    print(f'OOT2 ipad-v7 prepared: {PIN}, original shader chain {CHAIN}; reviewed frame pacing #1942 and profile #1927, telemetry and runner NUP release; original shader chain preserved')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('checkout', type=Path)
    prepare(p.parse_args().checkout)
