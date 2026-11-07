#!/usr/bin/env python3
"""Apply bounded host-only OOT2 experiments to the exact pinned source.

No shader-chain/profile changes; no game inputs, signing or build invocation.
The baseline is instrumented but keeps both upstream behaviours unchanged.
"""
import argparse
import hashlib
from pathlib import Path
import subprocess

PIN = 'c229bd7d52e30f072362e31c7b1e3206d107d4cd'
SOURCE = 'dm/gfx/nvn/nvn_mtl.m'
SOURCE_SHA256 = '693ca1f4edbbb4defee70e82be9da54cd3d2e06fd1c966a76b898b1c43689dc1'
VARIANTS = {
    'baseline': ('oot2_telemetry.patch',),
    'depth': ('oot2_telemetry.patch', 'oot2_depth_family.patch'),
    'memory-v1': ('oot2_telemetry.patch', 'oot2_depth_family.patch', 'oot2_end_alias.patch'),
}


def apply(root, variant):
    root = Path(root).resolve()
    head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if head != PIN:
        raise ValueError('Runtime patch requires the exact OOT2 upstream pin')
    if hashlib.sha256((root / SOURCE).read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError('Runtime source differs from pin (or already patched); refusing')
    patches = [str(Path(__file__).with_name(n)) for n in VARIANTS[variant]]
    # Check the complete set before any mutation. Git apply is atomic unless
    # --reject is requested, which is deliberately never used here.
    subprocess.run(['git', '-C', str(root), 'apply', '--check', *patches], check=True)
    subprocess.run(['git', '-C', str(root), 'apply', *patches], check=True)
    print(f'OOT2 runtime variant applied: {variant}; shader chain unchanged')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkout', type=Path)
    parser.add_argument('--variant', choices=VARIANTS, default='baseline')
    args = parser.parse_args()
    apply(args.checkout, args.variant)
