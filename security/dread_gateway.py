#!/usr/bin/env python3
"""Metroid Dread experimental/provisional nxnative port: restricted SSH gateway.

No arbitrary filesystem traversal or shell commands. Local original files
are only read, and cache/output paths are project-specific.
"""
from pathlib import Path
import re
import stat

ROOT = Path.home() / "portage-ipados" / "metroid-dread"
SOURCE_LINK = ROOT / "source"
KEYS = ROOT / "private" / "prod.keys"
CACHE = ROOT / "shader-cache"
CONFLICTS = ROOT / "shader-cache-conflicts"
OUTPUT = ROOT / "resultats"
TITLE = "010093801237C000"
UPDATE_TITLE = "010093801237C800"
VERSION = 'unverified'
ROUTES = frozenset({
    "dread-probe-v1", "dread-diagnose-v1", "dread-diagnose-v2", "dread-manifest-v1",
    "dread-read-base", "dread-read-update", "dread-read-keys",
    "dread-read-cache", "dread-write-cache", "dread-write-ipa", "dread-write-log",
    "dread-write-survey", "dread-write-profile", "dread-write-inspection",
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
    """Identify base/update by safe hints; only nxnative extraction can confirm internal version."""
    name = path.name.casefold()
    ids = {tag.upper() for tag in TITLE_TAG.findall(name)}
    if ids and not ids <= {TITLE, UPDATE_TITLE}:
        raise ValueError("unrelated title ID")
    versions = {int(v) for v in VERSION_TAG.findall(name)}
    if any(v < 0 for v in versions):
        raise ValueError("invalid version marker")
    # Retail NSP filenames may use a displayed game version like "v1.0.5"
    # rather than Nintendo's integer [vNNN] convention. The version string
    # only identifies a plausible update role: nx_extract later verifies
    # encrypted Application/Patch CNMT and the actual version.
    displayed_versions = {
        tuple(map(int, match.groups()))
        for match in re.finditer(
            r"(?<![a-z0-9])v?(\d+)\.(\d+)\.(\d+)(?![a-z0-9])",
            name,
        )
    }
    if len(displayed_versions) > 1:
        raise ValueError("conflicting displayed version markers")
    displayed = next(iter(displayed_versions), None)
    update_hint = (
        UPDATE_TITLE.casefold() in name or "update" in name or
        "mise a jour" in name or "mise à jour" in name or
        any(v > 0 for v in versions) or
        (displayed is not None and displayed > (1, 0, 0))
    )
    if update_hint:
        if TITLE.casefold() in name and UPDATE_TITLE.casefold() not in name and ids:
            raise ValueError("update marked as base title")
        if versions and (0 in versions or len(versions) != 1):
            raise ValueError("update version marker ambiguous")
        return "update"
    base_hint = (
        TITLE.casefold() in name or "base" in name or "metroid dread" in name or
        "[v0]" in name or "version 1.0.0" in name
    )
    if base_hint and not update_hint and UPDATE_TITLE.casefold() not in name:
        if versions and versions != {0}:
            raise ValueError("base version marker not zero")
        return "base"
    raise ValueError("unidentified package role; explicit title/version required")


def packages():
    """Resolve the two NSP roles without requiring particular filename conventions.

    A size-based fallback is acceptable only for an unambiguous pair. The
    encrypted Application/Patch identities are then checked with nx_extract
    on the runner before the provisional build starts.
    """
    files = sorted(p for p in source_folder().iterdir() if p.suffix.casefold() == ".nsp")
    if len(files) != 2:
        raise ValueError("exactly two NSPs expected")

    identified = {}
    unidentified = []
    for p in files:
        if p.is_symlink() or not p.is_file():
            raise ValueError("source is not a regular NSP")
        if not 100 * 1024 < p.stat().st_size < 18 * 1024**3:
            raise ValueError("NSP size outside bounded range")
        with p.open("rb") as stream:
            if stream.read(4) != b"PFS0":
                raise ValueError("NSP PFS0 header absent")
        try:
            role = classify(p)
        except ValueError as exc:
            # Never use a size fallback to override contradictory title or
            # version tags. Unknown naming alone is not proof of bad data.
            if str(exc) != "unidentified package role; explicit title/version required":
                raise
            unidentified.append(p)
            continue
        if role in identified:
            raise ValueError("duplicate package role")
        identified[role] = p

    if unidentified:
        ordered = sorted(files, key=lambda p: p.stat().st_size, reverse=True)
        largest, smallest = ordered
        # An update is generally much smaller for this title. If sizes are
        # close, the source role must be established by an explicit marker.
        if smallest.stat().st_size * 2 >= largest.stat().st_size:
            raise ValueError("ambiguous base/update package sizes")
        inferred = {"base": largest, "update": smallest}
        if any(identified.get(role, path) != path
               for role, path in inferred.items()):
            raise ValueError("filename identity contradicts package sizes")
        identified = inferred

    if set(identified) != {"base", "update"}:
        raise ValueError("incomplete base/update pair")
    if not 128 * 1024**2 < identified["base"].stat().st_size < 18 * 1024**3:
        raise ValueError("base NSP size outside bounded range")
    if not 100 * 1024 < identified["update"].stat().st_size < 5 * 1024**3:
        raise ValueError("update NSP size outside bounded range")
    return identified


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
    print(f"DREAD_DIAG_V1 source={'ok' if source else 'fail'} "
          f"packages={'ok' if sources else 'fail'} "
          f"keys={'ok' if keys else 'fail'}")
    return 0


def diagnose_detailed():
    """Report a fixed error category, without echoing source names or paths."""
    source = package_ok = key_ok = False
    reason = "none"
    try:
        source_folder()
        source = True
        packages()
        package_ok = True
    except (OSError, ValueError) as exc:
        issue = str(exc).casefold()
        if "exactly two" in issue:
            reason = "count"
        elif "size" in issue:
            reason = "size_or_role"
        elif "pfs0" in issue:
            reason = "header"
        elif "title id" in issue:
            reason = "title_id"
        elif "version" in issue:
            reason = "version_or_name"
        elif "regular" in issue or "symlink" in issue:
            reason = "file_type"
        elif not source:
            reason = "source"
        else:
            reason = "role"
    try:
        private_keys()
        key_ok = True
    except (OSError, ValueError):
        pass
    print(f"DREAD_DIAG_V2 source={'ok' if source else 'fail'} "
          f"packages={'ok' if package_ok else 'fail'} "
          f"keys={'ok' if key_ok else 'fail'} reason={reason}")
    return 0


def dispatch(command, parent):
    if command not in ROUTES:
        return 126
    if command == "dread-diagnose-v1":
        return diagnose()
    if command == "dread-diagnose-v2":
        return diagnose_detailed()
    if command == "dread-probe-v1":
        packages()
        private_keys()
        print("DREAD_GATEWAY_V1")
        return 0
    if command == "dread-manifest-v1":
        pair = packages()
        print(TITLE, VERSION, pair["base"].stat().st_size,
              pair["update"].stat().st_size)
        return 0
    if command in ("dread-read-base", "dread-read-update"):
        role = command.removeprefix("dread-read-")
        parent.send_file(packages()[role])
        return 0
    if command == "dread-read-keys":
        parent.send_file(private_keys())
        return 0

    previous = parent.CACHE, parent.CONFLICTS, parent.OUTPUT
    try:
        parent.CACHE, parent.CONFLICTS, parent.OUTPUT = CACHE, CONFLICTS, OUTPUT
        if command == "dread-read-cache":
            parent.read_cache()
        elif command == "dread-write-cache":
            parent.write_cache()
        elif command == "dread-write-ipa":
            parent.receive_file("MetroidDread-nxnative.ipa", 16 * 1024**3)
        elif command == "dread-write-log":
            parent.receive_file("dread-build.log", 32 * 1024**2)
        elif command == "dread-write-survey":
            parent.receive_file("dread-survey.md", 4 * 1024**2)
        elif command == "dread-write-profile":
            parent.receive_file("dread-profile.tsv", 2 * 1024**2)
        elif command == "dread-write-inspection":
            parent.receive_file("dread-inspection.log", 8 * 1024**2)
        return 0
    finally:
        parent.CACHE, parent.CONFLICTS, parent.OUTPUT = previous
