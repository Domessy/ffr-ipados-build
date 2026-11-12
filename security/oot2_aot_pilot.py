#!/usr/bin/env python3
"""Public iOS Metal-4 AOT fixture: render, compute, second-entry constants/cache.

No game inputs and no device access. This proves cross-compilation only;
archive lookup on the user's iPad remains a runtime check.
"""
import argparse
from pathlib import Path
import subprocess
import sys


def pilot(root, work):
    root, work = Path(root).resolve(), Path(work).resolve()
    sys.path.insert(0, str(root / 'dm/gfx/tools'))
    import pso_offline as po
    work.mkdir(parents=True, exist_ok=True)
    libs = work / 'libraries'; libs.mkdir(exist_ok=True)
    programs = {
        'v': '#include <metal_stdlib>\nusing namespace metal;\nvertex float4 vmain(uint i [[vertex_id]]) { return float4(float(i),0,0,1); }\n',
        'f': '#include <metal_stdlib>\nusing namespace metal;\nfragment float4 fmain() { return float4(1); }\n',
        'c': '#include <metal_stdlib>\nusing namespace metal;\n'
             f'constant bool dm_border_off [[function_constant({po.abi.BORDER_FC})]];\n'
             'kernel void first(device uint *out [[buffer(0)]], uint i [[thread_position_in_grid]]) { out[i]=i; }\n'
             'kernel void cmain(device uint *out [[buffer(0)]], uint i [[thread_position_in_grid]]) { out[i]=dm_border_off ? i : i+1; }\n',
    }
    for name, code in programs.items():
        source = work / (name + '.metal'); source.write_text(code)
        air = work / (name + '.air')
        subprocess.run(['xcrun', '-sdk', 'iphoneos', 'metal', '-std=metal4.0', '-mios-version-min=27.0', '-c', str(source), '-o', str(air)], check=True)
        subprocess.run(['xcrun', '-sdk', 'iphoneos', 'metallib', str(air), '-o', str(libs / (name + '.metallib'))], check=True)
    args = (libs, [('v', 'vmain', 'f', 'fmain')], work / 'batch', 'applegpu_g17g', 'ios', '27.0', po.tool_version('ios'))
    archive, reused = po.compile_batch(*args, computes=[('c', 'cmain')])
    assert not reused and archive.stat().st_size > 32
    assert po.read_failed(work / 'batch', 'applegpu_g17g') == ([], [])
    _, reused = po.compile_batch(*args, computes=[('c', 'cmain')]); assert reused
    print('PASS: render and specialized compute archived for iOS/g17g; identical rerun reused the cache. iPad execution not tested.')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('root'); ap.add_argument('work')
    a = ap.parse_args(); pilot(a.root, a.work)
