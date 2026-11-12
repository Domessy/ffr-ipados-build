#!/usr/bin/env python3
"""Synthetic iOS render/mesh prewarm data; no Nintendo files or GPU execution."""
import argparse
import json
from pathlib import Path
import subprocess

CHAIN = 'd24f05cf9d78'
SOURCE = r'''#include <metal_stdlib>
using namespace metal;
constant bool dm_border_off [[function_constant(120)]];
struct In { float4 p [[attribute(0)]]; };
vertex float4 vmain(In v [[stage_in]]) { return dm_border_off ? v.p : v.p * 2.0; }
fragment float4 fmain() { return float4(1, 0.5, 0.25, 1); }
struct V { float4 p [[position]]; };
struct P { uint n; };
using Mesh = metal::mesh<V, void, 3, 1, metal::topology::triangle>;
[[object]] void task(object_data P &p [[payload]], mesh_grid_properties grid) { p.n = 1; grid.set_threadgroups_per_grid(uint3(1)); }
[[object]] void block(object_data P &p [[payload]], mesh_grid_properties grid) { p.n = 1; grid.set_threadgroups_per_grid(uint3(1)); }
[[mesh]] void mmain(Mesh m, const object_data P &p [[payload]], uint tid [[thread_index_in_threadgroup]]) {
 if (!tid) { m.set_vertex(0, V{float4(-1,-1,0,1)}); m.set_vertex(1,V{float4(1,-1,0,1)}); m.set_vertex(2,V{float4(0,1,0,1)});
 m.set_index(0,0);m.set_index(1,1);m.set_index(2,2);m.set_primitive_count(p.n); }
}
'''


def fixture(root, native, executable):
    root, native = Path(root), Path(native)
    import sys
    sys.path.insert(0, str(native / 'dm/gfx/tools')); import dmsh_abi
    libs = root / f'msl/b-{CHAIN}'; libs.mkdir(parents=True)
    tables = root / 'dm'; tables.mkdir()
    source = root / 'fixture.metal'; source.write_text(SOURCE.replace('function_constant(120)', f'function_constant({dmsh_abi.BORDER_FC})'))
    air, library = root / 'fixture.air', root / 'fixture.metallib'
    subprocess.run(['xcrun', '-sdk', 'iphoneos', 'metal', '-std=metal4.0', '-mios-version-min=27.0', '-c', str(source), '-o', str(air)], check=True)
    subprocess.run(['xcrun', '-sdk', 'iphoneos', 'metallib', str(air), '-o', str(library)], check=True)
    entries = {'v': ('vertex', 'vmain'), 'f': ('pixel', 'fmain'), 't': ('task', 'task'), 'm': ('mesh', 'mmain'), 'n': ('mesh', 'mmain')}
    shader_map = 'package\tindex\tstage\tdm_ctl_sha16\tsource\n'
    for index, (key, (stage, entry)) in enumerate(entries.items()):
        (libs / f'{key}_b.metallib').write_bytes(library.read_bytes())
        reflection = {'chain': CHAIN, 'route': 'B', 'entry': entry, 'bindings': [], 'vertex_inputs': []}
        if key == 'v': reflection['vertex_inputs'] = [{'location': 0, 'msl_type': 'float4'}]
        if key in ('t', 'm', 'n'):
            reflection['mesh_stage'] = {'kind': 'ts' if key == 't' else 'ms', 'threads': 1, 'payload': 16, 'task': key == 'm'}
        if key == 'n': reflection['entry_object'] = 'block'
        (libs / f'{key}_b.json').write_text(json.dumps(reflection))
        shader_map += f'p.bin\t{index}\t{stage}\t{key}\tx\n'
    (tables / 'shader_map.tsv').write_text(shader_map)
    subprocess.run([str(executable), '--fixture-rows', str(tables / 'pso_manifest.tsv')], check=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('root'); p.add_argument('native'); p.add_argument('executable')
    a = p.parse_args(); fixture(a.root, a.native, a.executable)
