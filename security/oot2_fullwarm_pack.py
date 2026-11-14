#!/usr/bin/env python3
"""Add complete R/M archives and rebuilt host; preserve every other IPA byte."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import stat
import struct
import tempfile
import zipfile
try:
    from .oot2_ipad_aot import CHAIN, GPU, check_bundle, digest, inspect_ipa
    from .oot2_fullwarm import validate_render_coverage
    from .oot2_local_bundle import validate_zip_headers, extra_fields
except ImportError:
    from oot2_ipad_aot import CHAIN, GPU, check_bundle, digest, inspect_ipa
    from oot2_fullwarm import validate_render_coverage
    from oot2_local_bundle import validate_zip_headers, extra_fields


def check_full_bundle(bundle):
    bundle = Path(bundle); report = json.loads((bundle / 'fullwarm.json').read_text())
    c = report['coverage']
    validate_render_coverage(c)
    if (report['chain'] != CHAIN or report['gpu'] != GPU or report['platform'] != 'ios'
        or c['failed_tasks'] or not c['render_rows'] or not c['mesh_rows']
        or c['mesh_rows'] != c['emitted_mesh']
        or c['periods'] != len(report['archives'])): raise ValueError('full prewarm coverage')
    for name, meta in report['archives'].items():
        path = bundle / name
        if (not re.fullmatch(GPU + r'-prewarm-[0-9]{5}\.mtl4a', name) or path.is_symlink()
            or path.stat().st_size < 32 or path.stat().st_size != meta['bytes'] or digest(path) != meta['sha256']):
            raise ValueError('full prewarm archive identity')
    allowed = set(report['archives']) | {'fullwarm.json', 'prewarm.tsv'}
    if {p.name for p in bundle.iterdir()} != allowed: raise ValueError('unexpected full prewarm file')
    return report


def base_resources(base):
    base = Path(base)
    required = {GPU + '.mtl4a', 'prebuilt.tsv', 'archive.tsv'}
    names = {path.name for path in base.iterdir()}
    if not required <= names or names - required - {'rest_pairs.tsv'}:
        raise ValueError('base pipeline resource set')
    files = sorted(base / name for name in names)
    for path in files:
        if path.is_symlink() or not path.is_file():
            raise ValueError('base pipeline resource type: ' + path.name)
    check_bundle(base)
    rest = re.search(r'^rest\t([0-9]+)$', (base/'archive.tsv').read_text(), re.M)
    if not rest: raise ValueError('base pipeline rest count missing')
    # pso_offline deliberately removes this file when there are no remaining
    # pairs. Require it only when the producer reports actual remaining work.
    if int(rest[1]) and 'rest_pairs.tsv' not in names:
        raise ValueError('remaining pipeline pairs missing')
    return files


def repack(slim, base, full, host, output):
    slim, base, full, host, output = map(Path, (slim, base, full, host, output))
    prefix = inspect_ipa(slim); files = base_resources(base); report = check_full_bundle(full)
    files += sorted(full.iterdir())
    for path in files:
        if path.is_symlink() or not path.is_file(): raise ValueError("pipeline resource type: " + path.name)
    if report.get('host') and report['host']['sha256'] != digest(host): raise ValueError('full prewarm host identity')
    raw = host.read_bytes()
    if len(raw) < 32 or struct.unpack_from('<III', raw) != (0xfeedfacf, 0x100000c, 0):
        # arm64e and other architectures are intentionally outside this recipe.
        raise ValueError('rebuilt host must be arm64 Mach-O')
    if struct.unpack_from('<I', raw, 12)[0] != 2: raise ValueError('host is not executable')
    if output.exists() or output.is_symlink(): raise ValueError('full IPA output exists')
    output.parent.mkdir(parents=True, exist_ok=True)
    # Budget the uncompressed original plus every pipeline and a conservative
    # ZIP/header reserve. Fail before writing a multi-GB partial IPA.
    with zipfile.ZipFile(slim) as source:
        originals = sum(item.file_size for item in source.infolist())
        entries = len(source.infolist())
    pipelines = sum(path.stat().st_size for folder in (base, full) for path in folder.iterdir() if path.is_file())
    required = originals + host.stat().st_size + pipelines + (entries + 64) * 65536 + (1 << 30)
    free = shutil.disk_usage(output.parent).free
    print(f'Full IPA disk budget: free={free / 1024**3:.2f} GiB required={required / 1024**3:.2f} GiB', flush=True)
    if free < required:
        raise ValueError(f'insufficient disk for full IPA: free={free} required={required}')
    fd, temporary = tempfile.mkstemp(prefix='.oot2-fullwarm-', dir=output.parent); os.close(fd)
    hashes = {}; replaced = []
    try:
        with zipfile.ZipFile(slim) as src, zipfile.ZipFile(temporary, 'w', allowZip64=True) as dst:
            executable = prefix + plistlib.loads(src.read(prefix + 'Info.plist'))['CFBundleExecutable']
            for item in src.infolist():
                if item.filename.startswith(prefix + 'pso/'):
                    raise ValueError('use original pipeline-free v8 input')
                if '/_CodeSignature/' in item.filename or item.filename.endswith('/embedded.mobileprovision'):
                    raise ValueError('input must be unsigned')
                target = copy.copy(item)
                target.extra = b''.join(struct.pack('<HH', k, len(v)) + v for k, v in extra_fields(item.extra) if k != 1)
                h = hashlib.sha256()
                with (host.open('rb') if item.filename == executable else src.open(item)) as inp, dst.open(target, 'w', force_zip64=True) as out:
                    while block := inp.read(8 << 20): out.write(block); h.update(block)
                if not item.is_dir(): hashes[item.filename] = h.hexdigest()
                if item.filename == executable: replaced.append(item.filename)
            for path in files:
                if path.is_symlink() or not path.is_file(): raise ValueError('pipeline resource type')
                item = zipfile.ZipInfo(prefix + 'pso/' + path.name)
                item.external_attr = (stat.S_IFREG | 0o644) << 16; item.compress_type = zipfile.ZIP_STORED
                with path.open('rb') as inp, dst.open(item, 'w', force_zip64=True) as out: shutil.copyfileobj(inp, out, 8 << 20)
                hashes[item.filename] = digest(path)
        if replaced != [executable]: raise ValueError('host replacement missing')
        validate_zip_headers(temporary)
        with zipfile.ZipFile(temporary) as z:
            if len(z.namelist()) != len(set(z.namelist())): raise ValueError('duplicate full IPA entry')
            for name, expected in hashes.items():
                h = hashlib.sha256()
                with z.open(name) as inp:
                    while block := inp.read(8 << 20): h.update(block)
                if h.hexdigest() != expected: raise ValueError('full IPA resource changed')
        os.chmod(temporary, 0o600); os.replace(temporary, output)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {'chain': CHAIN, 'gpu': GPU, 'platform': 'ios', 'scope': 'bases, compute and full recorded R/M lists',
            'coverage': report['coverage'], 'host_sha256': digest(host), 'ipa_bytes': output.stat().st_size,
            'verified_files': len(hashes), 'original_resources_preserved_except_executable': True}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('slim', 'base', 'full', 'host', 'output'): p.add_argument(name, type=Path)
    a = p.parse_args(); print(json.dumps(repack(a.slim, a.base, a.full, a.host, a.output)))
