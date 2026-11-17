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
    # GPU fixtures compile here; a virtual runner cannot execute Metal 4 queues.
    # Execute the actual metadata-only producer and real iOS archive compiler instead.
    import oot2_fullwarm as full, oot2_fullwarm_fixture as fixture
    full.CHAIN=fixture.CHAIN=CHAIN
    tool=full.build_exporter(root)
    subprocess.run([str(tool),'--fixture-constants'],check=True)
    fixture.fixture(work/'fixture',root,tool)
    report=full.export(root,work/'fixture',work/'scripts')
    if report['failed_tasks'] or report['stale_keys']:raise ValueError('v10 native descriptor coverage')
    image=work/f'fixture/msl/b-{CHAIN}'
    first=full.compile_lists(root,image,work/'scripts',work/'cache',work/'bundle')
    again=full.compile_lists(root,image,work/'scripts',work/'cache',work/'bundle')
    if again['reused_groups']!=first['coverage']['periods']:raise ValueError('v10 archive cache reuse')
    from oot2_aot_pilot import pilot
    pilot(root,work/'ios-pilot')
    subprocess.run([sys.executable,str(root/'dm/ios/tools/build_smoke.py'),'--output',str(work/'ios-smoke')],env=env,check=True)
    print('PASS: v10 complete host/translator, native metadata R/M producer, real iOS render/mesh archives, cache reuse and production compile/link. GPU fixtures compiled only: runner has no Metal 4 GPU. iPad gameplay untested.')
if __name__=='__main__':main(*sys.argv[1:])
