#!/usr/bin/env python3
"""Restricted Silksong commands, dispatched by the existing FFR SSH gateway.

No access to the user's other documents, no generic shell, no filenames in CI
logs. Does not change the existing Final Fantasy Resonance routes.
"""
import sys
from pathlib import Path

BASE = Path.home() / "portage-ipados" / "hollow-knight-silksong"
SOURCE = Path.home() / "Documents" / "Hollow Knight Silksong"
KEYS = SOURCE / "prod.keys"
CACHE = BASE / "shader-cache"
CONFLICTS = BASE / "shader-cache-conflicts"
OUTPUT = BASE / "resultats"

COMMANDS = frozenset({
    "silksong-probe-v2", "silksong-read-base", "silksong-read-update",
    "silksong-read-keys",
    "silksong-read-cache", "silksong-write-cache",
    "silksong-write-ipa", "silksong-write-log",
})


def identify_inputs():
    """Two regular, non-symlink NSPs: largest is base, smaller is update."""
    if SOURCE.is_symlink() or not SOURCE.is_dir():
        raise ValueError("missing Silksong NSP folder")
    nsp = sorted(
        (p for p in SOURCE.iterdir()
         if p.suffix.lower() == ".nsp" and p.is_file() and not p.is_symlink()),
        key=lambda p: p.stat().st_size, reverse=True,
    )
    if len(nsp) != 2 or nsp[1].stat().st_size == 0:
        raise ValueError("expected exactly two nonempty Silksong NSPs")
    return nsp[0], nsp[1]


def identify_keys():
    """Only accept the private, named, non-symlink production key file."""
    if SOURCE.is_symlink() or not SOURCE.is_dir():
        raise ValueError("missing Silksong NSP folder")
    if KEYS.is_symlink() or not KEYS.is_file():
        raise ValueError("missing Silksong prod.keys")
    size = KEYS.stat().st_size
    if size <= 0 or size > 2 * 1024 * 1024:
        raise ValueError("invalid Silksong prod.keys size")
    return KEYS


def dispatch(command, parent):
    if command not in COMMANDS:
        return 126
    if command == "silksong-probe-v2":
        base, update = identify_inputs()
        identify_keys()
        if base.stat().st_size <= update.stat().st_size:
            raise ValueError("ambiguous NSP ordering")
        print("SILKSONG_GATEWAY_V2")
        return 0
    if command == "silksong-read-keys":
        parent.send_file(identify_keys())
        return 0
    if command in ("silksong-read-base", "silksong-read-update"):
        base, update = identify_inputs()
        parent.send_file(base if command.endswith("base") else update)
        return 0

    # Parent is the existing restricted SSH gateway loaded as __main__.
    # This is an independent SSH process, so these bindings cannot affect
    # concurrent FFR builds or the PC's persistent FFR cache.
    previous = (parent.CACHE, parent.CONFLICTS, parent.OUTPUT)
    try:
        parent.CACHE, parent.CONFLICTS, parent.OUTPUT = CACHE, CONFLICTS, OUTPUT
        if command == "silksong-read-cache":
            parent.read_cache()
        elif command == "silksong-write-cache":
            parent.write_cache()
        elif command == "silksong-write-ipa":
            parent.receive_file("Silksong-iPadOS.ipa", 16 * 1024 ** 3)
        elif command == "silksong-write-log":
            parent.receive_file("silksong-build.log", 32 * 1024 ** 2)
        return 0
    finally:
        parent.CACHE, parent.CONFLICTS, parent.OUTPUT = previous
