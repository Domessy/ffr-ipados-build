#!/usr/bin/env python3
"""Prepare the immutable OOT2 iPad optimization candidate; never build game data."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from oot2_patch_nup_release import patch as release_nup

PIN = '7f50222003e4270e3655d4f798e85744d390edf0'
CHAIN = 'fb6cc361728e'
HERE = Path(__file__).resolve().parent


def prepare(root):
    root = Path(root).resolve()
    manifest = json.loads((HERE / 'oot2_ipad_v5_manifest.json').read_text())
    patch = HERE / 'oot2_ipad_v5.patch'
    if manifest['base_revision'] != PIN or manifest['shader_chain'] != CHAIN:
        raise ValueError('candidate manifest identity')
    if hashlib.sha256(patch.read_bytes()).hexdigest() != manifest['patch_sha256']:
        raise ValueError('candidate patch digest')
    head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if head != PIN:
        raise ValueError('ipad-v5 requires exact official revision')
    originals = {}
    for name, hashes in manifest['files'].items():
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('candidate path')
        p = root / name
        if any(q.is_symlink() for q in (p, *p.parents)):
            raise ValueError('candidate source symlink')
        data = p.read_bytes() if p.exists() else None
        if (hashlib.sha256(data).hexdigest() if data is not None else None) != hashes['before_sha256']:
            raise ValueError('candidate source differs or already prepared: ' + name)
        originals[name] = data
    telemetry = HERE / 'oot2_telemetry.patch'
    for file in (patch, telemetry):
        subprocess.run(['git', '-C', str(root), 'apply', '--check', str(file)], check=True)
    try:
        subprocess.run(['git', '-C', str(root), 'apply', str(patch)], check=True)
        for name, hashes in manifest['files'].items():
            if hashlib.sha256((root / name).read_bytes()).hexdigest() != hashes['after_sha256']:
                raise ValueError('candidate output digest: ' + name)
        actual = subprocess.check_output(['python3', str(root / 'dm/gfx/tools/dmsh_chain.py')], text=True).strip()
        if actual != CHAIN or f'"{CHAIN}"' not in (root / 'dm/gfx/nvn/dmsh_chain.h').read_text():
            raise ValueError('generated shader chain differs')
        release_nup(root / 'scripts/build_ipa_from_nsp.py')
        subprocess.run(['git', '-C', str(root), 'apply', str(telemetry)], check=True)
    except Exception:
        for name, data in originals.items():
            p = root / name
            if data is None:
                p.unlink(missing_ok=True)
            else:
                p.write_bytes(data)
        raise
    print(f'OOT2 ipad-v5 prepared: {PIN}; shader chain {CHAIN}; grass pre-pass requires unpublished generator and stays disabled.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkout', type=Path)
    prepare(parser.parse_args().checkout)
