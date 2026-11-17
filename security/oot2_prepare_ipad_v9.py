#!/usr/bin/env python3
"""Prepare an immutable upstream migration; never relabel old shader resources."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
try:
    from .oot2_patch_nup_release import ANCHOR, INJECTION
except ImportError:
    from oot2_patch_nup_release import ANCHOR, INJECTION
PIN = '87422462a4c020def29cc39d3042b08cc9eab02a'
CHAIN = '9eecb8412308'

def prepare(root):
    root = Path(root).resolve(); here = Path(__file__).parent
    meta = json.loads((here/'oot2_ipad_v9_manifest.json').read_text())
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip() != PIN:
        raise ValueError('v9 exact upstream revision required')
    for name, expected in meta['originals'].items():
        p=root/name
        if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:
            raise ValueError('v9 source differs: '+name)
    patch=here/'oot2_ipad_v9_native.patch'
    if hashlib.sha256(patch.read_bytes()).hexdigest()!=meta['patch_sha256']:raise ValueError('v9 patch identity')
    for name in meta['new_files']:
        if (root/name).exists():raise ValueError('v9 payload already exists')
    subprocess.run(['git','-C',str(root),'apply','--check',str(patch.resolve())],check=True)
    originals={n:(root/n).read_bytes() for n in meta['originals']}
    try:
        subprocess.run(['git','-C',str(root),'apply',str(patch.resolve())],check=True)
        script=root/'scripts/build_ipa_from_nsp.py';code=script.read_text()
        if code.count(ANCHOR)!=1 or "if fam['nup'].siblings:" not in code:raise ValueError('v9 extraction contract')
        injection=INJECTION.replace('and not g.get("programs", "")','and not g.get("programs", "")\n            and not fam["nup"].siblings')
        code=code.replace(ANCHOR,ANCHOR+injection);compile(code,str(script),'exec');script.write_text(code)
        actual=subprocess.check_output(['python3',str(root/'dm/gfx/tools/dmsh_chain.py')],text=True).strip()
        if actual!=CHAIN:raise ValueError('v9 translation chain changed')
        (root/'.oot2-v9.json').write_text(json.dumps({'base':PIN,'chain':CHAIN,'patch_sha256':meta['patch_sha256']})+'\n')
    except BaseException:
        for n,b in originals.items():(root/n).write_bytes(b)
        for n in meta['new_files']:(root/n).unlink(missing_ok=True)
        (root/'.oot2-v9.json').unlink(missing_ok=True)
        raise
    print('OOT2 v9: official runtime and translator; metadata-only full R/M export; chain '+CHAIN)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);prepare(p.parse_args().root)
