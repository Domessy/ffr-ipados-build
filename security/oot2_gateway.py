#!/usr/bin/env python3
"""Title-scoped SSH gateway for ONE original Switch 2 Ocarina NUP.

No Nintendo keys are required for a NUP. No shell command or arbitrary path
is accepted, and output/caches never share another game's workspace.
"""
from pathlib import Path
import json
import re
try:
    from .oot2_nup_info import TITLE, VERSION, SUPER, inspect, selected_romfs_bytes, release_identity, NupInvalid
except ImportError:  # forced-command gateway runs as a standalone script
    from oot2_nup_info import TITLE, VERSION, SUPER, inspect, selected_romfs_bytes, release_identity, NupInvalid

HOME = Path.home()
ROOT = HOME / "portage-ipados" / "oot-switch2"
SOURCE_LINK = ROOT / "source"
CACHE = ROOT / "shader-cache"
CONFLICTS = ROOT / "shader-cache-conflicts"
OUTPUT = ROOT / "resultats"

ROUTES = frozenset({
    "oot2-diagnose-v1", "oot2-probe-v1", "oot2-manifest-v1", "oot2-space-v1",
    "oot2-read-nup", "oot2-read-cache", "oot2-write-cache",
    "oot2-write-ipa", "oot2-write-log",
    "oot2-read-metal-snapshot-v1",
    "oot2-metal-snapshot-info-v1",
    "oot2-release-preflight-v1",
    "oot2-write-host-kit-v1",
    "oot2-write-host-kit-v5",
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
    # Local selection is never supplied by the SSH client. Bind it to the
    # validated container's size and TOC, preserving every original NUP.
    selector = SOURCE_LINK.parent / "selected-nup.json"
    if selector.exists() or selector.is_symlink():
        if selector.is_symlink() or not selector.is_file() or selector.stat().st_size > 4096:
            raise ValueError("selection")
        try:
            chosen = json.loads(selector.read_text())
            if (not isinstance(chosen, dict) or set(chosen) != {"filename", "bytes", "toc_sha256"}
                    or not isinstance(chosen["filename"], str)
                    or chosen["filename"] in ("", ".", "..")
                    or "/" in chosen["filename"] or "\\" in chosen["filename"]
                    or type(chosen["bytes"]) is not int
                    or not isinstance(chosen["toc_sha256"], str)
                    or not re.fullmatch(r"[0-9a-f]{64}", chosen["toc_sha256"])):
                raise ValueError("selection")
            file = folder / chosen["filename"]
            if file not in files:
                raise ValueError("selection")
            inspect(file)  # Includes actual TOC digest verification.
            with file.open("rb") as stream:
                header = SUPER.unpack(stream.read(SUPER.size))
            if file.stat().st_size != chosen["bytes"] or header[5].hex() != chosen["toc_sha256"]:
                raise ValueError("selection")
        except (OSError, ValueError, TypeError, KeyError):
            raise ValueError("selection") from None
        return file
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
        reason = str(exc) if str(exc) in ("source", "count", "selection") else "source"
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
    if command == "oot2-release-preflight-v1":
        print("OOT2_RELEASE_READY_V1", release_identity(nup_file()))
        return 0
    if command == "oot2-manifest-v1":
        size, base, selected, count = inspect(nup_file())
        print(f"{TITLE:016X}", f"v{VERSION}", size, base, selected, count)
        return 0
    if command == "oot2-space-v1":
        path = nup_file()
        # Numeric-only reply, no filenames, path disclosure or game payload.
        print("OOT2_SPACE_V1", path.stat().st_size, selected_romfs_bytes(path))
        return 0
    if command == "oot2-read-nup":
        parent.send_file(nup_file())
        return 0
    if command in ("oot2-read-metal-snapshot-v1", "oot2-metal-snapshot-info-v1"):
        try:
            from .oot2_cache_snapshot import snapshot
        except ImportError:
            from oot2_cache_snapshot import snapshot
        archive, stats = snapshot(CACHE, ROOT / "cache-transfer")
        if command == "oot2-metal-snapshot-info-v1":
            print("OOT2_METAL_SNAPSHOT_V1", archive.stat().st_size,
                  stats["sqlite_bytes"], stats["entries"])
        else:
            parent.send_file(archive)
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
        elif command in ("oot2-write-host-kit-v1", "oot2-write-host-kit-v5"):
            filename = "OOT2HostKit-v5.tar.zst" if command.endswith("-v5") else "OOT2HostKit-v4.tar.zst"
            parent.receive_file(filename, 1 * 1024**3)
        return 0
    finally:
        parent.CACHE, parent.CONFLICTS, parent.OUTPUT = previous
