"""Allow only the measured NDSR key expansion in a validated captured host profile."""
import hashlib
import json
import re

NAMES = {'DM_GAME_UPSCALER_KEYS', 'DM_GAME_UPSCALER_N'}

def validate(original, generated, shader_map):
    def split(lines):
        keys = {}; rest = []
        for line in lines:
            parts = line.split(maxsplit=2)
            if len(parts) == 3 and parts[0] == '#define' and parts[1] in NAMES:
                if parts[1] in keys: raise ValueError('duplicate upscaler definition')
                keys[parts[1]] = parts[2]
            else: rest.append(line)
        if set(keys) != NAMES: raise ValueError('upscaler definitions missing')
        return keys, rest
    before, a = split(original); after, b = split(generated)
    if a != b: raise ValueError('unrelated captured profile difference')
    sets = []
    for pattern in (r'/agl_ndsr\.pck#', r'#NDSR@0x[0-9a-f]+$'):
        values = set()
        for line in shader_map.splitlines():
            c = line.split('\t')
            if len(c) >= 5 and c[2] == 'compute' and re.search(pattern,c[4]) and re.fullmatch('[0-9a-f]{16}',c[3]): values.add(c[3])
        sets.append(sorted(values))
    for defs, expected in zip((before,after),sets):
        if json.loads(defs['DM_GAME_UPSCALER_KEYS']) != ','.join(expected) or int(defs['DM_GAME_UPSCALER_N']) != len(expected):
            raise ValueError('upscaler definition differs from original shader map')
    if not set(sets[0]) <= set(sets[1]): raise ValueError('upscaler expansion lost keys')
    return {'kind':'ndsr-network-detection','before_count':len(sets[0]),'after_count':len(sets[1]),
            'keys_sha256':hashlib.sha256(','.join(sets[1]).encode()).hexdigest()}
