#!/usr/bin/env python3
"""Apply host-only terrain coherency fixes after the audited memory-v1 overlay.

No shader edits, game inputs, implicit network or compilation. Start with a
fresh exact-pin checkout for every attempt; never reapply in a live build.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from oot2_patch_runtime import PIN

HERE = Path(__file__).resolve().parent


def apply(root):
    root = Path(root).resolve()
    manifest = json.loads((HERE/'oot2_terrain_manifest.json').read_text())
    head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if head != PIN:
        raise ValueError('Terrain patch requires the exact OOT2 upstream pin')
    for path, expected in manifest['originals'].items():
        if hashlib.sha256((root/path).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Terrain prerequisite differs or was already patched: {path}')
    patch = str(HERE/'oot2_terrain.patch')
    subprocess.run(['git', '-C', str(root), 'apply', '--check', patch], check=True)
    subprocess.run(['git', '-C', str(root), 'apply', patch], check=True)
    print('OOT2 terrain-v3 applied: storage ranges, CPU rewrites, shared edge pages, retained texture residency')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('checkout', type=Path)
    apply(p.parse_args().checkout)
