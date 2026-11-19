"""Check the exact saved v11 snapshot before using the existing CAS importer."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
try:
    from .oot2_prepare_ipad_v11 import PIN, CHAIN, recipe
except ImportError:
    from oot2_prepare_ipad_v11 import PIN, CHAIN, recipe


def specification():
    spec = json.loads(Path(__file__).with_suffix('.json').read_text())
    if (spec['source'], spec['chain'], spec['recipe_sha256']) != (PIN, CHAIN, recipe()):
        raise ValueError('v11 resume source/chain/recipe')
    return spec


def verify_info(marker, compressed, sqlite, entries, spec):
    if marker != 'OOT2_METAL_SNAPSHOT_V1' or tuple(map(int, (compressed, sqlite, entries))) != tuple(spec[k] for k in ('compressed_bytes', 'sqlite_bytes', 'entries')):
        raise ValueError('v11 resume snapshot inventory')


def verify_archive(path, spec):
    path = Path(path)
    if path.is_symlink() or path.stat().st_size != spec['compressed_bytes']:
        raise ValueError('v11 resume archive size')
    h = hashlib.sha256()
    with path.open('rb') as f:
        while block := f.read(8 << 20):
            h.update(block)
    if h.hexdigest() != spec['sha256']:
        raise ValueError('v11 resume archive checksum')


def verify_indices(path, spec):
    db = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    try:
        count = 0
        for name, data in db.execute("SELECT e.name,b.data FROM entry e JOIN blob b ON b.id=e.blob WHERE e.name LIKE 'index/%'"):
            if json.loads(data).get('code_fp') != spec['code_fp']:
                raise ValueError('v11 resume shader fingerprint')
            count += 1
        if count != spec['indices']:
            raise ValueError('v11 resume shader count')
    finally:
        db.close()
    print('PASS: exact v11 cached shader indices:', count)


if __name__ == '__main__':
    spec = specification()
    mode = sys.argv[1]
    if mode == 'info':
        verify_info(*sys.argv[2:], spec)
    elif mode == 'archive':
        verify_archive(sys.argv[2], spec)
    elif mode == 'indices':
        verify_indices(sys.argv[2], spec)
    else:
        raise SystemExit('invalid v11 resume operation')
