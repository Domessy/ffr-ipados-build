#!/usr/bin/env python3
"""Title-scoped SSH gateway for ONE original Switch 2 Ocarina NUP.

No Nintendo keys are required for a NUP. No shell command or arbitrary path
is accepted, and output/caches never share another game's workspace.
"""
from pathlib import Path
try:
    from .oot2_nup_info import TITLE, VERSION, inspect, NupInvalid
except ImportError:  # forced-command gateway runs as a standalone script
    from oot2_nup_info import TITLE, VERSION, inspect, NupInvalid

HOME = Path.home()
ROOT = HOME / "portage-ipados" / "oot-switch2"
SOURCE_LINK = ROOT / "source"
CACHE = ROOT / "shader-cache"
CONFLICTS = ROOT / "shader-cache-conflicts"
OUTPUT = ROOT / "resultats"

ROUTES = frozenset({
    "oot2-diagnose-v1", "oot2-probe-v1", "oot2-manifest-v1",
    "oot2-read-nup", "oot2-read-cache", "oot2-write-cache",
    "oot2-write-ipa", "oot2-write-log",
})


def nup_file():
    documents = (HOME / "Documents").resolve(strict=True)
    if not SOURCE_LINK.is_symlink():
        raise ValueError("source")
    folder = SOURCE_LINK.resolve(strict=True)
    if (not folder.is_dir() or folder.parent != documents
            or folder.name.casefold() != "the legend of zelda ocarina of time"):
        raise ValueError("source")
    files = sorted(p for p in folder.iterdir() if p.suffix.casefold() == ".nup")
    if len(files) != 1:
        raise ValueError("count")
    file = files[0]
    inspect(file)
    return file


def diagnose():
    source = nup = False
    reason = "none"
    try:
        documents = (HOME / "Documents").resolve(strict=True)
        folder = SOURCE_LINK.resolve(strict=True) if SOURCE_LINK.is_symlink() else None
        source = bool(folder and folder.is_dir() and folder.parent == documents
                      and folder.name.casefold() == "the legend of zelda ocarina of time")
        if source:
            nup_file()
            nup = True
        else:
            reason = "source"
    except NupInvalid as exc:
        reason = exc.reason
    except (OSError, ValueError) as exc:
        reason = str(exc) if str(exc) in ("source", "count") else "source"
    print(f"OOT2_DIAG_V1 source={'ok' if source else 'fail'} "
          f"nup={'ok' if nup else 'fail'} reason={reason}")
    return 0


def dispatch(command, parent):
    if command not in ROUTES:
        return 126
    if command == "oot2-diagnose-v1":
        return diagnose()
    if command == "oot2-probe-v1":
        nup_file()
        print("OOT2_GATEWAY_V1")
        return 0
    if command == "oot2-manifest-v1":
        size, base, selected, count = inspect(nup_file())
        print(f"{TITLE:016X}", f"v{VERSION}", size, base, selected, count)
        return 0
    if command == "oot2-read-nup":
        parent.send_file(nup_file())
        return 0
    previous = parent.CACHE, parent.CONFLICTS, parent.OUTPUT
    try:
        parent.CACHE, parent.CONFLICTS, parent.OUTPUT = CACHE, CONFLICTS, OUTPUT
        if command == "oot2-read-cache":
            parent.read_cache()
        elif command == "oot2-write-cache":
            parent.write_cache()
        elif command == "oot2-write-ipa":
            parent.receive_file("ZeldaOcarinaOfTime.ipa", 50 * 1024**3)
        elif command == "oot2-write-log":
            parent.receive_file("oot2-build.log", 32 * 1024**2)
        return 0
    finally:
        parent.CACHE, parent.CONFLICTS, parent.OUTPUT = previous
