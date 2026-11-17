#!/usr/bin/env python3
"""Complete immutable official tree; no local renderer or translator overlay."""
import hashlib,json,subprocess
from pathlib import Path
try:
    from .oot2_patch_nup_release import ANCHOR,INJECTION
except ImportError:
    from oot2_patch_nup_release import ANCHOR,INJECTION
PIN='e4b0d9b75d39c41c10fdcfec2f0b070df496d7e5'
CHAIN='a9bfaeb9fa8c'
TITLE='0400486024DEC000'
def recipe():return hashlib.sha256(Path(__file__).with_name('oot2_ipad_v10_manifest.json').read_bytes()).hexdigest()
def prepare(root):
    root=Path(root).resolve();m=json.loads(Path(__file__).with_name('oot2_ipad_v10_manifest.json').read_text())
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=PIN:raise ValueError('v10 exact upstream pin')
    for name,h in m['originals'].items():
        p=root/name
        if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=h:raise ValueError('v10 input identity')
    chain=subprocess.check_output(['python3',str(root/'dm/gfx/tools/dmsh_chain.py')],text=True).strip()
    if chain!=CHAIN:raise ValueError('v10 actual translation chain')
    script=root/'scripts/build_ipa_from_nsp.py';code=script.read_text()
    if code.count(ANCHOR)!=1 or "if fam['nup'].siblings:" not in code:raise ValueError('v10 NUP lifecycle contract')
    injection=INJECTION.replace('and not g.get("programs", "")','and not g.get("programs", "")\n            and not fam["nup"].siblings')
    code=code.replace(ANCHOR,ANCHOR+injection);compile(code,str(script),'exec');script.write_text(code)
    (root/'.oot2-v10.json').write_text(json.dumps({'base':PIN,'chain':CHAIN,'recipe_sha256':recipe()})+'\n')
    print('PASS: complete official v10 source; actual new shader chain '+CHAIN)
if __name__=='__main__':
    import sys;prepare(sys.argv[1])
