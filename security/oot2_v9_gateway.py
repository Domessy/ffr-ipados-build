"""Fixed-path receipt for v9 only; v8 files and shader archives remain intact."""
import hashlib
import json
from pathlib import Path
import plistlib
import re
import zipfile
try:
    from .oot2_prepare_ipad_v9 import PIN, CHAIN
    from .oot2_local_bundle import bundle, identity, regular, validate_zip_headers
    from .oot2_fullwarm import validate_render_coverage
except ImportError:
    from oot2_prepare_ipad_v9 import PIN, CHAIN
    from oot2_local_bundle import bundle, identity, regular, validate_zip_headers
    from oot2_fullwarm import validate_render_coverage
GPU='applegpu_g17g'
ROUTES={'oot2-write-slim-v9','oot2-write-host-kit-v9','oot2-local-bundle-v9-ready','oot2-write-log-v9','oot2-write-checkpoint-v9'}

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while b:=f.read(8<<20):h.update(b)
    return h.hexdigest()

def validate_slim(path):
    validate_zip_headers(path)
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        if len(names)!=len(set(names)):raise ValueError('v9 duplicate member')
        infos=[n for n in names if n.startswith('Payload/') and n.endswith('.app/Info.plist') and n.count('/')==2]
        if len(infos)!=1:raise ValueError('v9 app layout')
        pre=infos[0][:-len('Info.plist')]
        if [n for n in names if re.fullmatch(re.escape(pre)+r'msl/b-[0-9a-f]{12}\.img',n)]!=[pre+f'msl/b-{CHAIN}.img']:raise ValueError('v9 genuine shader chain required')
        info=plistlib.loads(z.read(infos[0]))
        if info.get('CFBundleIdentifier')!='org.nxnative.0400486024dec000':raise ValueError('v9 title')
        r=json.loads(z.read(pre+'pso/fullwarm.json'));h=r['host'];marker=h['host_v9']
        manifest=json.loads(Path(__file__).with_name('oot2_ipad_v9_manifest.json').read_text())
        if r['chain']!=CHAIN or r['gpu']!=GPU or r['platform']!='ios' or h['source']!=PIN or marker!={'base':PIN,'chain':CHAIN,'patch_sha256':manifest['patch_sha256']}:raise ValueError('v9 archive/host provenance')
        validate_render_coverage(r['coverage'])
        if r['coverage']['failed_tasks'] or r['coverage']['stale_keys'] or r['coverage']['mesh_rows']!=r['coverage']['emitted_mesh'] or r['coverage']['periods']!=len(r['archives']):raise ValueError('v9 incomplete prewarm')
        with z.open(pre+info['CFBundleExecutable']) as f:
            sh=hashlib.file_digest(f,'sha256').hexdigest()
        if sh!=h['sha256']:raise ValueError('v9 host hash')
        for n,m in r['archives'].items():
            if not re.fullmatch(GPU+r'-prewarm-[0-9]{5}\.mtl4a',n):raise ValueError('v9 archive filename')
            item=z.getinfo(pre+'pso/'+n)
            with z.open(item) as f:sh=hashlib.file_digest(f,'sha256').hexdigest()
            if item.file_size!=m['bytes'] or sh!=m['sha256']:raise ValueError('v9 archive hash')
        z.getinfo(pre+'pso/'+GPU+'.mtl4a')
        if CHAIN not in z.read(pre+'pso/prebuilt.tsv').decode():raise ValueError('v9 base stamp')
    return r

def preserve(path):
    if path.exists():
        regular(path);backup=path.with_name(path.name+'.'+digest(path)+'.previous')
        if backup.exists():
            regular(backup)
            if digest(backup)!=digest(path):raise ValueError('v9 previous output corrupted')
            path.unlink()
        else:path.rename(backup)

def dispatch(command,parent,root,output,nup_identity):
    if command not in ROUTES:return 126
    old=parent.OUTPUT;parent.OUTPUT=output
    try:
        if command=='oot2-local-bundle-v9-ready':
            image=root/'local-bundle-v6/extract/v131072/RomFS.img';meta=root/'local-bundle-v6/romfs-manifest.json';regular(image);regular(meta);m=json.loads(meta.read_text())
            if m['source_identity']!=nup_identity() or list(identity(image))!=m['identity']:raise ValueError('v9 local RomFS identity')
            print('OOT2_LOCAL_BUNDLE_READY_V9',image.stat().st_size)
        elif command=='oot2-write-checkpoint-v9':
            try:
                from .oot2_ipad_aot import inspect_ipa
            except ImportError:
                from oot2_ipad_aot import inspect_ipa
            uploaded=output/'v9-checkpoint-upload.ipa'
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
            checkpoint=output/'ZeldaOcarinaOfTime-v9-unwarmed-checkpoint.ipa'
            preserve(checkpoint);uploaded.rename(checkpoint)
            record={'chain':CHAIN,'bytes':checkpoint.stat().st_size,'sha256':digest(checkpoint),'fullwarm_validated':False}
            (output/'v9-checkpoint.json').write_text(json.dumps(record,indent=2)+'\n')
            print('OOT2_V9_CHECKPOINT_SAVED',record['bytes'])
        elif command=='oot2-write-host-kit-v9':
            preserve(output/'OOT2HostKit-v9.tar.zst');parent.receive_file('OOT2HostKit-v9.tar.zst',1<<30)
        elif command=='oot2-write-log-v9':parent.receive_file('oot2-v9-build.log',32<<20)
        else:
            uploaded=output/'ZeldaOcarinaOfTime-v9-upload.ipa';parent.receive_file(uploaded.name,16<<30)
            validate_slim(uploaded)
            slim=output/'ZeldaOcarinaOfTime-v9-slim.ipa';preserve(slim);uploaded.rename(slim)
            final=output/'ZeldaOcarinaOfTime-ipad-v9-fullwarm-livecontainer.ipa';preserve(final)
            stats=bundle(slim,root/'local-bundle-v6/extract/v131072/RomFS.img',root/'local-bundle-v6/romfs-manifest.json',final,expected_chain=CHAIN)
            (output/'ipad-v9-local-bundle-result.json').write_text(json.dumps(stats,indent=2)+'\n')
            print('OOT2_V9_LOCAL_BUNDLE_OK',stats['ipa_bytes'])
    finally:parent.OUTPUT=old
    return 0
