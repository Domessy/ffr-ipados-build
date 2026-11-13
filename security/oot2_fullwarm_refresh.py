#!/usr/bin/env python3
"""Apply reviewed November 13 host backports after the exact v8 fullwarm recipe."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def digest(data): return hashlib.sha256(data).hexdigest()


def prepare(root):
    root=Path(root).resolve();here=Path(__file__).parent
    recipe=here/'oot2_fullwarm_refresh_manifest.json';meta=json.loads(recipe.read_text())
    patch=here/'oot2_fullwarm_refresh.patch'
    if digest(patch.read_bytes())!=meta['patch_sha256']:raise ValueError('refresh patch identity')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=meta['base']:
        raise ValueError('refresh base identity')
    originals={}
    for name,want in meta['originals'].items():
        path=root/name
        if path.is_symlink() or digest(path.read_bytes())!=want:raise ValueError('refresh original source identity: '+name)
        originals[name]=path.read_bytes()
    for name in meta['new_files']:
        if (root/name).exists() or (root/name).is_symlink():raise ValueError('refresh new file exists')
    subprocess.run(['git','-C',str(root),'apply','--check',str(patch.resolve())],check=True)
    try:
        subprocess.run(['git','-C',str(root),'apply',str(patch.resolve())],check=True)
        for name,want in meta['outputs'].items():
            if digest((root/name).read_bytes())!=want:raise ValueError('refresh resulting source identity')
        if ('"'+meta['chain']+'"') not in (root/'dm/gfx/nvn/dmsh_chain.h').read_text():raise ValueError('refresh changed shader chain')
        (root/'.oot2-fullwarm-refresh.json').write_text(json.dumps({'recipe_sha256':digest(recipe.read_bytes()),'patch_sha256':meta['patch_sha256'],'upstream':meta['upstream'],'chain':meta['chain']},indent=2)+'\n')
    except BaseException:
        for name,data in originals.items():(root/name).write_bytes(data)
        for name in meta['new_files']:(root/name).unlink(missing_ok=True)
        (root/'.oot2-fullwarm-refresh.json').unlink(missing_ok=True)
        raise
    print('OOT2 host refresh prepared: visibility, live ghost lifetime/views, pipeline prediction, sparse notes and archive ordering; original shader chain retained.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);prepare(p.parse_args().root)
