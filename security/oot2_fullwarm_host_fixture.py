#!/usr/bin/env python3
"""Exercise host-kit reconstruction using ONLY public synthetic smoke modules."""
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import zipfile
from oot2_fullwarm_host import PIN, CHAIN, TITLE, rebuild
from oot2_ipad_aot import TABLES, digest


def main(native, smoke, output):
    native, smoke, output = map(Path, (native, smoke, output)); output.mkdir()
    files = {}
    for path in (smoke / 'patched').iterdir(): files['patched/' + path.name] = path
    for folder in ('dm', 'Assets.xcassets'):
        for path in (smoke / 'project/Gen' / folder).rglob('*'):
            if path.is_file(): files['Gen/' + folder + '/' + path.relative_to(smoke / 'project/Gen' / folder).as_posix()] = path
    files['Gen/Info.plist'] = smoke / 'project/Gen/Info.plist'
    files['generated/game_profile.h'] = native / 'dm/host/gen' / TITLE / 'game_profile.h'
    for path in (native / 'dm/games' / TITLE).iterdir():
        if path.suffix == '.tsv' or path.name == 'patches.py': files['profile/' + TITLE + '/' + path.name] = path
    manifest = {'format': 1, 'title': TITLE, 'package': 'v131072', 'source_revision': PIN, 'shader_chain': CHAIN,
                'optimization_recipe_sha256': digest(Path(__file__).with_name('oot2_ipad_v8_manifest.json')),
                'host_only_rebuild_validated': False,
                'files': {name: {'bytes': path.stat().st_size, 'sha256': digest(path)} for name, path in files.items()}}
    tarpath = output / 'kit.tar'
    with tarfile.open(tarpath, 'w') as tar:
        data = json.dumps(manifest).encode(); member = tarfile.TarInfo('manifest.json'); member.size = len(data)
        tar.addfile(member, io.BytesIO(data))
        for name, path in files.items(): tar.add(path, arcname=name, recursive=False)
    kit = output / 'kit.tar.zst'
    subprocess.run(['zstd', '-q', str(tarpath), '-o', str(kit)], check=True)
    slim = output / 'input.ipa'; app = smoke / 'derived/Build/Products/Release-iphoneos/DmIOS.app'
    import plistlib
    info = plistlib.loads((app / 'Info.plist').read_bytes())
    info['CFBundleIdentifier'] = 'org.nxnative.0400486024dec000'
    with zipfile.ZipFile(slim, 'w') as z:
        prefix = 'Payload/Game.app/'
        z.writestr(prefix + 'Info.plist', plistlib.dumps(info))
        z.write(app / info['CFBundleExecutable'], prefix + info['CFBundleExecutable'])
        for name, path in files.items():
            if name.startswith('Gen/dm/'): z.write(path, prefix + name.removeprefix('Gen/'))
        for name in TABLES: z.writestr(prefix + 'dm/' + name, '# synthetic public fixture\n')
        z.writestr(prefix + f'msl/b-{CHAIN}.img', b'Synthetic marker; no game shaders')
    executable = rebuild(native, kit, slim, output / 'rebuilt')
    if executable.stat().st_size < 100000: raise ValueError('missing compiled host')
    print('PASS: verified host-kit unpack, actual gen_embed, production unsigned iOS rebuild; no retail data.')


if __name__ == '__main__': main(*sys.argv[1:])
