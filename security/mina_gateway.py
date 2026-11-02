#!/usr/bin/env python3
"""Mina the Hollower experimental/provisional nxnative port: restricted SSH gateway.

No arbitrary filesystem traversal or shell commands. Local original files
are only read, and cache/output paths are project-specific.
"""
from pathlib import Path
import re
import stat

ROOT = Path.home() / "portage-ipados" / "mina-the-hollower"
SOURCE_LINK = ROOT / "source"
KEYS = ROOT / "private" / "prod.keys"
CACHE = ROOT / "shader-cache"
CONFLICTS = ROOT / "shader-cache-conflicts"
OUTPUT = ROOT / "resultats"
TITLE = "0100DCD01F306000"
UPDATE_TITLE = "0100DCD01F306800"
VERSION = 'unverified'
ROUTES = frozenset({
    "mina-probe-v1", "mina-diagnose-v1", "mina-diagnose-v2", "mina-manifest-v1",
    "mina-read-base", "mina-read-update", "mina-read-keys",
    "mina-read-cache", "mina-write-cache", "mina-write-ipa", "mina-write-log",
    "mina-write-survey", "mina-write-profile",
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
    update_hint = (
        UPDATE_TITLE.casefold() in name or "update" in name or
        "mise a jour" in name or "mise à jour" in name or
        any(v > 0 for v in versions)
    )
    if update_hint:
        if TITLE.casefold() in name and UPDATE_TITLE.casefold() not in name and ids:
            raise ValueError("update marked as base title")
        if versions and (0 in versions or len(versions) != 1):
            raise ValueError("update version marker ambiguous")
        return "update"
    base_hint = (
        TITLE.casefold() in name or "base" in name or "mina the hollower" in name or
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
    print(f"MINA_DIAG_V1 source={'ok' if source else 'fail'} "
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
    print(f"MINA_DIAG_V2 source={'ok' if source else 'fail'} "
          f"packages={'ok' if package_ok else 'fail'} "
          f"keys={'ok' if key_ok else 'fail'} reason={reason}")
    return 0


def dispatch(command, parent):
    if command not in ROUTES:
        return 126
    if command == "mina-diagnose-v1":
        return diagnose()
    if command == "mina-diagnose-v2":
        return diagnose_detailed()
    if command == "mina-probe-v1":
        packages()
        private_keys()
        print("MINA_GATEWAY_V1")
        return 0
    if command == "mina-manifest-v1":
        pair = packages()
        print(TITLE, VERSION, pair["base"].stat().st_size,
              pair["update"].stat().st_size)
        return 0
    if command in ("mina-read-base", "mina-read-update"):
        role = command.removeprefix("mina-read-")
        parent.send_file(packages()[role])
        return 0
    if command == "mina-read-keys":
        parent.send_file(private_keys())
        return 0

    previous = parent.CACHE, parent.CONFLICTS, parent.OUTPUT
    try:
        parent.CACHE, parent.CONFLICTS, parent.OUTPUT = CACHE, CONFLICTS, OUTPUT
        if command == "mina-read-cache":
            parent.read_cache()
        elif command == "mina-write-cache":
            parent.write_cache()
        elif command == "mina-write-ipa":
            parent.receive_file("MinaTheHollower-nxnative.ipa", 16 * 1024**3)
        elif command == "mina-write-log":
            parent.receive_file("mina-build.log", 32 * 1024**2)
        elif command == "mina-write-survey":
            parent.receive_file("mina-survey.md", 4 * 1024**2)
        elif command == "mina-write-profile":
            parent.receive_file("mina-profile.tsv", 2 * 1024**2)
        return 0
    finally:
        parent.CACHE, parent.CONFLICTS, parent.OUTPUT = previous
