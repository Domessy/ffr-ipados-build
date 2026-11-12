#!/usr/bin/env python3
"""Stage an exact-code-fingerprint resume view without modifying any CAS entry."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
try:
    from .oot2_cache_snapshot import safe_dir, snapshot, cache_name
except ImportError:
    from oot2_cache_snapshot import safe_dir, snapshot, cache_name

HEX = re.compile(r'[0-9a-f]{64}\Z')

def stage(cache, conflicts, output, code_fp, include_metal=True):
    cache, conflicts, output = map(safe_dir, (cache, conflicts, output))
    if not HEX.fullmatch(code_fp) or output.exists():
        raise ValueError('resume identity or existing destination')
    selected = {}
    for base, conflict in ((cache, False), (conflicts, True)):
        for p in sorted((base / 'index').glob('*')):
            if p.is_symlink() or not p.is_file() or p.stat().st_size > 4096:
                raise ValueError('resume index')
            safe_dir(p.parent)
            label = p.name
            if conflict:
                match = re.fullmatch(r'([0-9a-f]+\.json)\.([0-9a-f]{64})\.conflict', label)
                if not match or hashlib.sha256(p.read_bytes()).hexdigest() != match[2]:
                    raise ValueError('resume conflict digest')
                label = match[1]
            d = json.loads(p.read_text())
            if d.get('code_fp') != code_fp:
                continue
            if not HEX.fullmatch(d.get('digest', '')) or not re.fullmatch(r'[0-9a-f]+\.json', label):
                raise ValueError('resume digest')
            previous = selected.get(label)
            if previous and previous[1] != d:
                raise ValueError('ambiguous resume index')
            selected[label] = (p, d)
    if not selected:
        raise ValueError('resume has no matching indices')
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='.resume-', dir=output.parent))
    counts = {'indices': len(selected), 'files': 0, 'bytes': 0, 'code_fp': code_fp, 'include_metal': include_metal}
    def link(p, name):
        safe_dir(p.parent)
        if p.is_symlink() or not p.is_file() or not cache_name(name, True):
            raise ValueError('resume member')
        dst = temp / name
        if dst.exists():
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.link(p, dst)
        counts['files'] += 1; counts['bytes'] += p.stat().st_size
    try:
        for name, (p, d) in selected.items():
            key = name[:-5]
            root = cache / 'shader' / d['digest']
            # Native cache_outputs needs Mac reflection/MSL and iOS reflection/library.
            for suffix in ('mac/' + key + '_b.json', 'mac/' + key + '_b.metal',
                           'ios/' + key + '_b.json', 'ios/' + key + '_b.metallib'):
                if not (root / suffix).is_file():
                    raise ValueError('incomplete translated shader')
            link(p, 'index/' + name)
            for f in root.rglob('*'):
                if f.is_symlink(): raise ValueError('resume symlink')
                if f.is_file(): link(f, f.relative_to(cache).as_posix())
        # Primary libraries are in shader/<digest>; retain side variants. The
        # optional compile namespace is unnecessary for an exact completed build.
        for ns in (('metallib', 'variant') if include_metal else ('variant',)):
            for f in (cache / ns).rglob('*'):
                if f.is_symlink(): raise ValueError('resume symlink')
                if f.is_file(): link(f, f.relative_to(cache).as_posix())
        (temp / 'resume.json').write_text(json.dumps(counts, indent=2)+'\n')
        os.rename(temp, output)
    finally:
        if temp.exists(): shutil.rmtree(temp)
    return counts

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('cache', type=Path); p.add_argument('conflicts', type=Path)
    p.add_argument('output', type=Path); p.add_argument('code_fp')
    a = p.parse_args()
    print(json.dumps(stage(a.cache, a.conflicts, a.output, a.code_fp), sort_keys=True))
