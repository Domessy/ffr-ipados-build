#!/usr/bin/env python3
"""Real iOS offline archives and native CPU checks from synthetic inputs only."""
from pathlib import Path
import subprocess
import sys
from oot2_v9_archives import configure

def main(root,work):
    root,work=map(lambda p:Path(p).resolve(),(root,work));work.mkdir(exist_ok=False)
    aot,full,pack=configure()
    tests=root/'dm/gfx/tests'
    targets=['t_serial_owner','t_pend_index','t_fstep','t_res_cb','t_pso_stall','t_rt_recycle','t_lazy_clear_order','t_vis_need']
    subprocess.run(['make','-C',str(tests),'GAME=0400486024DEC000','-j','3',*targets],check=True)
    for name in ['t_serial_owner','t_pend_index','t_fstep']:subprocess.run([str(tests/name)],check=True)
    tool=full.build_exporter(root)
    subprocess.run([str(tool),'--fixture-constants'],check=True)
    import oot2_fullwarm_fixture as fixture
    fixture.CHAIN=aot.CHAIN
    fixture.fixture(work/'fixture',root,tool)
    report=full.export(root,work/'fixture',work/'scripts')
    assert report['failed_tasks']==0 and report['stale_keys']==0
    image=work/f'fixture/msl/b-{aot.CHAIN}'
    result=full.compile_lists(root,image,work/'scripts',work/'cache',work/'bundle')
    again=full.compile_lists(root,image,work/'scripts',work/'cache',work/'bundle')
    assert again['reused_groups']==result['coverage']['periods']
    from oot2_aot_pilot import pilot
    pilot(root,work/'aot-pilot')
    print('PASS: v9 native CPU checks, graphical fixture compilation, real iOS R/M archives and complete reuse. GPU execution not performed.')

if __name__=='__main__':main(*sys.argv[1:])
