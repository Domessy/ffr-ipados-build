"""Validate private pipeline transfers before atomically publishing a cache.

Keep immutable previous versions; a failed restore or empty upload must never
replace the last useful checkpoint. No paths are supplied by the SSH client.
"""
import hashlib
import os
from pathlib import Path
import re
import tarfile
import uuid

MAX_CACHE = 12 << 30


def inspect_cache(path, fullwarm=False):
    with tarfile.open(path, 'r:gz') as archive:
        members = archive.getmembers(); names = {}; total = 0
        for item in members:
            p = Path(item.name); total += item.size
            if (not item.isfile() or p.is_absolute() or '..' in p.parts or '\\' in item.name
                or not p.parts or p.parts[0] not in ('work', 'bundle')
                or item.name in names or total > MAX_CACHE):
                raise ValueError('pipeline cache member')
            names[item.name] = item
        if len(names) > 20000: raise ValueError('pipeline cache count')
        count = 0
        for name in names:
            if fullwarm:
                match = re.fullmatch(r'work/[0-9]{5}/key', name)
                if not match: continue
                prefix = name[:-3]; binary = prefix + 'applegpu_g17g.mtl4a'; checksum = prefix + 'sha256'
                if binary not in names or checksum not in names: raise ValueError('incomplete pipeline group')
                expected = archive.extractfile(checksum).read(128).decode().strip()
                key = archive.extractfile(name).read(128).decode().strip()
                if not re.fullmatch('[0-9a-f]{64}', expected) or not re.fullmatch('[0-9a-f]{64}', key):
                    raise ValueError('pipeline group key/checksum')
                with archive.extractfile(binary) as source:
                    actual = hashlib.file_digest(source, 'sha256').hexdigest()
                if actual != expected: raise ValueError('pipeline archive checksum')
            else:
                if not re.fullmatch(r'work/batches\.applegpu_g17g/[^/]+/key\.applegpu_g17g', name): continue
                binary = name.rsplit('/', 1)[0] + '/applegpu_g17g.mtl4a'
                if binary not in names or not archive.extractfile(name).read(512).strip():
                    raise ValueError('incomplete pipeline group')
            if names[binary].size < 32: raise ValueError('pipeline archive too small')
            count += 1
        if not count: raise ValueError('empty pipeline cache')
        return count


def receive_cache(parent, cache, fullwarm=False):
    cache = Path(cache)
    incoming = cache.with_name('.' + cache.name + '.incoming-' + uuid.uuid4().hex)
    parent.receive_file(incoming.name, MAX_CACHE)
    # An invalid incoming file remains quarantined for diagnosis; latest stays.
    new_count = inspect_cache(incoming, fullwarm)
    if cache.exists():
        if cache.is_symlink(): raise ValueError('pipeline cache symlink')
        try: old_count = inspect_cache(cache, fullwarm)
        except (ValueError, tarfile.TarError, EOFError): old_count = 0
        if new_count < old_count: raise ValueError('pipeline cache would lose completed groups')
        with cache.open('rb') as source: identity = hashlib.file_digest(source, 'sha256').hexdigest()
        previous = cache.with_name(cache.name + '.' + identity + '.previous')
        try: os.link(cache, previous)
        except FileExistsError: pass
    os.replace(incoming, cache)
    return new_count
