#!/usr/bin/env python3
"""Link's Awakening nxnative v1.1.0: restricted title-scoped SSH gateway.

No arbitrary filesystem traversal or shell commands. Local original files
are only read, and cache/output paths are project-specific.
"""
from pathlib import Path
import re
import stat

ROOT = Path.home() / "portage-ipados" / "zelda-links-awakening"
SOURCE_LINK = ROOT / "source"
KEYS = ROOT / "private" / "prod.keys"
CACHE = ROOT / "shader-cache"
CONFLICTS = ROOT / "shader-cache-conflicts"
OUTPUT = ROOT / "resultats"
TITLE = "01006BB00C6F0000"
UPDATE_TITLE = "01006BB00C6F0800"
VERSION = 131072
ROUTES = frozenset({
    "zla-probe-v1", "zla-diagnose-v1", "zla-manifest-v1",
    "zla-read-base", "zla-read-update", "zla-read-keys",
    "zla-read-cache", "zla-write-cache", "zla-write-ipa", "zla-write-log",
})
TITLE_TAG = re.compile(r"\[([0-9a-f]{16})\]", re.I)
VERSION_TAG = re.compile(r"\[v(\d+)\]", re.I)


def source_folder():
    documents = (Path.home() / "Documents").resolve(strict=True)
    if not SOURCE_LINK.is_symlink():
        raise ValueError("game source link not configured")
    folder = SOURCE_LINK.resolve(strict=True)
    if not folder.is_dir() or folder.parent != documents:
        raise ValueError("game source must be an immediate Documents child")
    return folder


def classify(path):
    """Use explicit filename identity, not size/order guesses; nx_extract verifies NSP metadata."""
    name = path.name.casefold()
    ids = {tag.upper() for tag in TITLE_TAG.findall(name)}
    if ids and not ids <= {TITLE, UPDATE_TITLE}:
        raise ValueError("unrelated title ID")
    versions = {int(v) for v in VERSION_TAG.findall(name)}
    if versions and not versions <= {0, VERSION}:
        raise ValueError("unsupported version")
    update_hint = (
        UPDATE_TITLE.casefold() in name or "update" in name or
        "mise a jour" in name or "mise à jour" in name or
        "v131072" in name or "1.1.0" in name
    )
    if update_hint:
        if TITLE.casefold() in name and UPDATE_TITLE.casefold() not in name and ids:
            raise ValueError("update marked as base title")
        if versions and VERSION not in versions:
            raise ValueError("update version not 1.1.0")
        return "update"
    base_hint = (
        TITLE.casefold() in name or "base" in name or
        "[v0]" in name or "version 1.0.0" in name
    )
    if base_hint and UPDATE_TITLE.casefold() not in name:
        if versions and versions != {0}:
            raise ValueError("base version not 0")
        return "base"
    raise ValueError("unidentified package role; explicit title/version required")


def packages():
    files = sorted(p for p in source_folder().iterdir() if p.suffix.lower() == ".nsp")
    if len(files) != 2:
        raise ValueError("exactly two NSPs expected")
    result = {}
    for p in files:
        if p.is_symlink() or not p.is_file():
            raise ValueError("source is not a regular NSP")
        role = classify(p)
        size = p.stat().st_size
        if role == "base" and not 512 * 1024**2 < size < 18 * 1024**3:
            raise ValueError("base NSP size outside bounded range")
        if role == "update" and not 100 * 1024 < size < 5 * 1024**3:
            raise ValueError("update NSP size outside bounded range")
        if role in result:
            raise ValueError("duplicate package role")
        with p.open("rb") as stream:
            if stream.read(4) != b"PFS0":
                raise ValueError("NSP PFS0 header absent")
        result[role] = p
    if set(result) != {"base", "update"}:
        raise ValueError("incomplete base/update pair")
    return result


def private_keys():
    if KEYS.is_symlink() or not KEYS.is_file() or not KEYS.stat().st_size:
        raise ValueError("dedicated private keys not configured")
    if not stat.S_ISREG(KEYS.stat().st_mode):
        raise ValueError("keys must be a regular file")
    return KEYS


def diagnose():
    source = sources = keys = False
    try:
        source_folder()
        source = True
        packages()
        sources = True
    except (OSError, ValueError):
        pass
    try:
        private_keys()
        keys = True
    except (OSError, ValueError):
        pass
    print(f"ZLA_DIAG_V1 source={'ok' if source else 'fail'} "
          f"packages={'ok' if sources else 'fail'} "
          f"keys={'ok' if keys else 'fail'}")
    return 0


def dispatch(command, parent):
    if command not in ROUTES:
        return 126
    if command == "zla-diagnose-v1":
        return diagnose()
    if command == "zla-probe-v1":
        packages()
        private_keys()
        print("ZLA_GATEWAY_V1")
        return 0
    if command == "zla-manifest-v1":
        pair = packages()
        print(TITLE, VERSION, pair["base"].stat().st_size,
              pair["update"].stat().st_size)
        return 0
    if command in ("zla-read-base", "zla-read-update"):
        role = command.removeprefix("zla-read-")
        parent.send_file(packages()[role])
        return 0
    if command == "zla-read-keys":
        parent.send_file(private_keys())
        return 0

    previous = parent.CACHE, parent.CONFLICTS, parent.OUTPUT
    try:
        parent.CACHE, parent.CONFLICTS, parent.OUTPUT = CACHE, CONFLICTS, OUTPUT
        if command == "zla-read-cache":
            parent.read_cache()
        elif command == "zla-write-cache":
            parent.write_cache()
        elif command == "zla-write-ipa":
            parent.receive_file("ZeldaLinksAwakening-nxnative.ipa", 16 * 1024**3)
        elif command == "zla-write-log":
            parent.receive_file("zla-build.log", 32 * 1024**2)
        return 0
    finally:
        parent.CACHE, parent.CONFLICTS, parent.OUTPUT = previous
