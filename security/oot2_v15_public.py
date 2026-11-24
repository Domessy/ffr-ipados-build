#!/usr/bin/env python3
"""Public Mac/iOS gates for the unchanged complete upstream source tree."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
from oot2_prepare_ipad_v15 import PIN,CHAIN,TITLE,recipe

def main(root,work):
    root=Path(root).resolve();work=Path(work).resolve();work.mkdir(exist_ok=False)
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=PIN:raise ValueError('v15 pin')
    if subprocess.check_output([sys.executable,str(root/'dm/gfx/tools/dmsh_chain.py')],text=True).strip()!=CHAIN:raise ValueError('v15 chain')
    if json.loads((root/'.oot2-v15.json').read_text())!={'base':PIN,'chain':CHAIN,'recipe_sha256':recipe()}:raise ValueError('v15 provenance')
    from oot2_v15_profile import verify_profile
    verify_profile(root,json.loads(Path(__file__).with_name('oot2_ipad_v15_manifest.json').read_text())['registered_profile'])
    subprocess.run([sys.executable,'-m','unittest','-q','security.test_oot2_v15_restore'],cwd=Path(__file__).resolve().parents[1],check=True)
    subprocess.run([sys.executable,str(root/'dm/gfx/tools/tool_lock.py'),'--check-tools'],check=True)
    env=dict(os.environ,DMSH_TEST_XLATE=str(root/'dm/gfx/tools/dmsh_xlate_bin/dmsh_xlate'),DMSH_TEST_METAL='1',GAME=TITLE)
    subprocess.run(['make','-C',str(root/'dm/host/tests'),'GAME='+TITLE,'build/t_svc_memory'],check=True)
    suites=['dm/gfx/tests/test_dmsh_raw_noinline.py','dm/gfx/tests/test_dmsh_shfl.py','dm/gfx/tests/test_dmsh_maxwell_ftz.py','dm/gfx/tests/test_spirv_ordered_ne.py','dm/gfx/tests/test_dmsh_wide.py','dm/gfx/tests/test_dmsh_raw_last.py','dm/gfx/tests/test_dmsh_ampere_alu.py','dm/gfx/tests/test_dmsh_ampere_orin.py','dm/tools/tests/test_nsp_chain.py','dm/tools/tests/test_x18_select.py','dm/tools/tests/test_pso_offline.py','dm/tools/tests/test_dmsh_pairs.py','dm/tools/tests/test_split_bahs_entries.py','dm.tools.tests.test_nsp_incremental.SplitShaders','dm/tools/tests/test_shader_rewrites.py','dm/tools/tests/test_shader_toolchain_cache.py','dm/tools/tests/test_dmsh_code_fp.py','dm/tools/tests/test_ocarina_screen_shape.py','dm/tools/tests/test_ocarina_drs.py','dm/tools/tests/test_nsp_nup.py','dm/tools/tests/test_split_nxcx.py','dm/tools/tests/test_split_magics.py','dm/gfx/tests/test_dmsh_meshstage.py','dm.gfx.tests.test_dmsh_gather_offsets.Rewrite','dm/gfx/tests/test_dmsh_ampere_mem.py','dm/host/tests/test_memory_profile.py']
    subprocess.run([sys.executable,'-m','unittest','-q',*suites],cwd=root,env=env,check=True)
    subprocess.run(['make','-C',str(root/'dm/host'),'GAME='+TITLE,'-j3',f'gen/{TITLE}/dmhost'],check=True)
    subprocess.run(['make','-C',str(root/'dm/host/tests'),'GAME='+TITLE,'sync-wait'],check=True)
    names=['t_pso_prewarm','t_pool_replay','t_arena_trim','t_pso_demand_record','t_pso_skey','t_link_latch','t_link_drain','t_link_ticks','t_link_latch_cb','t_unwritten_store','t_upgrade_alias','t_mtl_init','t_pso_pending','t_mdx_prescan','t_upload_idle','t_rt_recycle','t_rt_lifetime','t_zero_colour','t_lazy_clear_order','t_upload_src','t_geometry_mesh','t_cbs_fault','t_library_data','t_pso_archive','t_dispatch_pipeline','t_upload_slots','t_depth_bounds','t_gfx_suspend','t_pkg_share','t_pkg_spare','t_pkg_evict','t_default_attrib','t_mesh_first_use','t_mfx_evict']
    subprocess.run(['make','-C',str(root/'dm/gfx/tests'),'GAME='+TITLE,'-j3',*names],check=True)
    for name in ('t_pso_skey','t_link_latch','t_link_drain','t_link_ticks','t_gfx_suspend'):
        subprocess.run([str(root/'dm/gfx/tests'/name)],check=True,timeout=120)
    # GPU fixtures compile here; a virtual runner cannot execute Metal 4 queues.
    # Execute the actual metadata-only producer and real iOS archive compiler instead.
    import oot2_fullwarm as full, oot2_fullwarm_v15_fixture as fixture
    full.CHAIN=fixture.CHAIN=CHAIN
    tool=full.build_exporter(root)
    subprocess.run([str(tool),'--fixture-constants'],check=True)
    fixture.fixture(work/'fixture',root,tool)
    report=full.export(root,work/'fixture',work/'scripts')
    if (report['failed_tasks'] or report['stale_keys'] or report['mesh_rows']!=2 or report['render_rows']!=5):raise ValueError('v15 native descriptor coverage')
    default_attribute = False
    descriptor_names=[]
    for path in (work/'scripts').glob('prewarm-*.mtl4-json'):
        script = json.loads(path.read_text())
        descriptor_names += [f['name'] for f in script['function_descriptors']['library_function_descriptors']]
        for row in script['pipeline_descriptors']['render_pipeline_descriptors']:
            vertex = row.get('vertex_descriptor')
            if vertex and any(a['buffer_index'] == 30 and a['offset'] == 16
                              for a in vertex['attributes']):
                if vertex['layouts'][30]['stride'] != 32:
                    raise ValueError('v15 default attribute stride')
                default_attribute = True
    if not default_attribute:
        raise ValueError('v15 fixture did not exercise an absent vertex attribute')
    if 'pullmain' not in descriptor_names:raise ValueError('v15 reflected pulling entry missing from exported descriptors')
    image=work/f'fixture/msl/b-{CHAIN}'
    first=full.compile_lists(root,image,work/'scripts',work/'cache',work/'bundle')
    again=full.compile_lists(root,image,work/'scripts',work/'cache',work/'bundle')
    if again['reused_groups']!=first['coverage']['periods']:raise ValueError('v15 archive cache reuse')
    from oot2_v15_official import install_indexes
    install_indexes(work/'scripts',work/'bundle')
    # Re-export in a new process: content-based index keys must remain stable.
    full.export(root,work/'fixture',work/'scripts-again')
    for path in (work/'scripts').glob('*.keys'):
        if path.read_bytes()!=(work/'scripts-again'/path.name).read_bytes():raise ValueError('v15 unstable native index')
    from oot2_aot_pilot import pilot
    pilot(root,work/'ios-pilot')
    subprocess.run([sys.executable,str(root/'dm/ios/tools/build_smoke.py'),'--output',str(work/'ios-smoke')],env=env,check=True)
    print('PASS: v15 complete host/translator, native metadata R/M producer, real iOS render/mesh archives, cache reuse and production compile/link. CPU pipeline-key and display-tick fixtures passed. GPU fixtures compiled only: runner has no Metal 4 GPU. iPad gameplay untested.')
if __name__=='__main__':main(*sys.argv[1:])
