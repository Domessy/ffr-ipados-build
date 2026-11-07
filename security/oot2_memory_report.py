#!/usr/bin/env python3
"""Summarize local Jetsam or OOT2 logs; emit only numeric diagnostics."""
import argparse
import json
from pathlib import Path
import re


def jetsam(text):
    # Apple .ips files can contain a metadata object then a report object.
    decoder = json.JSONDecoder()
    first, end = decoder.raw_decode(text.lstrip())
    report = json.loads(text.lstrip()[end:]) if text.lstrip()[end:].strip() else first
    page = report['memoryStatus']['pageSize']
    procs = report['processes']
    victims = [p for p in procs if p.get('name') == 'LiveContainer']
    compiler = [p for p in procs if p.get('name') == 'MTLCompilerService']
    mib = lambda pages: pages * page / 1024**2
    return {'page_bytes': page, 'free_mib': mib(report['memoryStatus']['memoryPages']['free']),
            'LiveContainer': [{'reason': p.get('reason'), 'resident_mib': mib(p['rpages']),
                               'lifetime_max_mib': mib(p['lifetimeMax'])} for p in victims],
            'compiler_services': len(compiler),
            'compiler_resident_mib': sum(mib(p['rpages']) for p in compiler)}


def runtime(text):
    samples = []
    old = re.compile(r'memory up to frame (\d+): resident (\d+) MB, GPU allocated (\d+) MB')
    for line in text.splitlines():
        if '[oot2-mem]' in line:
            fields = dict(re.findall(r'(sample|frame|seconds|\w+_mib)=([\d.]+)', line))
            if all(k in fields for k in ('frame', 'seconds', 'rss_mib', 'footprint_mib', 'metal_mib')):
                samples.append({k: float(v) for k, v in fields.items()})
        elif m := old.search(line):
            # The pinned host calls this "resident", but passes phys_footprint.
            samples.append(dict(zip(('frame', 'footprint_mib', 'metal_mib'), map(int, m.groups()))))
    result = {'sample_count': len(samples), 'samples': samples}
    for key in ('rss_mib', 'footprint_mib', 'metal_mib'):
        seq = [p[key] for p in samples if key in p]
        if seq:
            result[key] = {'first': seq[0], 'last': seq[-1], 'peak_sampled': max(seq), 'change': seq[-1] - seq[0]}
    timed = [p for p in samples if 'seconds' in p]
    if len(timed) >= 2 and (dt := timed[-1]['seconds'] - timed[0]['seconds']) > 0:
        result['interval_seconds'] = dt
        result['footprint_mib_per_minute'] = (timed[-1]['footprint_mib'] - timed[0]['footprint_mib']) * 60 / dt
    result['gpu_oom_lines'] = text.count('GPU out of memory:')
    result['compiler_connection_interrupted_lines'] = text.count('XPC_ERROR_CONNECTION_INTERRUPTED')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('path', type=Path)
    p.add_argument('--jetsam', action='store_true')
    args = p.parse_args()
    print(json.dumps((jetsam if args.jetsam else runtime)(args.path.read_text(errors='replace')), indent=2))
