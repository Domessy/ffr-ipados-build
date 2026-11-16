#!/usr/bin/env python3
"""Build new-chain iOS archives; no old-chain library/archive is accepted."""
import json
import os
from pathlib import Path
import shutil
import sys
import zipfile
import subprocess
from oot2_prepare_ipad_v9 import PIN, CHAIN

def configure():
    import oot2_ipad_aot as aot, oot2_fullwarm as full, oot2_fullwarm_pack as pack
    # These are isolated processes. Preserve every default used by v8 callers.
    aot.CHAIN=full.CHAIN=pack.CHAIN=CHAIN
    return aot,full,pack

def build(root,slim,work):
    root,slim,work=map(lambda p:Path(p).resolve(),(root,slim,work));work.mkdir(exist_ok=False)
    aot,full,pack=configure()
    prefix=aot.inspect_ipa(slim)
    inputs=aot.extract_inputs(slim,work/'inputs')
    full.build_exporter(root)
    scripts=work/'descriptors';full.export(root,inputs,scripts)
    full.compile_lists(root,inputs/f'msl/b-{CHAIN}.img',scripts,work/'full-cache',work/'full-bundle')
    base=aot.compile_archive(root,slim,work/'base')
    host=work/'rebuilt-host'
    with zipfile.ZipFile(slim) as z:
        import plistlib
        info=plistlib.loads(z.read(prefix+'Info.plist'));host.write_bytes(z.read(prefix+info['CFBundleExecutable']))
    report=json.loads((work/'full-bundle/fullwarm.json').read_text());report['host']={'source':PIN,'chain':CHAIN,'sha256':aot.digest(host),'host_v9':json.loads((root/'.oot2-v9.json').read_text())}
    (work/'full-bundle/fullwarm.json').write_text(json.dumps(report,indent=2)+'\n')
    pack.repack(slim,base,work/'full-bundle',host,work/'fullwarm.ipa')
    print('PASS: new-chain base/compute and complete native R/M archives packed; original game resources preserved.')

if __name__=='__main__':build(*sys.argv[1:])
