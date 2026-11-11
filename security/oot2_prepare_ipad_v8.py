#!/usr/bin/env python3
"""Prepare the official OOT2 ipad-v8 revision, without game data or builds.

The old pinned variants keep their own patches. Never apply those backports
on current upstream, which already contains their fixes.
"""
import argparse
import hashlib
from pathlib import Path
import subprocess

from oot2_patch_nup_release import patch as release_nup

PIN = 'ccd834e06a3938834bb5579e2ccc6a0ad13d3970'
CHAIN = 'd24f05cf9d78'
ORIGINALS = {
    "dm/gfx/nvn/nvn_mtl.m": "0084f9d988b41a7a8d291e239ea1ba3b0e03cd2e4025aed3587c133c2deedfb1",
    "dm/gfx/nvn/dmsh_chain.h": "e702728e36963f0cab3843bfe197142f49b363b8724ad1bfacd868035cb471cd",
    "scripts/build_ipa_from_nsp.py": "7724aa0dee54a9ccdfe626106168240a787b00a98397f2ed071ad3233baeeb7d",
    "dm/gfx/nvn/hle_nvn.c": "8abd1759a83e3114a67be3d37c9c95194ea1a7fe11c7837ec1e2f11a9b588d3a",
    "dm/gfx/nvn/nvn_fstep.h": "86c7a24a4668932c25188b266660567ed9c61fe65c1ca654e9d611fe1e4345cd",
    "dm/gfx/tests/t_fstep.c": "fc17fd12d85bc8a8bf215db63e44a78be4ef9a5f84c3be9fbe89ab56a02ebced",
    "dm/games/0400486024DEC000/game.tsv": "943dccf89a99d9fc89611695aae8fe95d8a37a284f87cc773aa57d1c6e37e68a"
}


def prepare(root):
    root = Path(root).resolve()
    head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if head != PIN:
        raise ValueError('ipad-v8 requires its exact 40-digit revision')
    for name, expected in ORIGINALS.items():
        p = root / name
        if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            raise ValueError('ipad-v8 source differs or was already prepared: ' + name)
    telemetry = Path(__file__).with_name('oot2_telemetry.patch')
    host = Path(__file__).with_name('oot2_ipad_v8_host.patch')
    if hashlib.sha256(host.read_bytes()).hexdigest() != '9fe39423ab72399e2692edd404edce1dc4cef6095d3382ddfff95efe13037696':
        raise ValueError('v8 host patch digest')
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
    print(f'OOT2 ipad-v8 prepared: {PIN}, original shader chain {CHAIN}; reviewed frame pacing #1942 and profile #1927, telemetry and runner NUP release; original shader chain preserved')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('checkout', type=Path)
    prepare(p.parse_args().checkout)
