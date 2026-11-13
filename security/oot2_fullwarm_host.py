#!/usr/bin/env python3
"""Rebuild only the unsigned native iOS executable from a verified v8 host kit.

Synthetic resource markers exercise staging only. Final packaging takes ONLY
this executable; all game resources remain from the original verified IPA.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import tarfile
try:
    from .oot2_ipad_aot import CHAIN, digest, inspect_ipa
except ImportError:
    from oot2_ipad_aot import CHAIN, digest, inspect_ipa

TITLE = '0400486024DEC000'
PIN = 'ccd834e06a3938834bb5579e2ccc6a0ad13d3970'
LIMIT = 1 << 30


def unpack(archive, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    proc = subprocess.Popen(['zstd', '-q', '-d', '-c', str(archive)], stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=proc.stdout, mode='r|') as tar:
            first = tar.next()
            if not first or first.name != 'manifest.json' or not first.isfile() or first.size > 1 << 20:
                raise ValueError('host kit manifest')
            manifest = json.load(tar.extractfile(first))
            recipe = digest(Path(__file__).with_name('oot2_ipad_v8_manifest.json'))
            if any(manifest.get(k) != v for k, v in {'format': 1, 'title': TITLE, 'package': 'v131072',
                    'source_revision': PIN, 'shader_chain': CHAIN, 'optimization_recipe_sha256': recipe}.items()):
                raise ValueError('host kit identity')
            files = manifest['files']; seen = set(); total = 0
            if not files or len(files) > 10000: raise ValueError('host kit count')
            while (member := tar.next()) is not None:
                name = member.name; path = Path(name); total += member.size
                if (name in seen or name not in files or not member.isfile() or total > LIMIT
                    or path.is_absolute() or '..' in path.parts or '\\' in name
                    or path.parts[0] not in ('patched', 'Gen', 'profile', 'generated')):
                    raise ValueError('host kit member')
                spec = files[name]
                if member.size != spec['bytes']: raise ValueError('host kit size')
                data = tar.extractfile(member).read()
                if hashlib.sha256(data).hexdigest() != spec['sha256']: raise ValueError('host kit hash')
                target = destination / name; target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data); seen.add(name)
            if seen != set(files): raise ValueError('host kit incomplete')
        if proc.wait(timeout=30): raise ValueError('host kit decompression')
        return manifest
    except BaseException:
        shutil.rmtree(destination)
        raise
    finally:
        proc.stdout.close()
        if proc.poll() is None: proc.kill(); proc.wait()


def rebuild(root, kit, slim, output):
    root, kit, slim, output = map(lambda p: Path(p).resolve(), (root, kit, slim, output))
    if output.exists(): raise ValueError('host output exists')
    output.mkdir(parents=True)
    unpack(kit, output / 'kit'); captured = output / 'kit'
    prefix = inspect_ipa(slim)
    import zipfile
    with zipfile.ZipFile(slim) as archive:
        # The embedded fixup/constant tables must belong to this exact app.
        for path in (captured / 'Gen/dm').glob('*'):
            if path.is_file() and archive.read(prefix + 'dm/' + path.name) != path.read_bytes():
                raise ValueError('host kit differs from IPA tables')
        original_info = plistlib.loads(archive.read(prefix + 'Info.plist'))
    ios = root / 'dm/ios'; project = output / 'project'; project.mkdir()
    shutil.copytree(captured / 'Gen', project / 'Gen')
    gen = project / 'Gen'
    for name in ('Sources', 'tools'): (project / name).symlink_to(ios / name, target_is_directory=True)
    shutil.copyfile(ios / 'project.yml', project / 'project.yml')
    icons = list((gen / 'Assets.xcassets').glob('*.appiconset'))
    if len(icons) > 1: raise ValueError('ambiguous captured icon set')
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DM_', 'DMSH_'))}
    env.update(GAME=TITLE, DM_GAME=TITLE, DM_GAMES_DIR=str(captured / 'profile'), DM_GAMES_FIRST='1',
               DM_BUNDLE_ID=original_info['CFBundleIdentifier'], DM_DISPLAY_NAME=original_info.get('CFBundleDisplayName', 'Ocarina of Time'),
               DM_APP_VERSION=original_info.get('CFBundleShortVersionString', '1.0'), DM_TEAM_ID='', DM_SCHEME_NAME='DmIOS',
               DM_APPICON=icons[0].stem if icons else '', DM_SHOW_FPS='YES', DM_LANG='en-US')
    def run(*command, capture=False):
        return subprocess.run([str(c) for c in command], cwd=project, env=env, check=True,
                              text=True, stdout=subprocess.PIPE if capture else None)
    # Real captured profile and real patched modules, never synthetic code.
    config = run(sys.executable, ios / 'tools/gen_build.py', root / 'dm/host', gen, capture=True).stdout
    header = root / 'dm/host/gen' / TITLE / 'game_profile.h'
    # The generated comment names its source path, which changes on relocation.
    def definitions(path):
        return [line for line in path.read_text().splitlines() if not line.startswith('//')]
    if definitions(header) != definitions(captured / 'generated/game_profile.h'):
        raise ValueError('regenerated host profile differs')
    sys.path.insert(0, str(root / 'dm/games')); import game
    modules = game.load(captured / 'profile' / TITLE).modules_in(captured / 'patched')
    flags = run(sys.executable, ios / 'tools/gen_embed.py', captured / 'patched', gen / 'embed.S', *modules, capture=True).stdout.strip()
    (gen / 'dm.xcconfig').write_text(config + f'OTHER_LDFLAGS = $(inherited) $(DM_FRAMEWORKS) {flags}\n')
    run('xcodegen', 'generate')
    romfs, shaders = output / 'romfs', output / 'shaders'; romfs.mkdir(); shaders.mkdir()
    marker = 'host-rebuild-staging-only.txt'
    for folder in (romfs, shaders): (folder / marker).write_text('Staging marker; excluded from final IPA.\n')
    derived = output / 'derived'
    run(sys.executable, ios / 'tools/gen_resources.py', project, romfs, marker, shaders, f'b-{CHAIN}', '', derived, root / 'dm/gfx/nvn/dmsh_chain.h')
    run('xcodebuild', '-project', project / 'DmIOS.xcodeproj', '-scheme', 'DmIOS', '-configuration', 'Release',
        '-destination', 'generic/platform=iOS', '-derivedDataPath', derived, '-jobs', '3',
        'CODE_SIGNING_ALLOWED=NO', 'CODE_SIGNING_REQUIRED=NO', 'CODE_SIGN_IDENTITY=',
        f'DM_XCODE_OUTPUT_ROOT={derived}', f'SYMROOT={derived}/Build/Products', f'OBJROOT={derived}/Build/Intermediates.noindex', 'build')
    app = derived / 'Build/Products/Release-iphoneos/DmIOS.app'
    info = plistlib.loads((app / 'Info.plist').read_bytes()); executable = app / info['CFBundleExecutable']
    if not executable.is_file() or (app / '_CodeSignature').exists() or (app / 'embedded.mobileprovision').exists():
        raise ValueError('unsigned rebuilt host missing')
    target = output / 'rebuilt-host'; shutil.copyfile(executable, target)
    (output / 'host-result.json').write_text(json.dumps({'source': PIN, 'chain': CHAIN, 'sha256': digest(target),
        'bytes': target.stat().st_size, 'real_kit_modules': True, 'unsigned': True,
        'host_refresh': json.loads((root/'.oot2-fullwarm-refresh.json').read_text()) if (root/'.oot2-fullwarm-refresh.json').exists() else None}, indent=2) + '\n')
    return target


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'kit', 'slim', 'output'): p.add_argument(name, type=Path)
    a = p.parse_args(); rebuild(a.root, a.kit, a.slim, a.output)
