#!/usr/bin/env python3
"""Public Mac/iOS gates for the unchanged complete upstream source tree."""
from pathlib import Path
import json,os,subprocess,sys
from oot2_prepare_ipad_v10 import PIN,CHAIN,TITLE,recipe

def main(root,work):
    root=Path(root).resolve();work=Path(work).resolve();work.mkdir(exist_ok=False)
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=PIN:raise ValueError('v10 pin')
    if subprocess.check_output([sys.executable,str(root/'dm/gfx/tools/dmsh_chain.py')],text=True).strip()!=CHAIN:raise ValueError('v10 chain')
    if json.loads((root/'.oot2-v10.json').read_text())!={'base':PIN,'chain':CHAIN,'recipe_sha256':recipe()}:raise ValueError('v10 provenance')
    subprocess.run([sys.executable,str(root/'dm/gfx/tools/tool_lock.py'),'--check-tools'],check=True)
    env=dict(os.environ,DMSH_TEST_XLATE=str(root/'dm/gfx/tools/dmsh_xlate_bin/dmsh_xlate'),DMSH_TEST_METAL='1',GAME=TITLE)
    suites=['dm/gfx/tests/test_dmsh_raw_noinline.py','dm/gfx/tests/test_dmsh_shfl.py','dm/gfx/tests/test_dmsh_maxwell_ftz.py','dm/gfx/tests/test_spirv_ordered_ne.py','dm/tools/tests/test_nsp_chain.py','dm/tools/tests/test_pso_offline.py']
    subprocess.run([sys.executable,'-m','unittest','-q',*suites],cwd=root,env=env,check=True)
    subprocess.run(['make','-C',str(root/'dm/host'),'GAME='+TITLE,'-j3',f'gen/{TITLE}/dmhost'],check=True)
    names=['t_pso_prewarm','t_pool_replay','t_arena_trim','t_pso_demand_record']
    subprocess.run(['make','-C',str(root/'dm/gfx/tests'),'GAME='+TITLE,'-j3',*names],check=True)
    for name in names:
        result=subprocess.run([str(root/'dm/gfx/tests'/name)],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,check=False,timeout=300)
        print(result.stdout,flush=True)
        result.check_returncode()
        if 'not run' in result.stdout or 'no Metal' in result.stdout:raise RuntimeError('v10 Metal gate skipped: '+name)
    from oot2_aot_pilot import pilot
    pilot(root,work/'ios-pilot')
    subprocess.run([sys.executable,str(root/'dm/ios/tools/build_smoke.py'),'--output',str(work/'ios-smoke')],env=env,check=True)
    print('PASS: v10 official host/translator, actual prewarm producer and lookup, pool/arena/demand fixtures, iOS Metal archives and production compile/link. iPad gameplay untested.')
if __name__=='__main__':main(*sys.argv[1:])
