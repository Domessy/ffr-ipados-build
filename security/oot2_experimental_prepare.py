#!/usr/bin/env python3
"""Apply experimental November 14 host backports after the exact v8 fullwarm recipe."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def digest(data): return hashlib.sha256(data).hexdigest()


def prepare(root):
    root=Path(root).resolve();here=Path(__file__).parent
    recipe=here/'oot2_experimental_manifest.json';meta=json.loads(recipe.read_text())
    patch=here/'oot2_experimental_native.patch'
    if digest(patch.read_bytes())!=meta['patch_sha256']:raise ValueError('experimental patch identity')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=meta['base']:
        raise ValueError('experimental base identity')
    originals={}
    for name,want in meta['originals'].items():
        path=root/name
        if path.is_symlink() or digest(path.read_bytes())!=want:raise ValueError('experimental original source identity: '+name)
        originals[name]=path.read_bytes()
    for name in meta['new_files']:
        if (root/name).exists() or (root/name).is_symlink():raise ValueError('experimental new file exists')
    subprocess.run(['git','-C',str(root),'apply','--check',str(patch.resolve())],check=True)
    try:
        subprocess.run(['git','-C',str(root),'apply',str(patch.resolve())],check=True)
        for name,want in meta['outputs'].items():
            if digest((root/name).read_bytes())!=want:raise ValueError('experimental resulting source identity')
        if ('"'+meta['chain']+'"') not in (root/'dm/gfx/nvn/dmsh_chain.h').read_text():raise ValueError('experimental changed shader chain')
        (root/'.oot2-experimental.json').write_text(json.dumps({'recipe_sha256':digest(recipe.read_bytes()),'patch_sha256':meta['patch_sha256'],'upstream':meta['upstream'],'chain':meta['chain']},indent=2)+'\n')
    except BaseException:
        for name,data in originals.items():(root/name).write_bytes(data)
        for name in meta['new_files']:(root/name).unlink(missing_ok=True)
        (root/'.oot2-experimental.json').unlink(missing_ok=True)
        raise
    print('OOT2 experimental host prepared: bounded depth zero copies and indexed storage-write commits; original shader chain retained.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);prepare(p.parse_args().root)
