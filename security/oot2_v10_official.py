#!/usr/bin/env python3
"""Strict wrapper of the official offline IPA exporter and bundle format."""
import collections,copy,hashlib,json,os,re,shutil,struct,subprocess,sys,time,zipfile
from pathlib import Path
try:
    from .oot2_prepare_ipad_v10 import PIN,CHAIN,TITLE,recipe
    from .oot2_ipad_aot import inspect_ipa,digest
    from .oot2_local_bundle import validate_zip_headers,extra_fields
except ImportError:
    from oot2_prepare_ipad_v10 import PIN,CHAIN,TITLE,recipe
    from oot2_ipad_aot import inspect_ipa,digest
    from oot2_local_bundle import validate_zip_headers,extra_fields
GPU='applegpu_g17g'
def counts(text):return dict(collections.Counter(l.split('\t',1)[0] for l in text.splitlines() if l and not l.startswith('#')))
def stamp(text):return dict(l.split('\t',1) for l in text.splitlines() if '\t' in l)
def official_bundle(folder,seed):
    folder=Path(folder);archives=sorted(folder.glob(GPU+'-prewarm-*.mtl4a'))
    if not archives or not (folder/(GPU+'.mtl4a')).is_file():raise ValueError('v10 base/prewarm archives missing')
    s=stamp((folder/'prewarm.tsv').read_text())
    if s.get('chain')!=CHAIN or int(s.get('files',0))!=len(archives) or int(s.get('lines',0))!=seed['R']+seed['M']:raise ValueError('v10 prewarm stamp coverage')
    if CHAIN not in (folder/'prebuilt.tsv').read_text():raise ValueError('v10 base stamp')
    summary=stamp((folder/'archive.tsv').read_text()).get('prewarm','')
    if not re.search(r', 0 pipelines left out',summary):raise ValueError('v10 exporter omitted pipelines')
    for p in archives:
        data=p.with_suffix('.keys').read_bytes()
        if len(data)<16 or data[:8]!=b'DMPSOIX2':raise ValueError('v10 archive index version')
        complete,n=struct.unpack_from('<II',data,8)
        if complete!=1 or n<1 or len(data)!=16+8*n:raise ValueError('v10 incomplete archive index')
    files={}
    for p in folder.iterdir():
        if p.is_symlink() or not p.is_file() or not re.fullmatch(r'[A-Za-z0-9_.-]{1,180}',p.name):raise ValueError('v10 archive resource')
        files[p.name]={'bytes':p.stat().st_size,'sha256':digest(p)}
    return files,len(archives)
def validate_delivery(path):
    # Final IPAs also carry RomFS; the shared strict ZIP validator covers both layouts.
    validate_zip_headers(path)
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        if len(names)!=len(set(names)):raise ValueError('v10 duplicate member')
        infos=[n for n in names if n.startswith('Payload/') and n.endswith('.app/Info.plist') and n.count('/')==2]
        if len(infos)!=1:raise ValueError('v10 app layout')
        import plistlib
        pre=infos[0][:-10];info=plistlib.loads(z.read(infos[0]))
        import stat
        for item in z.infolist():
            if '..' in Path(item.filename).parts or '\\' in item.filename or item.flag_bits&1 or stat.S_ISLNK(item.external_attr>>16) or not (item.filename.startswith(pre) or (item.is_dir() and pre.startswith(item.filename))):raise ValueError('v10 ZIP path/type')
        if info.get('CFBundleIdentifier')!='org.nxnative.0400486024dec000':raise ValueError('v10 bundle')
        libs=[n for n in names if re.fullmatch(re.escape(pre)+r'msl/b-[0-9a-f]{12}\.img',n)]
        if libs!=[pre+f'msl/b-{CHAIN}.img']:raise ValueError('v10 genuine new chain')
        r=json.loads(z.read(pre+'pso/oot2-v10.json'))
        if (r['chain'],r['source'],r['recipe_sha256'],r['gpu'],r['platform'])!=(CHAIN,PIN,recipe(),GPU,'ios'):raise ValueError('v10 provenance')
        seed=counts(z.read(pre+'dm/pso_manifest.tsv').decode());expected=json.loads(Path(__file__).with_name('oot2_ipad_v10_manifest.json').read_text())['seed_counts']
        if seed!=expected or seed!=r['seed_counts']:raise ValueError('v10 expanded seed coverage')
        with z.open(pre+info['CFBundleExecutable']) as f:h=hashlib.file_digest(f,'sha256').hexdigest()
        if h!=r['host_sha256']:raise ValueError('v10 host identity')
        keys=set(r['resources']);actual={n[len(pre+'pso/'):] for n in names if n.startswith(pre+'pso/') and not n.endswith('/')}
        if actual!=keys|{'oot2-v10.json'}:raise ValueError('v10 resource set')
        for name,meta in r['resources'].items():
            if not re.fullmatch(r'[A-Za-z0-9_.-]{1,180}',name):raise ValueError('v10 resource name')
            item=z.getinfo(pre+'pso/'+name)
            with z.open(item) as f:h=hashlib.file_digest(f,'sha256').hexdigest()
            if item.file_size!=meta['bytes'] or h!=meta['sha256']:raise ValueError('v10 resource hash')
        s=stamp(z.read(pre+'pso/prewarm.tsv').decode())
        archives=[n for n in keys if re.fullmatch(GPU+r'-prewarm-[0-9]{2,5}\.mtl4a',n)]
        if not archives or s.get('chain')!=CHAIN or int(s.get('lines',0))!=seed['R']+seed['M'] or int(s.get('files',0))!=len(archives) or len(archives)!=r['prewarm_files']:raise ValueError('v10 prewarm coverage')
        if GPU+'.mtl4a' not in keys or CHAIN not in z.read(pre+'pso/prebuilt.tsv').decode():raise ValueError('v10 base coverage')
        for n in archives:
            raw=z.read(pre+'pso/'+n[:-6]+'.keys')
            if len(raw)<16 or raw[:8]!=b'DMPSOIX2':raise ValueError('v10 keys')
            complete,count=struct.unpack_from('<II',raw,8)
            if complete!=1 or count<1 or len(raw)!=16+8*count:raise ValueError('v10 incomplete index')
        if not re.search(r', 0 pipelines left out',stamp(z.read(pre+'pso/archive.tsv').decode()).get('prewarm','')):raise ValueError('v10 omissions')
        return r

def build(root,slim,work):
    root,slim,work=map(lambda p:Path(p).resolve(),(root,slim,work));work.mkdir(exist_ok=False)
    pre=inspect_ipa(slim,expected_chain=CHAIN);inputs=work/'inputs';inputs.mkdir()
    with zipfile.ZipFile(slim) as z:
        for name in [f'msl/b-{CHAIN}.img']+['dm/'+n for n in ('shader_pairs.tsv','pso_pairs.tsv','shader_map.tsv','pso_manifest.tsv','c1_full.tsv','cb_extent.tsv')]:
            p=inputs/name;p.parent.mkdir(exist_ok=True,parents=True)
            with z.open(pre+name) as a,p.open('wb') as b:shutil.copyfileobj(a,b,8<<20)
        seed=counts(z.read(pre+'dm/pso_manifest.tsv').decode());import plistlib
        exe=pre+plistlib.loads(z.read(pre+'Info.plist'))['CFBundleExecutable']
        with z.open(exe) as f:hostsha=hashlib.file_digest(f,'sha256').hexdigest()
    expected=json.loads(Path(__file__).with_name('oot2_ipad_v10_manifest.json').read_text())['seed_counts']
    if seed!=expected:raise ValueError('v10 manifest not expanded')
    host=root/f'dm/host/gen/{TITLE}/dmhost';bundle=work/'bundle'
    # Entirely official host and descriptor exporter, built in the public gate.
    cmd=[sys.executable,str(root/'dm/gfx/tools/pso_offline.py'),'--game',TITLE,'--msl',str(inputs/f'msl/b-{CHAIN}.img'),'--shader-map',str(inputs/'dm/shader_map.tsv'),'--manifest',str(inputs/'dm/pso_manifest.tsv'),'--pairs',str(inputs/'dm/shader_pairs.tsv'),'--pairs',str(inputs/'dm/pso_pairs.tsv'),'--out',str(bundle),'--work',str(work/'cache'),'--gpu',GPU,'--platform','ios','--os-min','27.0','--depth','gl','--jobs','2','--prewarm-host',str(host)]
    env=dict(os.environ,DM_PSO_PREBUILD_THREADS='3')
    with (work/'official.log').open('wb') as log:
        proc=subprocess.Popen(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
        while proc.poll() is None:
            try:proc.wait(timeout=30)
            except subprocess.TimeoutExpired:print('Official v10 offline pipelines: running; completed cache files='+str(len(list((work/'cache').rglob('*.mtl4a')))),flush=True)
    if proc.returncode:raise RuntimeError('v10 official compiler failed; inspect private archive log')
    resources,n=official_bundle(bundle,seed)
    report={'chain':CHAIN,'source':PIN,'recipe_sha256':recipe(),'platform':'ios','gpu':GPU,'host_sha256':hostsha,'seed_counts':seed,'prewarm_files':n,'resources':resources}
    (bundle/'oot2-v10.json').write_text(json.dumps(report,indent=2)+'\n')
    output=work/'fullwarm.ipa'
    required=slim.stat().st_size+sum(p.stat().st_size for p in bundle.iterdir())+(1<<30)
    if shutil.disk_usage(work).free<required:raise ValueError('v10 final packing disk budget')
    with zipfile.ZipFile(slim) as src,zipfile.ZipFile(output,'w',allowZip64=True) as dst:
        for item in src.infolist():
            if item.filename.startswith(pre+'pso/'):raise ValueError('v10 requires pipeline-free checkpoint')
            target=copy.copy(item);target.extra=b''.join(struct.pack('<HH',k,len(v))+v for k,v in extra_fields(item.extra) if k!=1)
            with src.open(item) as a,dst.open(target,'w',force_zip64=True) as b:shutil.copyfileobj(a,b,8<<20)
        for p in bundle.iterdir():
            item=zipfile.ZipInfo(pre+'pso/'+p.name);item.external_attr=0o100644<<16;item.compress_type=zipfile.ZIP_STORED
            with p.open('rb') as a,dst.open(item,'w',force_zip64=True) as b:shutil.copyfileobj(a,b,8<<20)
    validate_delivery(output);print('PASS: official v10 expanded prewarm and all archive indexes verified.',flush=True)
if __name__=='__main__':build(*sys.argv[1:])
