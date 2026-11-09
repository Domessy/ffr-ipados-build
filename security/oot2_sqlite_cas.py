#!/usr/bin/env python3
"""Bridge nxnative's SQLite cas.db to the OOT2 fixed-route SSH CAS archive.

Only synthetic tests use this module in CI. No game files, keys or private
paths are emitted; export writes a gzip tar stream to stdout exclusively.

The pinned nxnative shader_cache.Store expects DMSH_CAS to name a SQLite
FILE. The fixed SSH gateway persists allowlisted index/shader/variant/metallib
entries as immutable individual files. This bridge imports those files into
cas.db before a build and exports committed SQLite entries at checkpoints.
"""
import hashlib
import io
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import sys
import tarfile
import time

NAMESPACES = ("index", "metallib", "shader", "variant")
SAFE_PART = re.compile(r"[A-Za-z0-9_.-]{1,180}\Z")
MAX_ITEM = 1 << 30
MAX_ITEMS = 1_000_000
SCHEMA = (
    "CREATE TABLE IF NOT EXISTS blob("
    "id INTEGER PRIMARY KEY, hash BLOB UNIQUE NOT NULL, data BLOB NOT NULL)",
    "CREATE TABLE IF NOT EXISTS entry("
    "name TEXT PRIMARY KEY, blob INTEGER NOT NULL, mtime REAL NOT NULL) WITHOUT ROWID",
)


def valid(name):
    parts = name.split("/")
    return (2 <= len(parts) <= 7 and parts[0] in NAMESPACES
            and all(part not in (".", "..") and SAFE_PART.fullmatch(part)
                    for part in parts))


def db_file(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("cache_root")
    db = root / "cas.db"
    if db.is_symlink() or db.is_dir():
        raise ValueError("cache_file")
    return db


def prepare(root):
    """Import safely restored old-format cache files to nxnative cas.db."""
    db_path = db_file(root)
    db = sqlite3.connect(db_path, timeout=120, isolation_level=None)
    count = 0
    try:
        db.execute("PRAGMA page_size=16384")
        db.execute("PRAGMA auto_vacuum=INCREMENTAL")
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=NORMAL")
        for sql in SCHEMA:
            db.execute(sql)
        db.execute("BEGIN IMMEDIATE")
        for prefix in NAMESPACES:
            folder = Path(root) / prefix
            if not folder.is_dir() or folder.is_symlink():
                continue
            for directory, dirs, files in os.walk(folder, followlinks=False):
                dirs[:] = sorted(d for d in dirs
                                 if not (Path(directory) / d).is_symlink())
                for name in sorted(files):
                    file = Path(directory) / name
                    label = file.relative_to(root).as_posix()
                    if not valid(label) or file.is_symlink():
                        continue
                    meta = file.stat()
                    if not stat.S_ISREG(meta.st_mode) or meta.st_size > MAX_ITEM:
                        raise ValueError("cache_item")
                    if count >= MAX_ITEMS:
                        raise ValueError("cache_count")
                    data = file.read_bytes()
                    digest = hashlib.blake2b(data, digest_size=16).digest()
                    db.execute("INSERT OR IGNORE INTO blob(hash,data) VALUES (?,?)",
                               (digest, data))
                    blob_id = db.execute("SELECT id FROM blob WHERE hash=?",
                                         (digest,)).fetchone()[0]
                    db.execute("INSERT OR REPLACE INTO entry(name,blob,mtime)"
                               " VALUES (?,?,?)", (label, blob_id, meta.st_mtime))
                    count += 1
                    if count % 200 == 0:
                        db.commit()
                        db.execute("BEGIN IMMEDIATE")
        db.commit()
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("database_integrity")
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except BaseException:
        if db.in_transaction:
            db.rollback()
        raise
    finally:
        db.close()
    # Only the restored, transient, allowlisted flat-file directories are
    # deleted. The database remains; the originating CachyOS cache is untouched.
    for prefix in NAMESPACES:
        folder = Path(root) / prefix
        if folder.is_dir() and not folder.is_symlink():
            shutil.rmtree(folder)
    print(f"OOT2_SQLITE_CAS_READY restored_entries={count}")


def export(root, since_ns, before_ns):
    """Stream committed SQLite entries to the existing fixed-route tar importer.

    A read transaction gives a stable snapshot while nxnative writes in WAL
    mode. The cutoff overlaps by 2 seconds to avoid float timestamp rounding
    losses; duplicate identical entries are deduplicated by the SSH gateway.
    """
    db_path = db_file(root)
    if not db_path.is_file():
        raise ValueError("cache_missing")
    if not 0 <= since_ns <= before_ns:
        raise ValueError("time_range")
    since = max(0, (since_ns / 1e9) - 2.0)
    before = before_ns / 1e9
    db = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True, timeout=120)
    exported = 0
    try:
        db.execute("PRAGMA busy_timeout=120000")
        db.execute("BEGIN")
        cursor = db.execute(
            "SELECT e.name, b.data, e.mtime "
            "FROM entry e JOIN blob b ON b.id=e.blob "
            "WHERE e.mtime>? AND e.mtime<=? AND substr(e.name,1,6) != 'stage/' ORDER BY e.name",
            (since, before))
        with tarfile.open(fileobj=sys.stdout.buffer, mode="w|gz",
                          compresslevel=1) as tar:
            for name, data, mtime in cursor:
                if not valid(name) or len(data) > MAX_ITEM:
                    raise ValueError("cache_item")
                if exported >= MAX_ITEMS:
                    raise ValueError("cache_count")
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mtime = int(mtime)
                info.mode = 0o600
                tar.addfile(info, io.BytesIO(data))
                exported += 1
        db.commit()
    finally:
        db.close()
    print(f"OOT2_SQLITE_CAS_EXPORTED={exported}", file=sys.stderr)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "prepare":
        prepare(Path(sys.argv[2]))
    elif len(sys.argv) == 5 and sys.argv[1] == "export":
        export(Path(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
    else:
        raise ValueError("usage")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, sqlite3.DatabaseError, tarfile.TarError):
        print("OOT2_SQLITE_CAS status=fail", file=sys.stderr)
        raise SystemExit(1)
