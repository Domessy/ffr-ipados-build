#!/usr/bin/env python3
"""Build iOS pair/compute archives from the verified v8 slim IPA, without a NUP.

The executable and shader image are copied unchanged. Full R/M prewarm-list
pipelines are a separate feature, not implemented by this optimization.
"""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import plistlib
import re
import shutil
import stat
import struct
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile

try:
    from .oot2_local_bundle import validate_zip_headers, extra_fields
except ImportError:
    from oot2_local_bundle import validate_zip_headers, extra_fields

CHAIN = 'd24f05cf9d78'
GPU = 'applegpu_g17g'
TABLES = ('shader_pairs.tsv', 'pso_pairs.tsv', 'shader_map.tsv', 'pso_manifest.tsv')
MAX_CACHE = 12 << 30


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        while block := source.read(8 << 20): h.update(block)
    return h.hexdigest()


def prepare_tools(root):
    root = Path(root)
    here = Path(__file__).parent
    meta = json.loads((here / 'oot2_aot_v8_manifest.json').read_text())
    if subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip() != meta['base']:
        raise ValueError('AOT requires the original v8 pin')
    patch = here / 'oot2_aot_v8_tools.patch'
    if digest(patch) != meta['patch_sha256']: raise ValueError('AOT patch identity')
    for name, expected in meta['originals'].items():
        if (root / name).is_symlink() or digest(root / name) != expected:
            raise ValueError('AOT input tool changed')
    subprocess.run(['git', '-C', str(root), 'apply', '--check', str(patch.resolve())], check=True)
    subprocess.run(['git', '-C', str(root), 'apply', str(patch.resolve())], check=True)


def inspect_ipa(path):
    validate_zip_headers(path)
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if len(names) != len(set(names)): raise ValueError('duplicate IPA members')
        infos = [n for n in names if n.startswith('Payload/') and n.endswith('.app/Info.plist') and n.count('/') == 2]
        if len(infos) != 1: raise ValueError('IPA app layout')
        prefix = infos[0][:-len('Info.plist')]
        for item in z.infolist():
            if ('..' in Path(item.filename).parts or '\\' in item.filename or item.flag_bits & 1
                or stat.S_ISLNK(item.external_attr >> 16)
                or not (item.filename.startswith(prefix) or (item.is_dir() and prefix.startswith(item.filename)))):
                raise ValueError('IPA member path/type')
        info = plistlib.loads(z.read(infos[0]))
        if info.get('CFBundleIdentifier') != 'org.nxnative.0400486024dec000': raise ValueError('IPA title')
        if not z.getinfo(prefix + info['CFBundleExecutable']).file_size: raise ValueError('IPA executable')
        if prefix + 'romfs.img' in names: raise ValueError('AOT requires the slim input')
        z.getinfo(prefix + f'msl/b-{CHAIN}.img')
        for table in TABLES: z.getinfo(prefix + 'dm/' + table)
        return prefix


def extract_inputs(slim, output):
    prefix = inspect_ipa(slim)
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(slim) as z:
        for name in [f'msl/b-{CHAIN}.img'] + ['dm/' + x for x in TABLES]:
            dest = output / name; dest.parent.mkdir(parents=True, exist_ok=True)
            with z.open(prefix + name) as src, dest.open('wb') as dst: shutil.copyfileobj(src, dst, 8 << 20)
    return output


def compiler_command(root, inputs, cache):
    root, inputs, cache = map(Path, (root, inputs, cache))
    # Use the actual packed tables, including pso_pairs emitted by the split.
    return [sys.executable, str(root / 'dm/gfx/tools/pso_offline.py'),
            '--pairs', str(inputs / 'dm/shader_pairs.tsv'), '--pairs', str(inputs / 'dm/pso_pairs.tsv'),
            '--shader-map', str(inputs / 'dm/shader_map.tsv'), '--manifest', str(inputs / 'dm/pso_manifest.tsv'),
            '--msl', str(inputs / f'msl/b-{CHAIN}'), '--out', str(cache / 'bundle'), '--work', str(cache / 'work'),
            '--gpu', GPU, '--platform', 'ios', '--os-min', '27.0', '--depth', 'gl', '--jobs', '2']


def check_bundle(folder):
    folder = Path(folder)
    archive = folder / (GPU + '.mtl4a')
    if archive.is_symlink() or not archive.is_file() or archive.stat().st_size < 32: raise ValueError('AOT archive missing')
    meta = (folder / 'archive.tsv').read_text()
    if not re.search(r'^platform\tios\t27\.0$', meta, re.M): raise ValueError('AOT platform')
    if not re.search(r'^arch\t' + GPU + '$', meta, re.M): raise ValueError('AOT GPU')
    if CHAIN not in (folder / 'prebuilt.tsv').read_text(): raise ValueError('AOT chain')
    if not re.search(r'^bases\t[1-9][0-9]*$', meta, re.M): raise ValueError('AOT contains no render base')
    return archive


def compile_archive(root, slim, work):
    work = Path(work); work.mkdir(parents=True, exist_ok=True)
    inputs = extract_inputs(slim, work / 'inputs')
    cache = work / 'cache'; cache.mkdir(exist_ok=True)
    log = work / 'aot-private.log'
    started = time.monotonic()
    with log.open('wb') as output:
        proc = subprocess.Popen(compiler_command(root, inputs, cache), stdout=output, stderr=subprocess.STDOUT)
        while True:
            try: rc = proc.wait(timeout=30); break
            except subprocess.TimeoutExpired:
                count = sum(1 for p in (cache / 'work').glob('batches.*/*/key.*'))
                print(f'AOT iOS: elapsed={int(time.monotonic()-started)}s; cached_batches={count}; log_bytes={log.stat().st_size}', flush=True)
    if rc: raise RuntimeError('AOT compiler failed; diagnostic remains private')
    check_bundle(cache / 'bundle')
    return cache / 'bundle'


def repack(slim, bundle, output):
    slim, bundle, output = map(Path, (slim, bundle, output))
    prefix = inspect_ipa(slim); check_bundle(bundle)
    if output.exists() or output.is_symlink(): raise ValueError('output already exists')
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.oot2-aot-', dir=output.parent); os.close(fd)
    hashes = {}
    try:
        with zipfile.ZipFile(slim) as src, zipfile.ZipFile(tmp, 'w', allowZip64=True) as dst:
            if any(n.startswith(prefix + 'pso/') for n in src.namelist()): raise ValueError('input already has pipelines')
            for item in src.infolist():
                target = copy.copy(item)
                target.extra = b''.join(struct.pack('<HH', k, len(v)) + v for k, v in extra_fields(item.extra) if k != 1)
                h = hashlib.sha256()
                with src.open(item) as inp, dst.open(target, 'w', force_zip64=True) as out:
                    while block := inp.read(8 << 20): out.write(block); h.update(block)
                if not item.is_dir(): hashes[item.filename] = h.hexdigest()
            for path in sorted(bundle.iterdir()):
                if path.is_symlink() or not path.is_file(): raise ValueError('AOT bundle entry type')
                if path.name not in (GPU + '.mtl4a', 'prebuilt.tsv', 'rest_pairs.tsv', 'archive.tsv'): raise ValueError('AOT bundle entry name')
                item = zipfile.ZipInfo(prefix + 'pso/' + path.name)
                item.external_attr = (stat.S_IFREG | 0o644) << 16; item.compress_type = zipfile.ZIP_STORED
                with path.open('rb') as inp, dst.open(item, 'w', force_zip64=True) as out: shutil.copyfileobj(inp, out, 8 << 20)
        validate_zip_headers(tmp)
        # Reread the output: the executable, translated shaders and defaults must
        # remain byte-identical, not merely have the same names and sizes.
        with zipfile.ZipFile(tmp) as z:
            for name, expected in hashes.items():
                h = hashlib.sha256()
                with z.open(name) as f:
                    while block := f.read(8 << 20): h.update(block)
                if h.hexdigest() != expected: raise ValueError('AOT changed an original resource')
        os.chmod(tmp, 0o600); os.replace(tmp, output)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return {'chain': CHAIN, 'gpu': GPU, 'platform': 'ios', 'ipa_bytes': output.stat().st_size,
            'original_resources_verified': len(hashes), 'scope': 'pair bases and compute; full R/M prewarm lists remain on device'}


def save_cache(folder, archive):
    folder, archive = Path(folder), Path(archive)
    total = sum(p.stat().st_size for p in folder.rglob('*') if p.is_file())
    if total > MAX_CACHE: raise ValueError('AOT cache exceeds limit')
    with tarfile.open(archive, 'w:gz', compresslevel=1) as out:
        for p in sorted(folder.rglob('*')):
            rel = p.relative_to(folder)
            # Compiler scratch libraries are large, reproducible and often left
            # after interruption. Save compiled groups and their exact keys only.
            if 'libraries' in rel.parts or p.suffix in ('.log', '.partial', '.mtl4-json'): continue
            if p.is_symlink(): raise ValueError('AOT cache symlink')
            if p.is_file(): out.add(p, arcname=rel.as_posix(), recursive=False)


def restore_cache(archive, folder):
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, 'r:gz') as src:
        members = src.getmembers(); total = 0; seen = set()
        for m in members:
            p = Path(m.name); total += m.size
            if not m.isfile() or p.is_absolute() or '..' in p.parts or '\\' in m.name or total > MAX_CACHE:
                raise ValueError('invalid AOT cache member')
            if p.parts[0] not in ('work', 'bundle'): raise ValueError('invalid AOT cache root')
            if m.name in seen: raise ValueError('duplicate AOT cache member')
            seen.add(m.name)
        if len(members) > 20000: raise ValueError('too many AOT cache members')
        for m in members:
            dest = folder / m.name; dest.parent.mkdir(parents=True, exist_ok=True)
            with src.extractfile(m) as inp, dest.open('wb') as out: shutil.copyfileobj(inp, out)


def private_diagnostic(root):
    root = Path(root)
    files = [root / 'wrapper-private.log', root / 'work/aot-private.log', root / 'work/aot-result.json']
    files += sorted((root / 'work/cache/work').rglob('*.log'))
    parts = []; left = 24 << 20
    for path in files:
        if not path.is_file() or path.is_symlink() or left <= 0: continue
        take = min(left, 2 << 20, path.stat().st_size)
        with path.open('rb') as f:
            f.seek(max(0, path.stat().st_size - take)); parts.append(f.read())
        parts.append(b'\n'); left -= take + 1
    return b''.join(parts)


def public_progress(work):
    work = Path(work); log = work / 'aot-private.log'
    text = ''
    if log.is_file():
        with log.open('rb') as source: text = source.read(65536).decode('utf8', errors='replace')
    bases = re.search(r'pso_offline: \d+ pairs: (\d+) bases,', text)
    computes = re.search(r'pso_offline: \d+ compute shaders: (\d+) compute pipelines,', text)
    total = math.ceil(int(bases[1]) / 1000) + math.ceil(int(computes[1]) / 16) if bases and computes else 0
    groups = list((work / 'cache/work').glob('batches.*/*/key.*'))
    done = len(groups)
    size = sum(p.stat().st_size for p in (work / 'cache/work').glob('batches.*/*/*.mtl4a') if p.is_file())
    return {'completed_batches': done, 'total_batches': total,
            'percent': min(100, round(100 * done / total, 1)) if total else 0,
            'compiled_archive_gib': round(size / 1024**3, 2)}


def save_completed_cache(folder, archive):
    """Checkpoint committed groups during compilation, never an in-flight binary.

    compile_batch removes its key before replacing a binary, and publishes the
    new key last. Check both before and after streaming a group into the tar.
    A race discards the entire checkpoint; a later checkpoint retries it.
    """
    folder, archive = Path(folder), Path(archive)
    temp = archive.with_name(archive.name + '.partial')
    try:
        with tarfile.open(temp, 'w:gz', compresslevel=1) as out:
            for key in sorted((folder / 'work').glob('batches.*/*/key.*')):
                binary = key.parent / (key.name.removeprefix('key.') + '.mtl4a')
                if not binary.is_file() or binary.is_symlink() or key.is_symlink(): continue
                kb = key.read_bytes(); before = binary.stat()
                files = [binary, key] + list(key.parent.glob('failed.*.tsv'))
                for path in files: out.add(path, arcname=path.relative_to(folder).as_posix(), recursive=False)
                after = binary.stat()
                if key.read_bytes() != kb or (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
                    raise ValueError('AOT group changed during checkpoint')
        if temp.stat().st_size > MAX_CACHE: raise ValueError('AOT checkpoint exceeds limit')
        os.replace(temp, archive)
    finally:
        temp.unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__); sub = ap.add_subparsers(dest='mode', required=True)
    p = sub.add_parser('prepare-tools'); p.add_argument('root', type=Path)
    for mode in ('build', 'build-cache'):
        p = sub.add_parser(mode); p.add_argument('root', type=Path); p.add_argument('slim', type=Path); p.add_argument('work', type=Path)
        if mode == 'build': p.add_argument('output', type=Path)
    for name in ('save-cache', 'restore-cache', 'save-completed-cache'):
        p = sub.add_parser(name); p.add_argument('source', type=Path); p.add_argument('destination', type=Path)
    a = ap.parse_args()
    if a.mode == 'prepare-tools': prepare_tools(a.root)
    elif a.mode == 'save-cache': save_cache(a.source, a.destination)
    elif a.mode == 'restore-cache': restore_cache(a.source, a.destination)
    elif a.mode == 'save-completed-cache': save_completed_cache(a.source, a.destination)
    else:
        bundle = compile_archive(a.root, a.slim, a.work)
        if a.mode == 'build-cache':
            print('AOT archive cache verified; intermediate IPA omitted.', flush=True)
            return
        result = repack(a.slim, bundle, a.output)
        (a.work / 'aot-result.json').write_text(json.dumps(result, indent=2) + '\n')
        print('AOT slim IPA packed; original resources verified.', flush=True)


if __name__ == '__main__': main()
