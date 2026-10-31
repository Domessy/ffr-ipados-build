#!/usr/bin/env python3
"""Private Metroid Prime Remastered 1.0.0 gateway, fixed-command SSH only.

No game data or private keys are stored in GitHub. The owner explicitly
selects one immediate ~/Documents folder through a project-local symlink.
"""
from pathlib import Path
import re

ROOT = Path.home() / "portage-ipados" / "metroid-prime-remastered"
SOURCE = ROOT / "source"
CACHE = ROOT / "shader-cache"
CONFLICTS = ROOT / "shader-cache-conflicts"
OUTPUT = ROOT / "resultats"
TITLE = "010012101468C000"
UPDATE = "010012101468C800"
ROUTES = frozenset({
    "mpr-probe-v1", "mpr-manifest-v1",
    "mpr-read-base", "mpr-read-keys", "mpr-read-cache",
    "mpr-write-cache", "mpr-write-ipa", "mpr-write-log",
})
HEXID = re.compile(r"\[([0-9a-f]{16})\]", re.I)


def local_source():
    docs = (Path.home() / "Documents").resolve(strict=True)
    if not SOURCE.is_symlink():
        raise ValueError("operator must configure project-local source symlink")
    folder = SOURCE.resolve(strict=True)
    if not folder.is_dir() or folder.parent != docs:
        raise ValueError("source must be a direct child of Documents")
    return folder


def base_file():
    files = sorted(p for p in local_source().iterdir()
                   if p.suffix.lower() == ".nsp")
    if not files or len(files) > 6:
        raise ValueError("no NSP files or too many NSP candidates")
    validated = []
    for p in files:
        if p.is_symlink() or not p.is_file() or not (128 * 1024**2 < p.stat().st_size < 24 * 1024**3):
            raise ValueError("unexpected NSP candidate")
        with p.open("rb") as f:
            if f.read(4) != b"PFS0":
                raise ValueError("NSP PFS0 header missing")
        ids = {x.upper() for x in HEXID.findall(p.name)}
        if ids and not ids <= {TITLE, UPDATE}:
            raise ValueError("unrelated title ID in source folder")
        is_update = UPDATE in ids or "update" in p.name.casefold()
        is_base = TITLE in ids and not is_update
        validated.append((p, is_base, is_update))
    bases = [p for p,b,_ in validated if b]
    if len(bases) == 1:
        base = bases[0]
    elif len(bases) == 0 and len(validated) == 1 and not validated[0][2]:
        # The selected folder contains a single regular NSP without an ID in
        # its filename. The upstream nx_extract must validate its internal title.
        base = validated[0][0]
    else:
        raise ValueError("ambiguous base NSP; expected one title-ID-tagged base")
    if any(p != base and not u for p,_,u in validated):
        raise ValueError("unrecognized extra NSP file")
    # Supported nxnative profile currently pins 1.0.0; ignore optional newer
    # update only deliberately, never silently apply it to the v0 profile.
    return base, sum(u for p,b,u in validated if p != base)


def dispatch(command, parent):
    if command not in ROUTES:
        return 126
    if command == "mpr-probe-v1":
        base_file()
        if not parent.PRIVATE.is_file():
            raise ValueError("private prod.keys not configured")
        print("MPR_GATEWAY_V1")
        return 0
    if command == "mpr-manifest-v1":
        base, updates = base_file()
        print(f"{TITLE} 0 {base.stat().st_size} {updates}")
        return 0
    if command == "mpr-read-base":
        parent.send_file(base_file()[0])
        return 0
    if command == "mpr-read-keys":
        if not parent.PRIVATE.is_file():
            raise ValueError("private prod.keys not configured")
        parent.send_file(parent.PRIVATE, allow_key_link=True)
        return 0
    previous = parent.CACHE, parent.CONFLICTS, parent.OUTPUT
    try:
        parent.CACHE, parent.CONFLICTS, parent.OUTPUT = CACHE, CONFLICTS, OUTPUT
        if command == "mpr-read-cache":
            parent.read_cache()
        elif command == "mpr-write-cache":
            parent.write_cache()
        elif command == "mpr-write-ipa":
            parent.receive_file("MetroidPrimeRemastered-iPadOS.ipa", 16 * 1024**3)
        elif command == "mpr-write-log":
            parent.receive_file("mpr-build.log", 32 * 1024**2)
        return 0
    finally:
        parent.CACHE, parent.CONFLICTS, parent.OUTPUT = previous
