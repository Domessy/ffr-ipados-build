#!/usr/bin/env python3
"""Private full prewarm driver. Caller redirects the diagnostic off public CI."""
import json
from pathlib import Path
import sys
from oot2_ipad_aot import CHAIN, extract_inputs
from oot2_fullwarm import export, compile_lists
from oot2_fullwarm_host import rebuild
from oot2_fullwarm_pack import repack


def build(native, slim, kit, base_work, output):
    native,slim,kit,base_work,output=map(Path,(native,slim,kit,base_work,output))
    (output/'cache/progress.json').unlink(missing_ok=True)
    def phase(name):
        temporary=output/'phase.partial';temporary.write_text(json.dumps({'phase':name}));temporary.replace(output/'phase.json')
    phase('exporting native descriptors')
    inputs=base_work/'inputs'
    if not inputs.exists():extract_inputs(slim,inputs)
    export(native,inputs,output/'scripts')
    phase('compiling iOS render/mesh archives')
    compile_lists(native,inputs/f'msl/b-{CHAIN}',output/'scripts',output/'cache/work',output/'cache/bundle')
    phase('rebuilding unsigned iOS host')
    executable=rebuild(native,kit,slim,output/'host')
    phase('packing and verifying original resources')
    result=repack(slim,base_work/'cache/bundle',output/'cache/bundle',executable,output/'output.ipa')
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    phase('complete')
    print('PASS: all recorded R/M lists compiled; rebuilt native loader; original shader bytes preserved.',flush=True)


if __name__=='__main__':build(*sys.argv[1:])
