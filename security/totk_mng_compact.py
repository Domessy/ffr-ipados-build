#!/usr/bin/env python3
"""Space-safe, fail-closed TOTK 1.4.3 MacNativeGames adapter.

Only applied to the exact pinned upstream builder on an ephemeral GitHub
runner. Original retail files on CachyOS are never written or removed.
The adapter keeps source/update verification and image SHA-256 checks intact.
"""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys

PIN = "933b6a0d1438de160208a0a13eb5e8d7a2cb8094"

DISK_CHECK = """        if same_volume:
            required=(60 if update else 45) if not base_cached else (40 if update else 18)"""
DISK_REPLACE = """        if same_volume:
            required=(60 if update else 45) if not base_cached else (40 if update else 18)
            # The short-lived runner frees the verified base RomFS before
            # merging the update, then removes the runner's NSP copies before
            # compiling shaders and building the full IPA. Keep the upstream
            # 60 GiB threshold for all other use and for all local builds.
            if args.platform == 'ios' and os.environ.get('TOTK_MNG_COMPACT') == '1' and update and not base_cached:
                required=34"""

BEFORE_MERGE = """    step_data(tree, game, keys, logs, firmware=firmware, shared_fonts=shared_fonts, mod=None if update else mod)
    if update:
        step_update_data(tree, game, update, keys, logs, version=version, mod=mod, native_4k=native_4k)"""
BEFORE_MERGE_REPLACE = """    step_data(tree, game, keys, logs, firmware=firmware, shared_fonts=shared_fonts, mod=None if update else mod)
    if update and args.platform == 'ios' and os.environ.get('TOTK_MNG_COMPACT') == '1':
        # extract_update_romfs.py reads the original base NSP directly, not
        # the decrypted base RomFS. The base is already verified at this point.
        old_base = tree / 'extracted/v0/romfs/romfs.bin'
        if not old_base.is_file() or old_base.stat().st_size < 10 * 1024**3:
            raise BuildError('CI compact: verified base RomFS is missing')
        old_base.unlink()
        say('CI compact: freed the redundant verified base RomFS before BKTR merge')
    if update:
        step_update_data(tree, game, update, keys, logs, version=version, mod=mod, native_4k=native_4k)
    if update and args.platform == 'ios' and os.environ.get('TOTK_MNG_COMPACT') == '1':
        # The merged v143 RomFS and ExeFS are now independently verified.
        # Extract the optional icon while the two ephemeral NSP copies exist.
        icon = tree / 'build/AppIcon.icns'
        if not icon.is_file():
            try:
                run([tree/'.venv/bin/python', 'scripts/extract_app_icon.py', game,
                     '--keys', keys, '--title', '0100f2c0115b6000',
                     '--output', 'build/AppIcon.icns'], logs/'app_icon.log', cwd=tree)
            except BuildError:
                say('CI compact: source icon unavailable; using default application icon')
        # Exact allowlisted staging paths only, confined to RUNNER_TEMP.
        staged = Path(os.environ['RUNNER_TEMP']) / 'totk-mng-nsp'
        for role in ('base', 'update'):
            candidate = staged / (role + '.nsp')
            if candidate.is_symlink() or not candidate.is_file():
                raise BuildError('CI compact: expected temporary NSP staging file missing')
            if candidate.resolve().parent != staged.resolve():
                raise BuildError('CI compact: source is outside private staging folder')
            candidate.unlink()
        say('CI compact: released two ephemeral NSP copies after verified v143 merge')"""


def apply(builder: Path, *, check: bool):
    repo = builder.parent
    head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"],
                                   text=True).strip()
    if head != PIN:
        raise ValueError("upstream MacNativeGames source differs from pinned revision")
    # The same builder can be verified and patched exactly once.
    source = builder.read_text()
    replacements = [
        (DISK_CHECK, DISK_REPLACE),
        (BEFORE_MERGE, BEFORE_MERGE_REPLACE),
    ]
    if any(source.count(old) != 1 for old, _ in replacements):
        raise ValueError("upstream builder structure changed: refusing compact patch")
    if check:
        print("TOTK compact adapter: both pinned upstream anchors verified", flush=True)
        return
    for old, new in replacements:
        source = source.replace(old, new, 1)
    compile(source, str(builder), "exec")
    # Only edit the dedicated ephemeral upstream clone, never retail content.
    builder.write_text(source)
    print("TOTK compact adapter: installed for temporary runner build", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--builder", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        apply(args.builder, check=args.check)
    except (OSError, ValueError, subprocess.CalledProcessError, SyntaxError) as error:
        print(f"TOTK compact adapter refused ({type(error).__name__})", flush=True)
        raise SystemExit(1)
