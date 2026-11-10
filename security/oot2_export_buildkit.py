#!/usr/bin/env python3
"""Save bounded private host-rebuild inputs after a successful full build.

This captures a future rebuild prerequisite, not a claim that host-only
reconstruction is already validated. Excludes NUP, RomFS, game shader images,
DerivedData, keys and arbitrary runner paths.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tarfile
import tempfile

TITLE = '0400486024DEC000'
PIN = '1794a35a1a2462a75cb1730eee29d32fac81248c'
CHAIN = '579d06bf3932'
LIMIT = 1 << 30


def build_identity():
    variant = os.environ.get('OOT2_RUNTIME_VARIANT', 'upstream-v4')
    if variant == 'upstream-v4':
        return PIN, CHAIN, None
    if variant in ('ipad-v5', 'ipad-v6', 'ipad-v7'):
        data = Path(__file__).with_name(f'oot2_{variant.replace("-", "_")}_manifest.json').read_bytes()
        manifest = json.loads(data)
        return manifest['base_revision'], manifest['shader_chain'], hashlib.sha256(data).hexdigest()
    raise ValueError('unsupported buildkit variant')


def collect(temp):
    temp = Path(temp).resolve()
    source, work = temp / 'nxnative', temp / 'oot2-work'
    head = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    pin, chain, _ = build_identity()
    if head != pin or f'"{chain}"' not in (source / 'dm/gfx/nvn/dmsh_chain.h').read_text():
        raise ValueError('buildkit revision/chain')
    patched = work / 'patched_v131072'
    gen = source / 'dm/ios/Gen'
    if not (patched / 'main.patched.bin').is_file() or not (gen / 'dm/c1_full.tsv').is_file():
        raise ValueError('buildkit inputs incomplete')
    profiles = [work / 'profile' / TITLE, source / 'dm/games' / TITLE]
    profile = next((p for p in profiles if (p / 'game.tsv').is_file()
                    and (p / 'c1_full.tsv').is_file()
                    and (p / 'c1_full.tsv').read_bytes() == (gen / 'dm/c1_full.tsv').read_bytes()), None)
    if profile is None:
        raise ValueError('matching build profile missing')
    files = {}
    def add(p, label):
        if any(q.is_symlink() for q in (p, *p.parents)):
            raise ValueError('buildkit symlink')
        if not stat.S_ISREG(p.stat().st_mode) or p.stat().st_size > LIMIT:
            raise ValueError('buildkit member')
        if any(w in p.name.casefold() for w in ('prod.keys', 'title.keys', '.pem', '.p12')):
            raise ValueError('buildkit forbidden input')
        files[label] = p
    for p in sorted(patched.iterdir()):
        if re.fullmatch(r'[A-Za-z0-9_-]+\.(?:patched\.bin|fixups\.tsv|gates\.tsv|cuts\.tsv|obs\.tsv)', p.name) or p.name == 'nro.tsv':
            add(p, 'patched/' + p.name)
    for base, label in ((gen / 'dm', 'Gen/dm'), (gen / 'Assets.xcassets', 'Gen/Assets.xcassets')):
        for p in sorted(base.rglob('*')):
            if p.is_symlink():
                raise ValueError('buildkit symlink')
            if p.is_file():
                add(p, label + '/' + p.relative_to(base).as_posix())
    add(gen / 'Info.plist', 'Gen/Info.plist')
    for p in sorted(profile.iterdir()):
        if p.suffix == '.tsv' or p.name == 'patches.py':
            add(p, 'profile/' + TITLE + '/' + p.name)
    header = source / 'dm/host/gen' / TITLE / 'game_profile.h'
    add(header, 'generated/game_profile.h')
    if 'patched/main.fixups.tsv' not in files or sum(p.stat().st_size for p in files.values()) > LIMIT:
        raise ValueError('buildkit incomplete or too large')
    return files


def export(temp, output):
    output = Path(output)
    if output.is_symlink() or output.exists() or output.parent.is_symlink():
        raise ValueError('buildkit output exists or symlink')
    files = collect(temp)
    pin, chain, recipe = build_identity()
    manifest = {'format': 1, 'title': TITLE, 'package': 'v131072', 'source_revision': pin,
                'shader_chain': chain, 'optimization_recipe_sha256': recipe,
                'host_only_rebuild_validated': False, 'files': {}}
    for label, p in files.items():
        manifest['files'][label] = {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.oot2-kit-', dir=output.parent)
    try:
        with os.fdopen(fd, 'wb') as compressed:
            proc = subprocess.Popen(['zstd', '-q', '-1', '-T0', '-c'], stdin=subprocess.PIPE, stdout=compressed)
            try:
                with tarfile.open(fileobj=proc.stdin, mode='w|') as tar:
                    data = json.dumps(manifest, sort_keys=True, indent=2).encode()
                    info = tarfile.TarInfo('manifest.json')
                    info.mode, info.size = 0o600, len(data)
                    tar.addfile(info, io.BytesIO(data))
                    for label, p in files.items():
                        data = p.read_bytes()
                        if hashlib.sha256(data).hexdigest() != manifest['files'][label]['sha256']:
                            raise ValueError('buildkit input changed')
                        info = tarfile.TarInfo(label)
                        info.mode, info.size = 0o600, len(data)
                        tar.addfile(info, io.BytesIO(data))
                proc.stdin.close()
                if proc.wait() != 0:
                    raise ValueError('buildkit compression')
            except BaseException:
                proc.stdin.close()
                proc.kill()
                proc.wait()
                raise
            compressed.flush()
            os.fsync(compressed.fileno())
        os.link(name, output)
    finally:
        os.unlink(name)
    print(f'OOT2_HOST_KIT_CAPTURED files={len(files)} compressed_bytes={output.stat().st_size}; host-only rebuild not yet validated')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runner_temp', type=Path)
    parser.add_argument('output', type=Path)
    a = parser.parse_args()
    export(a.runner_temp, a.output)
