#!/usr/bin/env python3
"""Restricted Tales source routing; does not expose local document paths in CI."""
import re
from pathlib import Path

BASE = Path.home() / "portage-ipados" / "tales-of-eternia"
SOURCE_LINK = BASE / "source"
CACHE = BASE / "shader-cache"
CONFLICTS = BASE / "shader-cache-conflicts"
OUTPUT = BASE / "resultats"
COMMANDS = frozenset({
    "tales-probe-v1", "tales-read-base", "tales-read-update", "tales-read-keys",
    "tales-read-cache", "tales-write-cache", "tales-write-ipa",
    "tales-write-log", "tales-write-survey",
})
TITLE = re.compile(r"\[([0-9A-Fa-f]{16})\]")
VERSION = re.compile(r"\[v(\d+)\]")


def local_source():
    """An intentional user-managed link to an immediate Documents subdirectory."""
    documents = (Path.home() / "Documents").resolve(strict=True)
    if not SOURCE_LINK.is_symlink():
        raise ValueError("missing private local source link")
    source = SOURCE_LINK.resolve(strict=True)
    if source.parent != documents or not source.is_dir():
        raise ValueError("source must be an immediate subdirectory of Documents")
    return source


def identify_inputs():
    source = local_source()
    nsps = [p for p in source.iterdir()
            if p.suffix.lower() == ".nsp" and p.is_file() and not p.is_symlink()]
    if len(nsps) != 2:
        raise ValueError("expected exactly two regular NSPs")
    classified = {}
    for p in nsps:
        match = TITLE.search(p.name)
        ver = VERSION.search(p.name)
        if not match or not ver or p.stat().st_size == 0:
            raise ValueError("NSP names must include title ID and version")
        title, version = int(match.group(1), 16), int(ver.group(1))
        kind = "base" if (title & 0xfff) == 0 else "update" if (title & 0xfff) == 0x800 else None
        if not kind or kind in classified:
            raise ValueError("unsupported NSP title-ID combination")
        classified[kind] = (p, title, version)
    if set(classified) != {"base", "update"}:
        raise ValueError("base/update pair missing")
    base, title, v0 = classified["base"]
    update, upd_title, upd_version = classified["update"]
    if v0 != 0 or upd_version == 0 or upd_title != title + 0x800:
        raise ValueError("base/update title IDs or versions are inconsistent")
    return base, update


def identify_keys():
    path = local_source() / "prod.keys"
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 2 * 1024 * 1024:
        raise ValueError("expected a regular, nonempty prod.keys")
    return path


def dispatch(command, parent):
    if command not in COMMANDS:
        return 126
    if command == "tales-probe-v1":
        identify_inputs()
        identify_keys()
        print("TALES_GATEWAY_V1")
        return 0
    if command == "tales-read-keys":
        parent.send_file(identify_keys())
        return 0
    if command in ("tales-read-base", "tales-read-update"):
        base, update = identify_inputs()
        parent.send_file(base if command.endswith("base") else update)
        return 0

    previous = parent.CACHE, parent.CONFLICTS, parent.OUTPUT
    try:
        parent.CACHE, parent.CONFLICTS, parent.OUTPUT = CACHE, CONFLICTS, OUTPUT
        if command == "tales-read-cache":
            parent.read_cache()
        elif command == "tales-write-cache":
            parent.write_cache()
        elif command == "tales-write-ipa":
            parent.receive_file("TalesOfEternia-iPadOS.ipa", 16 * 1024**3)
        elif command == "tales-write-log":
            parent.receive_file("tales-build.log", 32 * 1024**2)
        elif command == "tales-write-survey":
            parent.receive_file("tales-survey.md", 4 * 1024**2)
        return 0
    finally:
        parent.CACHE, parent.CONFLICTS, parent.OUTPUT = previous
