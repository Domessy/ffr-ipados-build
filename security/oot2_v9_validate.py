#!/usr/bin/env python3
"""Public checks for the exact v9 translator/runtime contract."""
import json
from pathlib import Path
import subprocess
import sys
from oot2_prepare_ipad_v9 import PIN, CHAIN

def validate(root):
    root=Path(root).resolve()
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=PIN:raise ValueError('v9 pin')
    if subprocess.check_output([sys.executable,str(root/'dm/gfx/tools/dmsh_chain.py')],text=True).strip()!=CHAIN:raise ValueError('v9 chain')
    m=json.loads((root/'.oot2-v9.json').read_text());want=json.loads(Path(__file__).with_name('oot2_ipad_v9_manifest.json').read_text())
    if m!={'base':PIN,'chain':CHAIN,'patch_sha256':want['patch_sha256']}:raise ValueError('v9 provenance')
    subprocess.run([sys.executable,str(root/'dm/gfx/tools/tool_lock.py'),'--check-tools'],check=True)
    print('PASS: genuine v9 chain, upstream revision and locked translator/compilers verified.')

if __name__=='__main__':validate(sys.argv[1])
