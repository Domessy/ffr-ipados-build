#!/usr/bin/env python3
"""Private, reusable SQLite transfer snapshot of the compiled Metal CAS only.

No Nintendo data, arbitrary SSH paths, shader relabelling or source-cache
deletion. The normal full restore remains available for same-chain resumes.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
import tempfile

PART = re.compile(r'[A-Za-z0-9_.-]{1,180}\Z')
MAX_FILE = 1 << 30
MAX_BYTES = 120 << 30
MAX_FILES = 1_000_000
SCHEMA = (
    'CREATE TABLE blob(id INTEGER PRIMARY KEY, hash BLOB UNIQUE NOT NULL, data BLOB NOT NULL)',
    'CREATE TABLE entry(name TEXT PRIMARY KEY, blob INTEGER NOT NULL, mtime REAL NOT NULL) WITHOUT ROWID',
)


def metal_name(name):
    parts = name.split('/')
    return (2 <= len(parts) <= 7 and parts[0] == 'metallib'
            and all(p not in ('.', '..') and PART.fullmatch(p) for p in parts))


def safe_dir(path):
    path = Path(path)
    # Walk parents too: a root redirect must not broaden a fixed-route export.
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('snapshot directory symlink')
    return path


def inventory(cache):
    cache = safe_dir(cache)
    base = safe_dir(cache / 'metallib')
    rows, total = [], 0
    if not base.is_dir():
        raise ValueError('compiled Metal cache missing')
    for folder, dirs, files in os.walk(base, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not (Path(folder) / d).is_symlink())
        for name in sorted(files):
            p = Path(folder) / name
            label = p.relative_to(cache).as_posix()
            st = p.lstat()
            if not stat.S_ISREG(st.st_mode) or not metal_name(label):
                continue
            total += st.st_size
            if st.st_size > MAX_FILE or total > MAX_BYTES or len(rows) >= MAX_FILES:
                raise ValueError('compiled cache bound exceeded')
            rows.append((label, st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_ino))
    if not rows:
        raise ValueError('compiled cache empty')
    fingerprint = hashlib.sha256(json.dumps(rows, separators=(',', ':')).encode()).hexdigest()
    return rows, total, fingerprint


def snapshot(cache, output):
    cache, output = safe_dir(cache), safe_dir(output)
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(output, 0o700)
    lock = output / 'metal-v1.lock'
    with os.fdopen(os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600), 'rb') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        rows, source_bytes, fingerprint = inventory(cache)
        archive = output / 'metal-v1.sqlite.zst'
        manifest = output / 'metal-v1.json'
        if archive.is_symlink() or manifest.is_symlink():
            raise ValueError('snapshot output symlink')
        if archive.is_file() and manifest.is_file():
            old = json.loads(manifest.read_text())
            if old.get('fingerprint') == fingerprint and old.get('compressed_bytes') == archive.stat().st_size:
                return archive, old
        # Build outside the immutable source CAS. Nothing is extracted or
        # renamed in that CAS, even if the transfer is interrupted.
        with tempfile.TemporaryDirectory(prefix='.metal-snapshot-', dir=output) as temp:
            dbfile = Path(temp) / 'cas.db'
            db = sqlite3.connect(dbfile)
            try:
                db.execute('PRAGMA page_size=16384')
                db.execute('PRAGMA auto_vacuum=INCREMENTAL')
                for sql in SCHEMA:
                    db.execute(sql)
                for index, (name, size, mtime, ctime, inode) in enumerate(rows):
                    p = cache / name
                    safe_dir(p.parent)
                    with os.fdopen(os.open(p, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as f:
                        st = os.fstat(f.fileno())
                        if (st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_ino) != (size, mtime, ctime, inode):
                            raise ValueError('compiled entry changed during snapshot')
                        data = f.read(MAX_FILE + 1)
                        if len(data) != size:
                            raise ValueError('compiled entry changed size')
                    digest = hashlib.blake2b(data, digest_size=16).digest()
                    db.execute('INSERT OR IGNORE INTO blob(hash,data) VALUES (?,?)', (digest, data))
                    ident = db.execute('SELECT id FROM blob WHERE hash=?', (digest,)).fetchone()[0]
                    db.execute('INSERT INTO entry(name,blob,mtime) VALUES (?,?,?)', (name, ident, mtime / 1e9))
                    if index % 500 == 0:
                        db.commit()
                db.commit()
                if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                    raise ValueError('snapshot integrity')
                blobs = db.execute('SELECT count(*) FROM blob').fetchone()[0]
            finally:
                db.close()
            compressed = Path(temp) / 'cas.db.zst'
            subprocess.run(['zstd', '-q', '-1', '-T0', str(dbfile), '-o', str(compressed)], check=True)
            os.chmod(compressed, 0o600)
            stats = {'version': 1, 'fingerprint': fingerprint, 'entries': len(rows),
                     'blobs': blobs, 'source_bytes': source_bytes,
                     'sqlite_bytes': dbfile.stat().st_size, 'compressed_bytes': compressed.stat().st_size}
            meta = Path(temp) / 'manifest.json'
            meta.write_text(json.dumps(stats, indent=2) + '\n')
            os.chmod(meta, 0o600)
            os.replace(compressed, archive)
            os.replace(meta, manifest)
            return archive, stats


def accept(root):
    """Publish a complete runner-local snapshot only after validation."""
    root = safe_dir(root)
    src, dst = root / 'cas.db.partial', root / 'cas.db'
    if src.is_symlink() or dst.exists() or dst.is_symlink() or not src.is_file():
        raise ValueError('snapshot destination')
    if not 0 < src.stat().st_size <= MAX_BYTES:
        raise ValueError('snapshot size')
    db = sqlite3.connect(src.as_uri() + '?mode=ro', uri=True)
    try:
        if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('snapshot integrity')
        schema = db.execute("SELECT name,type FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
        if schema != [('blob', 'table'), ('entry', 'table')]:
            raise ValueError('snapshot schema')
        for digest, data in db.execute('SELECT hash,data FROM blob'):
            if len(data) > MAX_FILE or hashlib.blake2b(data, digest_size=16).digest() != digest:
                raise ValueError('snapshot blob checksum')
        count, total = 0, 0
        for name, size, digest_size in db.execute('SELECT e.name,length(b.data),length(b.hash) FROM entry e JOIN blob b ON e.blob=b.id'):
            count += 1
            total += size
            if not metal_name(name) or size > MAX_FILE or digest_size != 16 or count > MAX_FILES or total > MAX_BYTES:
                raise ValueError('snapshot entry')
        if not count or count != db.execute('SELECT count(*) FROM entry').fetchone()[0]:
            raise ValueError('snapshot missing entries')
    finally:
        db.close()
    os.chmod(src, 0o600)
    # Publishing must not overwrite a database another process just opened.
    os.link(src, dst)
    src.unlink()
    print(f'OOT2_METAL_SNAPSHOT_READY entries={count} logical_bytes={total}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='cmd', required=True)
    create = sub.add_parser('create')
    create.add_argument('cache', type=Path)
    create.add_argument('output', type=Path)
    validate = sub.add_parser('accept')
    validate.add_argument('root', type=Path)
    args = parser.parse_args()
    if args.cmd == 'create':
        _, stats = snapshot(args.cache, args.output)
        print(json.dumps(stats, sort_keys=True))
    else:
        accept(args.root)
