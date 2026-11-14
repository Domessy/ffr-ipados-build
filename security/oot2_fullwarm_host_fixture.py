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


def main(native, smoke, output, base_archive=None, full=None):
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
    import struct, hashlib
    from oot2_local_bundle import identity
    pc=output/'pc'; pc_results=pc/'resultats'; pc_results.mkdir(parents=True)
    local=pc/'local-bundle-v6'; romfs=local/'extract/v131072/RomFS.img'; romfs.parent.mkdir(parents=True)
    body=b'public synthetic RomFS body'; index=b'public synthetic index'
    romfs.write_bytes(struct.pack('<8sQQQ',b'DMROMFS1',32+len(body),len(index),1)+body+index)
    ident=identity(romfs)
    (local/'romfs-manifest.json').write_text(json.dumps({'bytes':romfs.stat().st_size,'identity':ident,'sha256':hashlib.sha256(romfs.read_bytes()).hexdigest()}))
    with zipfile.ZipFile(slim,'a') as z:
        z.writestr(prefix+'romfs.id',f'DMROMFSID1 title={TITLE} size={ident[0]} index={ident[1]}')
    executable = rebuild(native, kit, slim, output / 'rebuilt')
    if executable.stat().st_size < 100000: raise ValueError('missing compiled host')
    if base_archive is not None:
        from oot2_fullwarm_pack import repack
        from oot2_ipad_aot import GPU
        base=output/'base';base.mkdir()
        shutil.copyfile(base_archive,base/(GPU+'.mtl4a'))
        (base/'archive.tsv').write_text(f'platform\tios\t27.0\narch\t{GPU}\nbases\t1\nrest\t0\n')
        (base/'prebuilt.tsv').write_text(f'chain\t{CHAIN}\n')
        full=Path(full);report=json.loads((full/'fullwarm.json').read_text())
        report['host']=json.loads((output/'rebuilt/host-result.json').read_text())
        (full/'fullwarm.json').write_text(json.dumps(report))
        result=repack(slim,base,full,executable,output/'verified-output.ipa')
        assert result['original_resources_preserved_except_executable']
        assert report['host']['host_refresh']['upstream']
        from unittest.mock import patch
        from types import SimpleNamespace
        import oot2_gateway as gateway, ffr_ssh_gate as parent
        with (output/'verified-output.ipa').open('rb') as stream:
            with patch.object(gateway,'ROOT',pc), patch.object(gateway,'OUTPUT',pc_results), patch.object(sys,'stdin',SimpleNamespace(buffer=stream)):
                assert gateway.dispatch('oot2-fullwarm-v8-write-slim',parent)==0
        delivered=pc_results/'ZeldaOcarinaOfTime-ipad-v8-fullwarm-livecontainer.ipa'
        with zipfile.ZipFile(delivered) as z:
            assert z.testzip() is None
            assert z.read(prefix+'romfs.img')==romfs.read_bytes()
            assert prefix+'pso/rest_pairs.tsv' not in z.namelist()
        print('PASS: production receive gateway and final RomFS assembly verified with zero remaining pairs.')
        print('PASS: complete synthetic IPA repacked with actual iOS archives and rebuilt host; original resources rehashed.')
    print('PASS: verified host-kit unpack, actual gen_embed, production unsigned iOS rebuild; no retail data.')


if __name__ == '__main__': main(*sys.argv[1:])
