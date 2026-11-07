#!/usr/bin/env python3
"""Exercise every patch variant on real pinned code, without retail inputs."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile
from oot2_patch_runtime import apply, PIN, SOURCE, VARIANTS


def run(checkout):
    checkout = Path(checkout).resolve()
    original = subprocess.check_output(['git', '-C', str(checkout), 'show', f'{PIN}:{SOURCE}'])
    for variant in VARIANTS:
        with tempfile.TemporaryDirectory(prefix='oot2-runtime-') as tmp:
            root = Path(tmp)
            subprocess.run(['git', 'clone', '-q', '--shared', '--no-checkout', str(checkout), tmp], check=True)
            subprocess.run(['git', '-C', tmp, 'update-ref', 'HEAD', PIN], check=True)
            f = root / SOURCE
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(original)
            apply(root, variant)
            try:
                apply(root, variant)
            except ValueError:
                pass
            else:
                raise AssertionError('Must reject a second application')
            code = f.read_text()
            function = re.search(r'static int image_shape\(const tex_t \*t\) \{.*?\n\}', code, re.S).group()
            enum = re.search(r'enum \{ IMAGE_NOT_SHARED = .*?\};', code)
            header = subprocess.check_output(['git', '-C', str(checkout), 'show', f'{PIN}:dm/gfx/nvn/include/nvn.h'], text=True)
            flags = dict(re.findall(r'(NVN_TEXTURE_FLAGS_\w+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)', header))
            assert flags
            c = '#include <assert.h>\n#include <stddef.h>\n'
            c += '\n'.join(f'#define {k} {v}' for k, v in flags.items())
            c += '\n#define NVN_TEXTURE_TARGET_2D 1\n'
            c += 'typedef struct {void *pool; int has_layout; struct {unsigned flags,target,depth,levels,samples,stride;} d;} tex_t;\n'
            c += (enum.group() if enum else '') + '\n' + function
            c += '''
int main(void) {
 tex_t t={.pool=(void*)1,.d={.flags=NVN_TEXTURE_FLAGS_COMPRESSIBLE|NVN_TEXTURE_FLAGS_IMAGE,.target=1,.depth=1,.levels=1,.samples=1}};
 assert(image_shape(&t)); assert(!image_shape(NULL));
 t.d.flags=NVN_TEXTURE_FLAGS_COMPRESSIBLE;
 assert(image_shape(&t)==DEPTH_EXPECTED);
 unsigned excluded[]={NVN_TEXTURE_FLAGS_DISPLAY,NVN_TEXTURE_FLAGS_VIDEO_DECODE,NVN_TEXTURE_FLAGS_LINEAR,NVN_TEXTURE_FLAGS_SPARSE,NVN_TEXTURE_FLAGS_LINEAR_RENDER_TARGET};
 for(unsigned i=0;i<sizeof excluded/sizeof *excluded;i++) {t.d.flags=NVN_TEXTURE_FLAGS_COMPRESSIBLE|NVN_TEXTURE_FLAGS_IMAGE|excluded[i];assert(!image_shape(&t));}
 t.d.flags=NVN_TEXTURE_FLAGS_COMPRESSIBLE|NVN_TEXTURE_FLAGS_IMAGE;
 t.has_layout=1;assert(!image_shape(&t));t.has_layout=0;
 t.d.depth=2;assert(!image_shape(&t));t.d.depth=1;
 t.d.levels=2;assert(!image_shape(&t));t.d.levels=1;
 t.d.samples=4;assert(!image_shape(&t));t.d.samples=1;
 t.d.stride=256;assert(!image_shape(&t));t.d.stride=0;
 t.pool=0;assert(!image_shape(&t)); return 0;
}
'''
            c = c.replace('DEPTH_EXPECTED', '0' if variant == 'baseline' else '1')
            (root/'shape.c').write_text(c)
            subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', str(root/'shape.c'), '-o', str(root/'shape')], check=True)
            subprocess.run([str(root/'shape')], check=True)
            # The consumer barriers and relaxed draw-pass path must stay intact.
            assert code.count('visibilityOptions:resource_vis()') == original.decode().count('visibilityOptions:resource_vis()')
            assert ('end_alias && sw_on(end_alias)' in code) == (variant == 'memory-v1')
            print(f'{variant}: exact-pin apply, duplicate rejection, native shape guards passed')
    print('No shaders, game inputs, signing, installation or IPA build performed')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('checkout', type=Path)
    run(p.parse_args().checkout)
