"""Fixed-path receipt for v10 only; v8 files and shader archives remain intact."""
import hashlib
import json
from pathlib import Path
import plistlib
import re
import zipfile
try:
    from .oot2_prepare_ipad_v10 import PIN, CHAIN
    from .oot2_local_bundle import bundle, identity, regular, validate_zip_headers
    from .oot2_fullwarm import validate_render_coverage
except ImportError:
    from oot2_prepare_ipad_v10 import PIN, CHAIN
    from oot2_local_bundle import bundle, identity, regular, validate_zip_headers
    from oot2_fullwarm import validate_render_coverage
GPU='applegpu_g17g'
ROUTES={'oot2-write-slim-v10','oot2-write-host-kit-v10','oot2-local-bundle-v10-ready','oot2-write-log-v10','oot2-write-checkpoint-v10','oot2-write-archive-log-v10','oot2-checkpoint-v10-info','oot2-read-checkpoint-v10'}

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while b:=f.read(8<<20):h.update(b)
    return h.hexdigest()

def validate_slim(path):
    try:
        from .oot2_v10_official import validate_delivery
    except ImportError:
        from oot2_v10_official import validate_delivery
    return validate_delivery(path)


def preserve(path):
    if path.exists():
        regular(path);backup=path.with_name(path.name+'.'+digest(path)+'.previous')
        if backup.exists():
            regular(backup)
            if digest(backup)!=digest(path):raise ValueError('v10 previous output corrupted')
            path.unlink()
        else:path.rename(backup)

def dispatch(command,parent,root,output,nup_identity):
    if command not in ROUTES:return 126
    old=parent.OUTPUT;parent.OUTPUT=output
    try:
        if command=='oot2-local-bundle-v10-ready':
            image=root/'local-bundle-v6/extract/v131072/RomFS.img';meta=root/'local-bundle-v6/romfs-manifest.json';regular(image);regular(meta);m=json.loads(meta.read_text())
            if m['source_identity']!=nup_identity() or list(identity(image))!=m['identity']:raise ValueError('v10 local RomFS identity')
            print('OOT2_LOCAL_BUNDLE_READY_V10',image.stat().st_size)
        elif command in ('oot2-checkpoint-v10-info','oot2-read-checkpoint-v10'):
            checkpoint=output/'ZeldaOcarinaOfTime-v10-unwarmed-checkpoint.ipa'
            regular(checkpoint);meta=output/'v10-checkpoint.json';regular(meta)
            record=json.loads(meta.read_text())
            if record.get('chain')!=CHAIN or record.get('bytes')!=checkpoint.stat().st_size or record.get('sha256')!=digest(checkpoint) or record.get('fullwarm_validated') is not False:
                raise ValueError('v10 checkpoint identity')
            if command=='oot2-checkpoint-v10-info':print('OOT2_V10_CHECKPOINT_V1',record['bytes'],record['sha256'])
            else:parent.send_file(checkpoint)
        elif command=='oot2-write-checkpoint-v10':
            try:
                from .oot2_ipad_aot import inspect_ipa
            except ImportError:
                from oot2_ipad_aot import inspect_ipa
            uploaded=output/'v10-checkpoint-upload.ipa'
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
            checkpoint=output/'ZeldaOcarinaOfTime-v10-unwarmed-checkpoint.ipa'
            preserve(checkpoint);uploaded.rename(checkpoint)
            record={'chain':CHAIN,'bytes':checkpoint.stat().st_size,'sha256':digest(checkpoint),'fullwarm_validated':False}
            (output/'v10-checkpoint.json').write_text(json.dumps(record,indent=2)+'\n')
            print('OOT2_V10_CHECKPOINT_SAVED',record['bytes'])
        elif command=='oot2-write-host-kit-v10':
            preserve(output/'OOT2HostKit-v10.tar.zst');parent.receive_file('OOT2HostKit-v10.tar.zst',1<<30)
        elif command=='oot2-write-archive-log-v10':parent.receive_file('oot2-v10-archives.log',32<<20)
        elif command=='oot2-write-log-v10':parent.receive_file('oot2-v10-build.log',32<<20)
        else:
            uploaded=output/'ZeldaOcarinaOfTime-v10-upload.ipa';parent.receive_file(uploaded.name,16<<30)
            validate_slim(uploaded)
            slim=output/'ZeldaOcarinaOfTime-v10-slim.ipa';preserve(slim);uploaded.rename(slim)
            final=output/'ZeldaOcarinaOfTime-ipad-v10-fullwarm-livecontainer.ipa';preserve(final)
            stats=bundle(slim,root/'local-bundle-v6/extract/v131072/RomFS.img',root/'local-bundle-v6/romfs-manifest.json',final,expected_chain=CHAIN)
            (output/'ipad-v10-local-bundle-result.json').write_text(json.dumps(stats,indent=2)+'\n')
            print('OOT2_V10_LOCAL_BUNDLE_OK',stats['ipa_bytes'])
    finally:parent.OUTPUT=old
    return 0
