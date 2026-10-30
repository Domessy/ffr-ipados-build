#!/usr/bin/env python3
"""Four strictly identified BOTW NSPs behind the existing forced-command SSH key.

No access to arbitrary files or shell commands. Original source folder's name
is kept off the public repository by using a local, operator-created symlink.
"""
import re
from pathlib import Path

BASE = Path.home() / "portage-ipados" / "zelda-botw"
SOURCE_LINK = BASE / "source"
CACHE = BASE / "shader-cache"
CONFLICTS = BASE / "shader-cache-conflicts"
OUTPUT = BASE / "resultats"
TITLE_ID = 0x01007EF00011E000
UPDATE_VERSION = 1114112
DLC_VERSION = 196608
ROUTES = frozenset({
    "botw-probe-v1", "botw-manifest-v1", "botw-read-base",
    "botw-read-update", "botw-read-dlc1", "botw-read-dlc2",
    "botw-read-keys", "botw-read-cache", "botw-write-cache",
    "botw-write-ipa", "botw-write-log",
})
TITLE_TAG = re.compile(r"\[([0-9a-f]{16})\]", re.I)


def local_source():
    documents = (Path.home() / "Documents").resolve(strict=True)
    if not SOURCE_LINK.is_symlink():
        raise ValueError("missing operator-selected game source link")
    folder = SOURCE_LINK.resolve(strict=True)
    if not folder.is_dir() or folder.parent != documents:
        raise ValueError("source must be an immediate Documents subdirectory")
    return folder


def inputs():
    source = local_source()
    candidates = sorted(p for p in source.iterdir() if p.suffix.casefold() == ".nsp")
    if len(candidates) != 4:
        raise ValueError("expected four BOTW NSPs, including both DLC")
    found = {}
    for file in candidates:
        if file.is_symlink() or not file.is_file() or not 0 < file.stat().st_size < 32 * 1024**3:
            raise ValueError("invalid source NSP")
        n = file.name.casefold()
        tag = TITLE_TAG.search(n)
        tid = int(tag.group(1), 16) if tag else None
        if "[dlc pack 1]" in n:
            role = "dlc1"
            if tid != TITLE_ID + 0x1001 or "[v196608]" not in n:
                raise ValueError("DLC1 ID/version mismatch")
        elif "[dlc pack 2]" in n:
            role = "dlc2"
            if tid != TITLE_ID + 0x1002 or "[v196608]" not in n:
                raise ValueError("DLC2 ID/version mismatch")
        elif "base" in n and "[v0]" in n and "update" not in n and "dlc" not in n:
            role = "base"
            if tid is not None and tid != TITLE_ID:
                raise ValueError("base title ID mismatch")
            if file.stat().st_size < 1024**3:
                raise ValueError("unexpectedly small base NSP")
        elif "update" in n and ("v1.9.0p" in n or "[v1114112]" in n):
            role = "update"
            if tid is not None and tid != TITLE_ID + 0x800:
                raise ValueError("update title ID mismatch")
            if file.stat().st_size < 1024**2:
                raise ValueError("unexpectedly small update NSP")
        else:
            raise ValueError("unrecognized BOTW NSP")
        if role in found:
            raise ValueError("duplicate BOTW source role")
        # File magic is an inexpensive, non-decrypting format check.
        with file.open("rb") as data:
            if data.read(4) != b"PFS0":
                raise ValueError("invalid NSP PFS0 header")
        found[role] = file
    if set(found) != {"base", "update", "dlc1", "dlc2"}:
        raise ValueError("incomplete base/update/DLC set")
    return found


def dispatch(command, parent):
    if command not in ROUTES:
        return 126
    if command == "botw-probe-v1":
        inputs()
        if not parent.PRIVATE.is_file():
            raise ValueError("private keys not configured")
        print("BOTW_GATEWAY_V1")
        return 0
    if command == "botw-manifest-v1":
        found = inputs()
        sizes = [found[x].stat().st_size for x in ("base", "update", "dlc1", "dlc2")]
        print(f"{TITLE_ID:016X} {UPDATE_VERSION} {DLC_VERSION} " + " ".join(map(str, sizes)))
        return 0
    roles = {
        "botw-read-base": "base", "botw-read-update": "update",
        "botw-read-dlc1": "dlc1", "botw-read-dlc2": "dlc2",
    }
    if command in roles:
        parent.send_file(inputs()[roles[command]])
        return 0
    if command == "botw-read-keys":
        if not parent.PRIVATE.is_file():
            raise ValueError("private keys not configured")
        parent.send_file(parent.PRIVATE, allow_key_link=True)
        return 0

    previous = (parent.CACHE, parent.CONFLICTS, parent.OUTPUT)
    try:
        parent.CACHE, parent.CONFLICTS, parent.OUTPUT = CACHE, CONFLICTS, OUTPUT
        if command == "botw-read-cache":
            parent.read_cache()
        elif command == "botw-write-cache":
            parent.write_cache()
        elif command == "botw-write-ipa":
            parent.receive_file("ZeldaBreathOfTheWild-iPadOS.ipa", 32 * 1024**3)
        elif command == "botw-write-log":
            parent.receive_file("botw-build.log", 32 * 1024**2)
        return 0
    finally:
        parent.CACHE, parent.CONFLICTS, parent.OUTPUT = previous
