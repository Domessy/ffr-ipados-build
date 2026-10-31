#!/usr/bin/env python3
"""TOTK 1.4.3 nxnative fixed-command SSH gateway; title-scoped private data only."""
from pathlib import Path
import stat

ROOT = Path.home() / "portage-ipados" / "zelda-totk-nxnative"
SOURCE_LINK = ROOT / "source"
KEYS = ROOT / "private" / "prod.keys"
CACHE = ROOT / "shader-cache"
CONFLICTS = ROOT / "shader-cache-conflicts"
OUTPUT = ROOT / "resultats"
TITLE = "0100F2C0115B6000"
VERSION = 720896
ROUTES = frozenset({
    "totknx-probe-v1", "totknx-diagnose-v1", "totknx-manifest-v1",
    "totknx-read-base", "totknx-read-update", "totknx-read-keys",
    "totknx-read-cache", "totknx-write-cache",
    "totknx-write-ipa", "totknx-write-log",
})


def source_folder():
    docs = (Path.home() / "Documents").resolve(strict=True)
    if not SOURCE_LINK.is_symlink():
        raise ValueError("source link not configured")
    folder = SOURCE_LINK.resolve(strict=True)
    if not folder.is_dir() or folder.parent != docs:
        raise ValueError("source not inside immediate Documents child")
    return folder


def packages():
    files = sorted(p for p in source_folder().iterdir() if p.suffix.lower() == ".nsp")
    if len(files) != 2:
        raise ValueError("exactly two title packages expected")
    result = {}
    for p in files:
        if p.is_symlink() or not p.is_file():
            raise ValueError("source NSP not regular")
        name = p.name.lower()
        if "[0100f2c0115b6000][v0]" in name and "update" not in name:
            role = "base"
            if not 10 * 1024**3 < p.stat().st_size < 24 * 1024**3:
                raise ValueError("base size outside expected bounds")
        elif "update_v720896" in name or (
            "[0100f2c0115b6800]" in name and "[v720896]" in name
        ):
            role = "update"
            if not 100 * 1024**2 < p.stat().st_size < 3 * 1024**3:
                raise ValueError("update size outside expected bounds")
        else:
            raise ValueError("unexpected NSP identity")
        if role in result:
            raise ValueError("duplicate title role")
        with p.open("rb") as stream:
            if stream.read(4) != b"PFS0":
                raise ValueError("not PFS0")
        result[role] = p
    if set(result) != {"base", "update"}:
        raise ValueError("base/update mismatch")
    return result


def private_keys():
    if KEYS.is_symlink() or not KEYS.is_file() or KEYS.stat().st_size == 0:
        raise ValueError("dedicated TOTK private keys not configured")
    if not stat.S_ISREG(KEYS.stat().st_mode):
        raise ValueError("private keys must be regular file")
    return KEYS


def diagnose():
    source = package = keys = False
    try:
        source_folder()
        source = True
        packages()
        package = True
    except (OSError, ValueError):
        pass
    try:
        private_keys()
        keys = True
    except (OSError, ValueError):
        pass
    print(f"TOTKNX_DIAG_V1 source={'ok' if source else 'fail'} "
          f"packages={'ok' if package else 'fail'} "
          f"keys={'ok' if keys else 'fail'}")
    return 0


def dispatch(command, parent):
    if command not in ROUTES:
        return 126
    if command == "totknx-diagnose-v1":
        return diagnose()
    if command == "totknx-probe-v1":
        packages()
        private_keys()
        print("TOTKNX_GATEWAY_V1")
        return 0
    if command == "totknx-manifest-v1":
        p = packages()
        print(TITLE, VERSION, p["base"].stat().st_size,
              p["update"].stat().st_size)
        return 0
    if command in ("totknx-read-base", "totknx-read-update"):
        role = command.removeprefix("totknx-read-")
        parent.send_file(packages()[role])
        return 0
    if command == "totknx-read-keys":
        parent.send_file(private_keys())
        return 0

    old = (parent.CACHE, parent.CONFLICTS, parent.OUTPUT)
    try:
        parent.CACHE, parent.CONFLICTS, parent.OUTPUT = CACHE, CONFLICTS, OUTPUT
        if command == "totknx-read-cache":
            parent.read_cache()
        elif command == "totknx-write-cache":
            parent.write_cache()
        elif command == "totknx-write-ipa":
            parent.receive_file("ZeldaTOTK-nxnative.ipa", 32 * 1024**3)
        elif command == "totknx-write-log":
            parent.receive_file("totknx-build.log", 32 * 1024**2)
        return 0
    finally:
        parent.CACHE, parent.CONFLICTS, parent.OUTPUT = old
