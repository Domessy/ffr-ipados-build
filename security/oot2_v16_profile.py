"""Verify the registered profile and the tables generated from OOT2 v131072."""

import collections
import hashlib
from pathlib import Path


TITLE = '0400486024DEC000'
SHADER_COUNT = 42847
GENERATED_TABLES = ('shader_map.tsv', 'shader_facts.tsv', 'shader_pairs.tsv', 'pso_pairs.tsv')


def verify_profile(root, expected):
    profile = Path(root) / 'dm/games' / TITLE
    for name, digest in expected.items():
        path = profile / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('v16 official profile identity: ' + name)
    for name in GENERATED_TABLES:
        if (profile / name).exists() or (profile / name).is_symlink():
            raise ValueError('v16 generated table present in registered profile: ' + name)
    settings = dict(line.split('\t', 1) for line in (profile / 'game.tsv').read_text().splitlines()
                    if line and not line.startswith('#') and '\t' in line)
    if settings.get('mem_reserve') != '0x420000000' or settings.get('mem_alias') != '0x200000000':
        raise ValueError('v16 virtual alias reservation')


def validate_shader_map(text, expected_count=SHADER_COUNT):
    indices = collections.Counter()
    keys = set()
    for line in text.splitlines():
        if not line or line.startswith(('#', 'package\t')):
            continue
        package, index, stage, key, source = line.split('\t')
        if int(index) != indices[package] or key in keys or key == 'ce0eba6c3584814d':
            raise ValueError('v16 generated shader map sequence')
        indices[package] += 1
        keys.add(key)
    if len(keys) != expected_count:
        raise ValueError('v16 generated shader count')
    return keys
