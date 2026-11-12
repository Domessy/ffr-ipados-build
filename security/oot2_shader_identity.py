#!/usr/bin/env python3
"""Evaluate the pinned builder's exact public CODE_FP without running a build.

Use the same interpreter as the private build: Python's AST version is keyed.
No game data, cache mutation, translation or compiler invocation is needed.
"""
import argparse
import ast
import hashlib
import importlib
import inspect
from pathlib import Path
import sys


def identity(root):
    root = Path(root).resolve()
    sys.path[:0] = [str(root/'dm/gfx/tools'), str(root/'dm/ios/tools')]
    names = ('dmsh_chain', 'dmsh_geometry', 'dmsh_atomic', 'dmsh_wide',
             'dmsh_meshstage', 'dmsh_rewrite', 'dmsh_reflect', 'dmsh_entry',
             'dmsh_ampere', 'dmsh_side', 'dmsh_abi', 'ios_metal', 'dmsh_fetch')
    modules = {name: importlib.import_module(name) for name in names}
    source = (root/'dm/gfx/tools/dmsh_build.py').read_text()
    tree = ast.parse(source)
    def assignment(name):
        return next(n for n in tree.body if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == name for t in n.targets))
    rules = assignment('RULES')
    if not isinstance(rules.value, ast.List) or rules.value.elts:
        raise ValueError('unsupported rule list; refusing inferred shader identity')
    namespace = dict(modules, hashlib=hashlib, inspect=inspect,
                     abi=modules['dmsh_abi'], IOSOUT=True)
    namespace['source_without_rule_bodies'] = lambda: modules['dmsh_chain'].code_form(source, set())
    expression = ast.Expression(assignment('CODE_FP').value)
    return eval(compile(expression, '<pinned CODE_FP>', 'eval'), namespace)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkout', type=Path)
    parser.add_argument('--expected')
    args = parser.parse_args()
    actual = identity(args.checkout)
    print(f'OOT2 shader identity: Python {sys.version_info.major}.{sys.version_info.minor}; CODE_FP={actual}')
    if args.expected and actual != args.expected:
        raise SystemExit('Resume shader identity differs; stop before any private transfer.')
