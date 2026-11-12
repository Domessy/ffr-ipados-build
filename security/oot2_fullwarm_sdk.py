#!/usr/bin/env python3
"""Derive Metal script enum names from the selected Apple SDK, not numeric guesses."""
import argparse
import json
from pathlib import Path
import subprocess

TYPES = ('MTLPixelFormat', 'MTLVertexFormat', 'MTLVertexStepFunction', 'MTLPrimitiveTopologyClass',
         'MTLBlendFactor', 'MTLBlendOperation', 'MTL4BlendState',
         'MTL4AlphaToCoverageState')


def objects(text):
    decoder = json.JSONDecoder(); pos = 0
    while pos < len(text):
        while pos < len(text) and text[pos].isspace(): pos += 1
        if pos == len(text): return
        item, pos = decoder.raw_decode(text, pos); yield item


def constants(node, prefix):
    found = {}
    def walk(item):
        if item.get('kind') == 'EnumDecl' and item.get('name') == prefix:
            previous = -1
            for child in item.get('inner', []):
                if child.get('kind') != 'EnumConstantDecl': continue
                def value(n):
                    if n.get('kind') == 'ConstantExpr' and 'value' in n: return int(n['value'])
                    for inner in n.get('inner', []):
                        v = value(inner)
                        if v is not None: return v
                    return None
                number = value(child)
                if number is None: number = previous + 1
                previous = number
                name = child['name']
                if name.startswith(prefix): found.setdefault(number, name[len(prefix):])
        for child in item.get('inner', []): walk(child)
    walk(node); return found


def generate(destination):
    tables = {}
    for name in TYPES:
        proc = subprocess.run(['xcrun', '-sdk', 'macosx', 'clang', '-x', 'objective-c', '-fsyntax-only',
                               '-Xclang', '-ast-dump=json', '-Xclang', '-ast-dump-filter=' + name, '-'],
                              input='#import <Metal/Metal.h>\n', text=True, capture_output=True, check=True)
        table = {}
        for node in objects(proc.stdout): table.update(constants(node, name))
        if not table: raise ValueError('SDK enum missing: ' + name)
        tables[name] = table
    lines = ['// Generated from the selected public Metal SDK.']
    lines += ['static NSString *full_enum(const char *kind, uint64_t value) {']
    for name, table in tables.items():
        lines.append(f'    if (!strcmp(kind, "{name}")) switch (value) {{')
        for value, suffix in sorted(table.items()):
            lines.append(f'        case {value & ((1 << 64)-1)}ULL: return @"{suffix}";')
        lines.append('    }')
    lines += ['    fprintf(stderr, "Unsupported Metal enum %s=%llu\\n", kind, (unsigned long long)value); abort();', '}']
    Path(destination).write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('destination', type=Path)
    generate(ap.parse_args().destination)
