"""Verify the official corrected profile without rewriting any upstream table."""
import collections
import hashlib
from pathlib import Path


def verify_profile(root, expected):
    profile = Path(root) / 'dm/games/0400486024DEC000'
    for name, digest in expected.items():
        path = profile / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('v14 official profile identity: ' + name)
    indices = collections.Counter()
    keys = set()
    for line in (profile / 'shader_map.tsv').read_text().splitlines():
        if not line or line.startswith(('#', 'package\t')):
            continue
        package, index, stage, key, source = line.split('\t')
        if int(index) != indices[package] or key in keys or key == 'ce0eba6c3584814d':
            raise ValueError('v14 official shader map sequence')
        indices[package] += 1
        keys.add(key)
    if len(keys) != 42847:
        raise ValueError('v14 official shader count')
    settings = dict(line.split('\t', 1) for line in (profile / 'game.tsv').read_text().splitlines()
                    if line and not line.startswith('#') and '\t' in line)
    if settings.get('mem_reserve') != '0x420000000' or settings.get('mem_alias') != '0x200000000':
        raise ValueError('v14 virtual alias reservation')
    return len(keys)
