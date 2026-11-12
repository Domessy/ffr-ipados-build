#!/usr/bin/env python3
"""Prepare the hash-locked v8 runtime loader and CPU-only full-list exporter."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from oot2_prepare_ipad_v8 import prepare as prepare_runtime
from oot2_ipad_aot import prepare_tools


def prepare(root):
    root = Path(root).resolve(); here = Path(__file__).parent
    meta = json.loads((here / 'oot2_fullwarm_manifest.json').read_text())
    # These routines verify the original pin and their complete input hashes.
    prepare_runtime(root); prepare_tools(root)
    for name, expected in meta['prepared_originals'].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError('full prewarm prepared source differs: ' + name)
    patch = here / 'oot2_fullwarm_native.patch'
    if hashlib.sha256(patch.read_bytes()).hexdigest() != meta['patch_sha256']: raise ValueError('full prewarm patch digest')
    subprocess.run(['git', '-C', str(root), 'apply', '--check', str(patch.resolve())], check=True)
    for source, destination in meta['files'].items():
        data = (here / source).read_bytes()
        if hashlib.sha256(data).hexdigest() != destination['sha256']: raise ValueError('full prewarm payload digest')
        if (root / destination['path']).exists(): raise ValueError('full prewarm payload already present')
    subprocess.run(['git', '-C', str(root), 'apply', str(patch.resolve())], check=True)
    for source, destination in meta['files'].items(): shutil.copy2(here / source, root / destination['path'])
    print('Full-list exporter and runtime loader prepared; original v8 shader chain retained.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('root', type=Path)
    prepare(p.parse_args().root)
