#!/usr/bin/env python3
"""TOTK 1.4.3 source gateway. Fixed commands only; never expose arbitrary paths."""
import io
from pathlib import Path
import re
import tarfile

ROOT = Path.home() / "portage-ipados" / "zelda-totk-mng"
SOURCE_LINK = ROOT / "source"
FONTS = ROOT / "private" / "shared-fonts"
RESULTS = ROOT / "resultats"
BASE_ID = "0100F2C0115B6000"
UPDATE_VERSION = 720896
FONT_NAMES = tuple(f"{i}-{name}.bfttf" for i, name in enumerate((
    "standard", "chinese-simplified", "chinese-simplified-extension",
    "chinese-traditional", "korean", "nintendo-extension",
)))
CMDS = frozenset({
    "totk-mng-probe-v1", "totk-mng-manifest-v1",
    "totk-mng-read-base", "totk-mng-read-update", "totk-mng-read-keys",
    "totk-mng-read-fonts", "totk-mng-write-log",
    "totk-mng-write-ipa", "totk-mng-write-romfs",
})


def source_folder():
    documents = (Path.home() / "Documents").resolve(strict=True)
    if not SOURCE_LINK.is_symlink():
        raise ValueError("operator-selected source symlink not configured")
    folder = SOURCE_LINK.resolve(strict=True)
    if not folder.is_dir() or folder.parent != documents:
        raise ValueError("source must resolve to a direct Documents subdirectory")
    return folder


def sources():
    folder = source_folder()
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() == ".nsp")
    if len(files) != 2:
        raise ValueError("exactly two TOTK NSP files expected")
    result = {}
    for p in files:
        if p.is_symlink() or not p.is_file():
            raise ValueError("regular NSP required")
        n = p.name.lower()
        if "[0100f2c0115b6000][v0]" in n and "update" not in n:
            role = "base"
            if p.stat().st_size < 10 * 1024**3:
                raise ValueError("unexpectedly small base NSP")
        elif "update_v720896" in n or ("[0100f2c0115b6800]" in n and "[v720896]" in n):
            role = "update"
            if not 100 * 1024**2 < p.stat().st_size < 3 * 1024**3:
                raise ValueError("unexpected update size")
        else:
            raise ValueError("unexpected TOTK source filename")
        if role in result:
            raise ValueError("duplicate NSP role")
        with p.open("rb") as f:
            if f.read(4) != b"PFS0":
                raise ValueError("NSP PFS0 header missing")
        result[role] = p
    if set(result) != {"base", "update"}:
        raise ValueError("missing TOTK base or update")
    return result


def font_files():
    if FONTS.is_symlink() or not FONTS.is_dir():
        return None
    result = []
    for name in FONT_NAMES:
        p = FONTS / name
        if p.is_symlink() or not p.is_file():
            return None
        if not 8 < p.stat().st_size < 32 * 1024**2:
            return None
        with p.open("rb") as stream:
            if stream.read(4) != b"BFTF":
                # BFTTF exact structure and firmware authenticity checked upstream.
                # Don't reject a valid file solely for a guessed magic.
                pass
        result.append(p)
    return result


def dispatch(command, parent):
    if command not in CMDS:
        return 126
    if command == "totk-mng-probe-v1":
        sources()
        if not parent.PRIVATE.is_file():
            raise ValueError("private key file is not configured")
        print("TOTK_MNG_GATEWAY_V1")
        return 0
    if command == "totk-mng-manifest-v1":
        p = sources()
        available = int(font_files() is not None)
        print(BASE_ID, UPDATE_VERSION, p["base"].stat().st_size,
              p["update"].stat().st_size, available)
        return 0
    if command in ("totk-mng-read-base", "totk-mng-read-update"):
        p = sources()
        parent.send_file(p["base" if command.endswith("base") else "update"])
        return 0
    if command == "totk-mng-read-keys":
        if not parent.PRIVATE.is_file():
            raise ValueError("private keys not configured")
        parent.send_file(parent.PRIVATE, allow_key_link=True)
        return 0
    if command == "totk-mng-read-fonts":
        files = font_files()
        if files is None:
            raise ValueError("six validated source files absent")
        with tarfile.open(fileobj=parent.sys.stdout.buffer, mode="w|gz") as bundle:
            for f in files:
                bundle.add(f, arcname=f.name, recursive=False)
        return 0
    previous = parent.OUTPUT
    try:
        parent.OUTPUT = RESULTS
        if command == "totk-mng-write-ipa":
            parent.receive_file("ZeldaTOTK-MacNativeGames.ipa", 32 * 1024**3)
        elif command == "totk-mng-write-romfs":
            parent.receive_file("TOTK-v143-romfs.bin", 24 * 1024**3)
        elif command == "totk-mng-write-log":
            parent.receive_file("totk-mng-build.log", 32 * 1024**2)
        return 0
    finally:
        parent.OUTPUT = previous
