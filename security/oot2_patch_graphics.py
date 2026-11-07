#!/usr/bin/env python3
"""Apply an opt-in, auditable OOT2 shader-chain experiment without building shaders.

The official translator objects must already have been fetched. No implicit
network, game inputs, cache deletion, signing or IPA compilation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
PIN = 'c229bd7d52e30f072362e31c7b1e3206d107d4cd'


def apply(root):
    root = Path(root).resolve()
    manifest = json.loads((HERE/'oot2_graphics_manifest.json').read_text())
    head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if head != PIN:
        raise ValueError('Graphics patch requires the exact OOT2 pin')
    for path, digest in manifest['originals'].items():
        if hashlib.sha256((root/path).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Graphics source differs from pin: {path}')
    blobs = {}
    for path, digest in manifest['files'].items():
        data = subprocess.check_output(['git', '-C', str(root), 'show', f"{manifest['source_commit']}:{path}"])
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('Official translator object fingerprint differs from audit')
        blobs[path] = data
    patch = str(HERE/'oot2_graphics.patch')
    subprocess.run(['git', '-C', str(root), 'apply', '--check', patch], check=True)
    subprocess.run(['git', '-C', str(root), 'apply', patch], check=True)
    for path, data in blobs.items():
        (root/path).write_bytes(data)
    # Never forge the old chain stamp or let the host accept old shader outputs.
    tool = str(root/'dm/gfx/tools/dmsh_chain.py')
    chain = subprocess.check_output(['python3', tool], text=True).strip()
    if chain != manifest['expected_chain']:
        raise ValueError('Shader chain differs from audited experiment; refusing build')
    subprocess.run(['python3', tool, '--header'], check=True)
    print('OOT2 graphics-v2 applied: LDSM, HMMA accumulator, mesh bounds, mesh invariance; NEW chain')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('checkout', type=Path)
    apply(p.parse_args().checkout)
