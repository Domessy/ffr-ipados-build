"""Refresh the registered OOT2 map after the authoritative BAHS array fix.

The complete private split was independently compared on CachyOS: one stray
vertex key disappears; all retained payload identities, facts and pairs stay.
Keep the upstream packer's full split/table comparison enabled.
"""
import collections
import hashlib
from pathlib import Path


def refreshed_map(data, spec):
    if hashlib.sha256(data).hexdigest() != spec['input_sha256']:
        raise ValueError('v12 registered shader map identity')
    counts = collections.Counter()
    output = []
    removed = 0
    for line in data.decode().splitlines():
        if not line or line.startswith('#') or line.startswith('package\t'):
            output.append(line)
            continue
        fields = line.split('\t')
        if len(fields) != 5:
            raise ValueError('v12 shader map columns')
        if fields[3] == spec['removed_key']:
            if fields[0] != 'vs_shader.bin' or fields[2] != 'vertex' or '#BAHS@' not in fields[4]:
                raise ValueError('v12 stray BAHS identity')
            removed += 1
            continue
        fields[1] = str(counts[fields[0]])
        counts[fields[0]] += 1
        output.append('\t'.join(fields))
    result = ('\n'.join(output) + '\n').encode()
    if removed != 1 or hashlib.sha256(result).hexdigest() != spec['output_sha256']:
        raise ValueError('v12 refreshed shader map identity')
    return result


def refresh_profile(root, spec):
    profile = Path(root) / 'dm/games/0400486024DEC000'
    for name in ('shader_facts.tsv', 'shader_pairs.tsv', 'pso_pairs.tsv', 'pso_manifest.tsv'):
        data = (profile / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != spec['preserved'][name]:
            raise ValueError('v12 preserved shader/prewarm table identity')
        if spec['removed_key'].encode() in data:
            raise ValueError('v12 stray shader still referenced')
    path = profile / 'shader_map.tsv'
    path.write_bytes(refreshed_map(path.read_bytes(), spec))
