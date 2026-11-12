#!/usr/bin/env python3
"""Export native v8 R/M descriptors without a GPU compiler, compile for iPad.

The export uses the actual iOS libraries through Metal unified libraries.
No shader translation, guest execution, save access or device is involved.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

try:
    from .oot2_ipad_aot import CHAIN, GPU, digest
    from .oot2_fullwarm_sdk import generate as generate_sdk
except ImportError:
    from oot2_ipad_aot import CHAIN, GPU, digest
    from oot2_fullwarm_sdk import generate as generate_sdk


def build_exporter(root):
    root = Path(root).resolve()
    generate_sdk(root / 'dm/gfx/nvn/oot2_fullwarm_enums.h')
    subprocess.run(['make', '-C', str(root / 'dm/gfx/tests'), 'GAME=0400486024DEC000', 'oot2_fullwarm_export'], check=True)
    return root / 'dm/gfx/tests/oot2_fullwarm_export'


def export(root, inputs, output):
    root, inputs, output = map(lambda p: Path(p).resolve(), (root, inputs, output))
    executable = root / 'dm/gfx/tests/oot2_fullwarm_export'
    if not executable.is_file(): executable = build_exporter(root)
    if output.exists(): raise ValueError('full-list export output already exists')
    # Ensure the tool never inherits the player's controls, saves or overrides.
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DM_', 'DMSH_'))}
    subprocess.run([str(executable), str(inputs / 'msl'), str(inputs / 'dm/shader_map.tsv'), str(output)], env=env, check=True)
    return validate_export(output)


def validate_export(directory):
    directory = Path(directory)
    meta = json.loads((directory / 'coverage.json').read_text())
    if (meta.get('chain') != CHAIN or meta.get('failed_tasks') != 0 or meta.get('stale_keys', 0) != 0
        or meta.get('pipeline_creation_used') is not False or meta.get('new_shaders_compiled') is not False):
        raise ValueError('full prewarm exporter failed coverage/identity')
    scripts = sorted(directory.glob('prewarm-*.mtl4-json'))
    if len(scripts) != meta.get('periods') or not scripts: raise ValueError('full prewarm periods incomplete')
    render = mesh = 0
    for path in scripts:
        cfg = json.loads(path.read_text()); descriptors = cfg['pipeline_descriptors']
        render += len(descriptors.get('render_pipeline_descriptors', []))
        mesh += len(descriptors.get('mesh_render_pipeline_descriptors', []))
        for lib in cfg['libraries']:
            if not re.fullmatch(r'[A-Za-z0-9_.@-]{1,180}\.metallib', lib['path']): raise ValueError('full prewarm library path')
    if not render or not mesh or render != meta.get('render_rows') or mesh != meta.get('mesh_rows'):
        raise ValueError('full prewarm render/mesh rows missing')
    if render != meta.get('emitted_render') or mesh != meta.get('emitted_mesh'): raise ValueError('full prewarm counter mismatch')
    return meta


def materialize(configuration, image, destination, po):
    """Resolve exact iOS IR bytes; specialize secondary entries in isolated libs.

    No Mac IR, generated shader, renamed chain or copied Mac index is accepted.
    """
    destination = Path(destination); destination.mkdir(parents=True, exist_ok=True)
    source = po.romfs.Path(po.shader_lib.view(image))
    cfg = json.loads(json.dumps(configuration))
    by_label = {}; declarations = {}
    for item in cfg['libraries']:
        name = item['path']
        if not re.fullmatch(r'[A-Za-z0-9_.@-]{1,180}\.metallib', name): raise ValueError('full prewarm library path')
        raw = (source / name).read_bytes()
        target = destination / name; target.write_bytes(raw)
        item['path'] = str(target.resolve()); by_label[item['label']] = target
        declarations[item['label']] = po.constants(target)
    fds = cfg['function_descriptors']
    functions = {f['label']: f for f in fds['library_function_descriptors']}
    for special in fds.get('specialized_function_descriptors', []):
        fn = functions.get(special['function_descriptor'].removeprefix('fnd:'))
        if fn is None: raise ValueError('full prewarm nested specialization')
        label = fn['library'].removeprefix('lib:'); name = fn['name']
        if not po.needs_cut(declarations[label], name): continue
        cut_label = label + '_' + name
        if cut_label not in by_label:
            data = po.dmsh_side.cut(by_label[label].read_bytes(), {name})[1]
            target = destination / (cut_label + '.metallib'); target.write_bytes(data)
            by_label[cut_label] = target
            cfg['libraries'].append({'label': cut_label, 'path': str(target.resolve())})
        fn['library'] = 'lib:' + cut_label
    return cfg


def group_key(configuration, toolchain):
    cfg = json.loads(json.dumps(configuration)); libraries = hashlib.sha256()
    for lib in cfg['libraries']:
        libraries.update(lib['label'].encode() + b'\0' + bytes.fromhex(digest(lib['path'])))
        lib['path'] = lib['label']
    body = {'configuration': cfg, 'library_bytes': libraries.hexdigest(), 'platform': 'ios', 'gpu': GPU,
            'min_os': '27.0', 'metal_tt': toolchain, 'format': 1}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def compile_lists(root, image, scripts, cache, bundle):
    root, image, scripts, cache, bundle = map(Path, (root, image, scripts, cache, bundle))
    coverage = validate_export(scripts)
    sys.path.insert(0, str(root.resolve() / 'dm/gfx/tools')); import pso_offline as po
    toolchain = po.tool_version('ios'); cache.mkdir(parents=True, exist_ok=True); bundle.mkdir(parents=True, exist_ok=True)
    archives = {}; reused = 0
    def progress(done):
        path = cache.parent / 'progress.json'; temporary = path.with_suffix('.partial')
        temporary.write_text(json.dumps({'completed': done, 'total': coverage['periods'],
            'percent': round(100*done/coverage['periods'], 1), 'reused': reused,
            'gib': round(sum(item['bytes'] for item in archives.values()) / 1024**3, 2)}))
        os.replace(temporary, path)
    progress(0)
    for index, script in enumerate(sorted(scripts.glob('prewarm-*.mtl4-json'))):
        work = cache / f'{index:05d}'; work.mkdir(exist_ok=True)
        data = materialize(json.loads(script.read_text()), image, work / 'libraries', po)
        key = group_key(data, toolchain); key_file = work / 'key'; archive = work / f'{GPU}.mtl4a'; checksum = work / 'sha256'
        if not (archive.is_file() and not archive.is_symlink() and key_file.is_file() and checksum.is_file()
                and key_file.read_text().strip() == key and checksum.read_text().strip() == digest(archive)):
            key_file.unlink(missing_ok=True)
            js = work / 'pipelines.mtl4-json'; js.write_text(json.dumps(data, sort_keys=True))
            part = work / 'archive.partial'; part.unlink(missing_ok=True)
            count = sum(len(rows) for rows in data['pipeline_descriptors'].values())
            # Fail the full-list build if a valid row cannot compile. Do not
            # publish a partial archive while calling the list fully prepared.
            po.compile_archive(js, part, work, GPU, 'ios', '27.0', count)
            if part.stat().st_size < 32: raise ValueError('full prewarm archive empty')
            os.replace(part, archive)
            checksum.write_text(digest(archive) + '\n'); key_file.write_text(key + '\n')
        else: reused += 1
        subprocess.run([str(root / 'dm/gfx/tests/oot2_fullwarm_export'), '--validate-archive', str(archive)], check=True)
        shutil.rmtree(work / 'libraries')
        name = f'{GPU}-prewarm-{index:05d}.mtl4a'
        target = bundle / name
        shutil.copyfile(archive, target)
        archives[name] = {'bytes': target.stat().st_size, 'sha256': digest(target), 'key': key}
        progress(index+1)
        print(f'Full prewarm: groups={index+1}/{coverage["periods"]}; progress={100*(index+1)/coverage["periods"]:.1f}%', flush=True)
    report = {'format': 1, 'chain': CHAIN, 'gpu': GPU, 'platform': 'ios', 'coverage': coverage, 'archives': archives,
              'metal_tt': toolchain, 'reused_groups': reused, 'index_mode': 'Metal descriptor lookup; no Mac filename/digest index copied'}
    for stale in bundle.glob(GPU + '-prewarm-*.mtl4a'):
        if stale.name not in archives: stale.unlink()
    (bundle / 'fullwarm.json').write_text(json.dumps(report, indent=2) + '\n')
    (bundle / 'prewarm.tsv').write_text(f'chain\t{CHAIN}\nplatform\tios\ngpu\t{GPU}\nfiles\t{len(archives)}\n')
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='mode', required=True)
    s = sub.add_parser('build-exporter'); s.add_argument('root')
    s = sub.add_parser('export'); s.add_argument('root'); s.add_argument('inputs'); s.add_argument('output')
    s = sub.add_parser('compile'); s.add_argument('root'); s.add_argument('image'); s.add_argument('scripts'); s.add_argument('cache'); s.add_argument('bundle')
    a = p.parse_args()
    if a.mode == 'build-exporter': build_exporter(a.root)
    elif a.mode == 'export': export(a.root, a.inputs, a.output)
    else: compile_lists(a.root, a.image, a.scripts, a.cache, a.bundle)


if __name__ == '__main__': main()
