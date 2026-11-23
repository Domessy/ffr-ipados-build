#!/usr/bin/env python3
"""Complete immutable runtime/translator, plus isolated runner metadata exporter."""
import hashlib,json,subprocess
from pathlib import Path
try:
    from .oot2_patch_nup_release import INJECTION
    from .oot2_v13_profile import verify_profile
except ImportError:
    from oot2_patch_nup_release import INJECTION
    from oot2_v13_profile import verify_profile
PIN='a63ca65115cbd586ccca3bedc4af89984eddf2e5'
CHAIN='26e1a5f38264'
TITLE='0400486024DEC000'
ANCHOR = '    aoc = stage_external_dlc(work, aoc_dir) if aoc_dir is not None else extract_aoc(nx, keys, repo, work, app, fam, logs)\n'

def nup_release_source(code):
    if code.count(ANCHOR) != 1 or 'OOT2_RUNNER_NUP_RELEASE_V1' in code:
        raise ValueError('v13 NUP lifecycle anchor')
    injection = INJECTION.replace('and not g.get("programs", "")',
        'and not g.get("programs", "")\n            and not fam["nup"].siblings\n            and aoc_dir is None')
    result = code.replace(ANCHOR, ANCHOR + injection)
    compile(result, 'build_ipa_from_nsp.py', 'exec')
    return result

def recipe():return hashlib.sha256(Path(__file__).with_name('oot2_ipad_v13_manifest.json').read_bytes()).hexdigest()
def prepare(root):
    root=Path(root).resolve();m=json.loads(Path(__file__).with_name('oot2_ipad_v13_manifest.json').read_text())
    if hashlib.sha256(Path(__file__).with_name('oot2_ipad_v13_defaults.env').read_bytes()).hexdigest()!=m['defaults_sha256']:raise ValueError('v13 defaults identity')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=PIN:raise ValueError('v13 exact upstream pin')
    for name,h in m['originals'].items():
        p=root/name
        if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=h:raise ValueError('v13 input identity')
    chain=subprocess.check_output(['python3',str(root/'dm/gfx/tools/dmsh_chain.py')],text=True).strip()
    if chain!=CHAIN:raise ValueError('v13 actual translation chain')
    patch=Path(__file__).with_name('oot2_ipad_v13_native.patch')
    if hashlib.sha256(patch.read_bytes()).hexdigest()!=m['patch_sha256']:raise ValueError('v13 tool patch identity')
    subprocess.run(['git','-C',str(root),'apply','--check',str(patch.resolve())],check=True)
    verify_profile(root,m['registered_profile'])
    script=root/'scripts/build_ipa_from_nsp.py';code=script.read_text()
    if "if fam['nup'].siblings:" not in code:raise ValueError('v13 NUP sibling contract')
    code=nup_release_source(code)
    subprocess.run(['git','-C',str(root),'apply',str(patch.resolve())],check=True)
    script.write_text(code)
    (root/'.oot2-v13.json').write_text(json.dumps({'base':PIN,'chain':CHAIN,'recipe_sha256':recipe()})+'\n')
    print('PASS: complete official v13 source; actual new shader chain '+CHAIN)
if __name__=='__main__':
    import sys;prepare(sys.argv[1])
