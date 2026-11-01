#!/usr/bin/env python3
"""Echoes of Wisdom: fixed-command SSH gateway for one XCI base and one NSP update."""
from pathlib import Path
import re
import stat

ROOT = Path.home() / "portage-ipados" / "zelda-echoes-of-wisdom"
SOURCE_LINK = ROOT / "source"
KEYS = ROOT / "private" / "prod.keys"
CACHE = ROOT / "shader-cache"
CONFLICTS = ROOT / "shader-cache-conflicts"
OUTPUT = ROOT / "resultats"
TITLE = "01008CF01BAAC000"
UPDATE_TITLE = "01008CF01BAAC800"
VERSION = 196608
ROUTES = frozenset({
    "eow-probe-v1", "eow-diagnose-v1", "eow-manifest-v1",
    "eow-read-base", "eow-read-update", "eow-read-keys",
    "eow-read-cache", "eow-write-cache", "eow-write-ipa", "eow-write-log",
})
TITLE_TAG = re.compile(r"\[([0-9a-f]{16})\]", re.I)
VERSION_TAG = re.compile(r"\[v(\d+)\]", re.I)


def source_folder():
    documents = (Path.home() / "Documents").resolve(strict=True)
    if not SOURCE_LINK.is_symlink():
        raise ValueError("source selection missing")
    folder = SOURCE_LINK.resolve(strict=True)
    if not folder.is_dir() or folder.parent != documents:
        raise ValueError("source must resolve to a direct Documents child")
    return folder


def packages():
    folder = source_folder()
    files = [p for p in folder.iterdir() if p.suffix.casefold() in (".xci", ".nsp")]
    if len(files) != 2:
        raise ValueError("one XCI and one NSP required")
    result = {}
    for p in files:
        if p.is_symlink() or not p.is_file():
            raise ValueError("game package must be regular")
        role = {".xci": "base", ".nsp": "update"}[p.suffix.casefold()]
        if role in result:
            raise ValueError("duplicate package role")
        name = p.name.casefold()
        ids = {x.upper() for x in TITLE_TAG.findall(name)}
        allowed_ids = {TITLE} if role == "base" else {TITLE, UPDATE_TITLE}
        if ids and not ids <= allowed_ids:
            raise ValueError("unrelated explicit package title")
        versions = {int(v) for v in VERSION_TAG.findall(name)}
        if versions and versions != ({0} if role == "base" else {VERSION}):
            raise ValueError("unsupported explicit package version")
        size = p.stat().st_size
        if role == "base" and not 512 * 1024**2 < size < 24 * 1024**3:
            raise ValueError("XCI base outside bounded size")
        if role == "update" and not 100 * 1024 < size < 8 * 1024**3:
            raise ValueError("NSP update outside bounded size")
        with p.open("rb") as stream:
            if role == "base":
                stream.seek(0x100)
                if stream.read(4) != b"HEAD":
                    raise ValueError("XCI gamecard header missing at offset 0x100")
            elif stream.read(4) != b"PFS0":
                raise ValueError("NSP PFS0 header missing")
        result[role] = p
    if set(result) != {"base", "update"}:
        raise ValueError("XCI base or NSP update missing")
    return result


def private_keys():
    if KEYS.is_symlink() or not KEYS.is_file() or not KEYS.stat().st_size:
        raise ValueError("dedicated private keys missing")
    if not stat.S_ISREG(KEYS.stat().st_mode):
        raise ValueError("key file not regular")
    return KEYS


def diagnose():
    source = packages_ok = keys = False
    try:
        source_folder()
        source = True
        packages()
        packages_ok = True
    except (OSError, ValueError):
        pass
    try:
        private_keys()
        keys = True
    except (OSError, ValueError):
        pass
    print(f"EOW_DIAG_V1 source={'ok' if source else 'fail'} "
          f"packages={'ok' if packages_ok else 'fail'} "
          f"keys={'ok' if keys else 'fail'}")
    return 0


def dispatch(command, parent):
    if command not in ROUTES:
        return 126
    if command == "eow-diagnose-v1":
        return diagnose()
    if command == "eow-probe-v1":
        packages()
        private_keys()
        print("EOW_GATEWAY_V1")
        return 0
    if command == "eow-manifest-v1":
        source = packages()
        print(TITLE, VERSION, source["base"].stat().st_size,
              source["update"].stat().st_size)
        return 0
    if command in ("eow-read-base", "eow-read-update"):
        parent.send_file(packages()[command.removeprefix("eow-read-")])
        return 0
    if command == "eow-read-keys":
        parent.send_file(private_keys())
        return 0

    old = parent.CACHE, parent.CONFLICTS, parent.OUTPUT
    try:
        parent.CACHE, parent.CONFLICTS, parent.OUTPUT = CACHE, CONFLICTS, OUTPUT
        if command == "eow-read-cache":
            parent.read_cache()
        elif command == "eow-write-cache":
            parent.write_cache()
        elif command == "eow-write-ipa":
            parent.receive_file("ZeldaEchoesOfWisdom-nxnative.ipa", 16 * 1024**3)
        elif command == "eow-write-log":
            parent.receive_file("eow-build.log", 32 * 1024**2)
        return 0
    finally:
        parent.CACHE, parent.CONFLICTS, parent.OUTPUT = old
