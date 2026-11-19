#!/usr/bin/env python3
"""Complete immutable runtime/translator, plus isolated runner metadata exporter."""
import hashlib,json,subprocess
from pathlib import Path
try:
    from .oot2_patch_nup_release import ANCHOR,INJECTION
    from .oot2_refresh_v11_profile import refresh_profile
except ImportError:
    from oot2_patch_nup_release import ANCHOR,INJECTION
    from oot2_refresh_v11_profile import refresh_profile
PIN='0b5fd6020093407af8bb5ad166e78e00bd2b7242'
CHAIN='03a3ac831bfb'
TITLE='0400486024DEC000'
def recipe():return hashlib.sha256(Path(__file__).with_name('oot2_ipad_v11_manifest.json').read_bytes()).hexdigest()
def prepare(root):
    root=Path(root).resolve();m=json.loads(Path(__file__).with_name('oot2_ipad_v11_manifest.json').read_text())
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=PIN:raise ValueError('v11 exact upstream pin')
    for name,h in m['originals'].items():
        p=root/name
        if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=h:raise ValueError('v11 input identity')
    chain=subprocess.check_output(['python3',str(root/'dm/gfx/tools/dmsh_chain.py')],text=True).strip()
    if chain!=CHAIN:raise ValueError('v11 actual translation chain')
    patch=Path(__file__).with_name('oot2_ipad_v11_native.patch')
    if hashlib.sha256(patch.read_bytes()).hexdigest()!=m['patch_sha256']:raise ValueError('v11 tool patch identity')
    subprocess.run(['git','-C',str(root),'apply','--check',str(patch.resolve())],check=True)
    refresh_profile(root,m['shader_profile_refresh'])
    subprocess.run(['git','-C',str(root),'apply',str(patch.resolve())],check=True)
    script=root/'scripts/build_ipa_from_nsp.py';code=script.read_text()
    if code.count(ANCHOR)!=1 or "if fam['nup'].siblings:" not in code:raise ValueError('v11 NUP lifecycle contract')
    injection=INJECTION.replace('and not g.get("programs", "")','and not g.get("programs", "")\n            and not fam["nup"].siblings')
    code=code.replace(ANCHOR,ANCHOR+injection);compile(code,str(script),'exec');script.write_text(code)
    (root/'.oot2-v11.json').write_text(json.dumps({'base':PIN,'chain':CHAIN,'recipe_sha256':recipe()})+'\n')
    print('PASS: complete official v11 source; actual new shader chain '+CHAIN)
if __name__=='__main__':
    import sys;prepare(sys.argv[1])
