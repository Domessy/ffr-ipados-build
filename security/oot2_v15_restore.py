"""Restore only v15 CAS, and expose a verified pause to one automatic resume job."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
try:
    from .oot2_prepare_ipad_v15 import CHAIN
    from .oot2_transfer import transfer
    from .oot2_cache_snapshot import accept
    from .oot2_sqlite_cas import prepare
except ImportError:
    from oot2_prepare_ipad_v15 import CHAIN
    from oot2_transfer import transfer
    from oot2_cache_snapshot import accept
    from oot2_sqlite_cas import prepare


def parse_info(text):
    fields = text.strip().split()
    if fields == ['OOT2_V15_CACHE_EMPTY']:
        return None
    if len(fields) != 6 or fields[0] != 'OOT2_V15_CACHE_V1' or fields[4] != CHAIN:
        raise ValueError('v15 cache identity')
    if not all(re.fullmatch(r'[1-9][0-9]*', n) for n in fields[1:4]) or not re.fullmatch(r'[0-9a-f]{64}',fields[5]):
        raise ValueError('v15 cache inventory')
    size, sql, entries = map(int, fields[1:4])
    if size > 80<<30 or sql > 120<<30 or entries > 1_000_000:
        raise ValueError('v15 cache bounds')
    return dict(bytes=size, sqlite_bytes=sql, entries=entries, sha256=fields[5])


def remote_info():
    return parse_info(subprocess.check_output(['ssh','-o','ConnectTimeout=25','ffr-cachyos','oot2-cache-v15-info'],text=True,timeout=600))


def verify_indices(path):
    db = sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)
    try:
        count = 0
        for name,data in db.execute("SELECT e.name,b.data FROM entry e JOIN blob b ON e.blob=b.id WHERE e.name LIKE 'index/%'"):
            if not re.fullmatch(r'index/[0-9a-f]{16}\.json',name):raise ValueError('v15 index name')
            meta=json.loads(data)
            if any(not re.fullmatch(r'[0-9a-f]{64}',meta.get(k,'')) for k in ('digest','code_fp','rule_fp')):raise ValueError('v15 index fingerprint')
            key=Path(name).stem;prefix='shader/'+meta['digest']+'/'
            for suffix in ('mac/'+key+'_b.json','mac/'+key+'_b.metal','ios/'+key+'_b.json','ios/'+key+'_b.metallib'):
                found=db.execute('SELECT b.data FROM entry e JOIN blob b ON e.blob=b.id WHERE e.name=?',(prefix+suffix,)).fetchone() if suffix.endswith('.json') else db.execute('SELECT length(b.data) FROM entry e JOIN blob b ON e.blob=b.id WHERE e.name=?',(prefix+suffix,)).fetchone()
                if not found:raise ValueError('v15 incomplete cached shader')
                if suffix.endswith('.json') and json.loads(found[0]).get('chain')!=CHAIN:raise ValueError('v15 cached reflection chain')
            count+=1
        if not count:raise ValueError('v15 cache has no complete shader indices')
        return count
    finally:
        db.close()


def restore():
    root=Path(os.environ['RUNNER_TEMP']).resolve();cache=root/'oot2-shader-cas'
    cache.mkdir(mode=0o700,exist_ok=True)
    if (cache/'cas.db').exists():raise ValueError('v15 restore destination exists')
    info=remote_info()
    if info is None:
        prepare(cache)
        print('V15: first build of the new chain; isolated empty CAS initialized.',flush=True)
        return
    if shutil.disk_usage(root).free < info['bytes']+info['sqlite_bytes']+(7<<30):raise ValueError('v15 restore disk')
    archive=cache/'metal-snapshot.zst';transfer('v15-cache',info['bytes'],archive)
    with archive.open('rb') as f:
        if hashlib.file_digest(f,'sha256').hexdigest()!=info['sha256']:raise ValueError('v15 cache transfer checksum')
    print('V15 cache transfer complete; decompressing verified snapshot.',flush=True)
    with (cache/'cas.db.partial').open('xb') as f:
        subprocess.run(['zstd','-q','-d','-c',str(archive)],stdout=f,check=True)
    archive.unlink()
    if (cache/'cas.db.partial').stat().st_size!=info['sqlite_bytes']:raise ValueError('v15 restored size')
    accept(cache,translations=True)
    with sqlite3.connect(cache/'cas.db') as db:
        if db.execute('SELECT count(*) FROM entry').fetchone()[0]!=info['entries']:raise ValueError('v15 restored inventory')
    count=verify_indices(cache/'cas.db')
    subprocess.run([str(root/'oot2-venv/bin/python'),str(root/'nxnative/dm/tools/shader_cache.py'),str(cache/'cas.db')],check=True)
    print('PASS: v15 exact native cache restored; completed shaders:',count,flush=True)


def job():
    rc=subprocess.call([sys.executable,str(Path(__file__).with_name('run_oot2.py'))])
    if rc==0:
        state='ready'
    elif rc==75 and os.environ.get('OOT2_ALLOW_PAUSE')=='1':
        if remote_info() is None:raise ValueError('v15 pause has no durable shader checkpoint')
        state='paused'
        print('V15: durable shader cache acknowledged; continuing in a fresh automatic job.',flush=True)
    else:
        raise SystemExit(rc)
    with Path(os.environ['GITHUB_OUTPUT']).open('a') as f:f.write('state='+state+'\n')


if __name__=='__main__':
    if sys.argv[1:]==['restore']:restore()
    elif sys.argv[1:]==['job']:job()
    else:raise SystemExit('invalid v15 cache operation')
