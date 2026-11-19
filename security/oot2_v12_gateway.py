"""Fixed-path receipt for v12 only; v10 files and shader archives remain intact."""
import hashlib
import json
from pathlib import Path
import plistlib
import re
import zipfile
try:
    from .oot2_prepare_ipad_v12 import PIN, CHAIN
    from .oot2_local_bundle import bundle, identity, regular, validate_zip_headers
    from .oot2_fullwarm import validate_render_coverage
except ImportError:
    from oot2_prepare_ipad_v12 import PIN, CHAIN
    from oot2_local_bundle import bundle, identity, regular, validate_zip_headers
    from oot2_fullwarm import validate_render_coverage
GPU='applegpu_g17g'
ROUTES={'oot2-write-slim-v12','oot2-write-host-kit-v12','oot2-local-bundle-v12-ready','oot2-write-log-v12','oot2-write-checkpoint-v12','oot2-write-archive-log-v12','oot2-checkpoint-v12-info','oot2-read-checkpoint-v12'}
ROUTES |= {'oot2-write-cache-v12', 'oot2-cache-v12-info', 'oot2-read-cache-v12'}

def cache_snapshot(root):
    try:
        from .oot2_cache_snapshot import snapshot, safe_dir
    except ImportError:
        from oot2_cache_snapshot import snapshot, safe_dir
    cache = safe_dir(root/'shader-cache-v12')
    if not cache.exists() or not any((cache/'index').glob('*.json')):
        return None
    archive, meta = snapshot(cache, root/'cache-transfer-v12', translations=True)
    return archive, meta, digest(archive)

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while b:=f.read(8<<20):h.update(b)
    return h.hexdigest()

def validate_slim(path):
    try:
        from .oot2_v12_official import validate_delivery
    except ImportError:
        from oot2_v12_official import validate_delivery
    return validate_delivery(path)


def preserve(path):
    if path.exists():
        regular(path);backup=path.with_name(path.name+'.'+digest(path)+'.previous')
        if backup.exists():
            regular(backup)
            if digest(backup)!=digest(path):raise ValueError('v12 previous output corrupted')
            path.unlink()
        else:path.rename(backup)

def dispatch(command,parent,root,output,nup_identity):
    if command not in ROUTES:return 126
    old=parent.OUTPUT;parent.OUTPUT=output
    try:
        if command=='oot2-write-cache-v12':
            saved = parent.CACHE, parent.CONFLICTS
            try:
                parent.CACHE, parent.CONFLICTS = root/'shader-cache-v12', root/'shader-cache-conflicts-v12'
                parent.receive_cache()
            finally:
                parent.CACHE, parent.CONFLICTS = saved
        elif command in ('oot2-cache-v12-info', 'oot2-read-cache-v12'):
            current = cache_snapshot(root)
            if current is None:
                if command != 'oot2-cache-v12-info':raise ValueError('v12 cache has no completed shaders')
                print('OOT2_V12_CACHE_EMPTY')
            else:
                archive, meta, checksum = current
                if command=='oot2-cache-v12-info':
                    print('OOT2_V12_CACHE_V1',archive.stat().st_size,meta['sqlite_bytes'],meta['entries'],CHAIN,checksum)
                else:parent.send_file(archive)
        elif command=='oot2-local-bundle-v12-ready':
            image=root/'local-bundle-v6/extract/v131072/RomFS.img';meta=root/'local-bundle-v6/romfs-manifest.json';regular(image);regular(meta);m=json.loads(meta.read_text())
            if m['source_identity']!=nup_identity() or list(identity(image))!=m['identity']:raise ValueError('v12 local RomFS identity')
            print('OOT2_LOCAL_BUNDLE_READY_V12',image.stat().st_size)
        elif command in ('oot2-checkpoint-v12-info','oot2-read-checkpoint-v12'):
            checkpoint=output/'ZeldaOcarinaOfTime-v12-unwarmed-checkpoint.ipa'
            regular(checkpoint);meta=output/'v12-checkpoint.json';regular(meta)
            record=json.loads(meta.read_text())
            if record.get('chain')!=CHAIN or record.get('bytes')!=checkpoint.stat().st_size or record.get('sha256')!=digest(checkpoint) or record.get('fullwarm_validated') is not False:
                raise ValueError('v12 checkpoint identity')
            if command=='oot2-checkpoint-v12-info':print('OOT2_V12_CHECKPOINT_V1',record['bytes'],record['sha256'])
            else:parent.send_file(checkpoint)
        elif command=='oot2-write-checkpoint-v12':
            try:
                from .oot2_ipad_aot import inspect_ipa
            except ImportError:
                from oot2_ipad_aot import inspect_ipa
            uploaded=output/'v12-checkpoint-upload.ipa'
            parent.receive_file(uploaded.name,16<<30)
            pre=inspect_ipa(uploaded,expected_chain=CHAIN)
            with zipfile.ZipFile(uploaded) as z:
                images=[n for n in z.namelist() if re.fullmatch(re.escape(pre)+r'msl/b-[0-9a-f]{12}\.img',n)]
                if images!=[pre+f'msl/b-{CHAIN}.img']:raise ValueError('checkpoint shader chain')
                info=plistlib.loads(z.read(pre+'Info.plist'))
                with z.open(pre+info['CFBundleExecutable']) as f:
                    header=f.read(8)
                if header!=bytes.fromhex('cffaedfe0c000001'):raise ValueError('checkpoint ARM64 executable')
                if z.testzip() is not None:raise ValueError('checkpoint CRC')
            checkpoint=output/'ZeldaOcarinaOfTime-v12-unwarmed-checkpoint.ipa'
            preserve(checkpoint);uploaded.rename(checkpoint)
            record={'chain':CHAIN,'bytes':checkpoint.stat().st_size,'sha256':digest(checkpoint),'fullwarm_validated':False}
            (output/'v12-checkpoint.json').write_text(json.dumps(record,indent=2)+'\n')
            print('OOT2_V12_CHECKPOINT_SAVED',record['bytes'])
        elif command=='oot2-write-host-kit-v12':
            preserve(output/'OOT2HostKit-v12.tar.zst');parent.receive_file('OOT2HostKit-v12.tar.zst',1<<30)
        elif command=='oot2-write-archive-log-v12':parent.receive_file('oot2-v12-archives.log',32<<20)
        elif command=='oot2-write-log-v12':parent.receive_file('oot2-v12-build.log',32<<20)
        else:
            uploaded=output/'ZeldaOcarinaOfTime-v12-upload.ipa';parent.receive_file(uploaded.name,16<<30)
            validate_slim(uploaded)
            slim=output/'ZeldaOcarinaOfTime-v12-slim.ipa';preserve(slim);uploaded.rename(slim)
            final=output/'ZeldaOcarinaOfTime-ipad-v12-fullwarm-livecontainer.ipa';preserve(final)
            stats=bundle(slim,root/'local-bundle-v6/extract/v131072/RomFS.img',root/'local-bundle-v6/romfs-manifest.json',final,expected_chain=CHAIN)
            (output/'ipad-v12-local-bundle-result.json').write_text(json.dumps(stats,indent=2)+'\n')
            print('OOT2_V12_LOCAL_BUNDLE_OK',stats['ipa_bytes'])
    finally:parent.OUTPUT=old
    return 0
