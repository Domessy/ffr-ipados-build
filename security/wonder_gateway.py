#!/usr/bin/env python3
"""Super Mario Bros. Wonder 1.2.0 derived-profile XCI/NSP restricted SSH gateway.

No arbitrary filesystem traversal or shell commands. Local original files
are only read, and cache/output paths are project-specific.
"""
from pathlib import Path
import re
import stat

ROOT = Path.home() / "portage-ipados" / "super-mario-bros-wonder"
SOURCE_LINK = ROOT / "source"
KEYS = ROOT / "private" / "prod.keys"
CACHE = ROOT / "shader-cache"
CONFLICTS = ROOT / "shader-cache-conflicts"
OUTPUT = ROOT / "resultats"
TITLE = "010015100B514000"
UPDATE_TITLE = "010015100B514800"
VERSION = 'unverified'
ROUTES = frozenset({
    "wonder-probe-v1", "wonder-diagnose-v1", "wonder-diagnose-v2", "wonder-manifest-v1",
    "wonder-read-base", "wonder-read-update", "wonder-read-keys",
    "wonder-read-cache", "wonder-write-cache", "wonder-write-ipa", "wonder-write-log",
    "wonder-write-survey", "wonder-write-profile", "wonder-write-inspection",
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
        TITLE.casefold() in name or "base" in name or "super mario bros wonder" in name or
        "[v0]" in name or "version 1.0.0" in name
    )
    if base_hint and not update_hint and UPDATE_TITLE.casefold() not in name:
        if versions and versions != {0}:
            raise ValueError("base version marker not zero")
        return "base"
    raise ValueError("unidentified package role; explicit title/version required")


def packages():
    """Require the user's single base XCI and update NSP, never rename originals.

    File extensions determine roles; encrypted CNMT, not a guessed filename or
    file-size ratio, is the authoritative title/version check on the Mac.
    """
    files = sorted(p for p in source_folder().iterdir()
                   if p.suffix.casefold() in (".xci", ".nsp"))
    if len(files) != 2 or sum(p.suffix.casefold() == ".xci" for p in files) != 1:
        raise ValueError("exactly one XCI base and one NSP update required")
    result = {}
    for p in files:
        if p.is_symlink() or not p.is_file():
            raise ValueError("package must be a regular file")
        role = {".xci": "base", ".nsp": "update"}[p.suffix.casefold()]
        if role in result:
            raise ValueError("duplicate package role")
        ids = {tag.upper() for tag in TITLE_TAG.findall(p.name)}
        required_id = TITLE if role == "base" else UPDATE_TITLE
        if ids and ids != {required_id}:
            raise ValueError("explicit title ID contradicts package role")
        versions = {int(v) for v in VERSION_TAG.findall(p.name)}
        if role == "base" and versions and versions != {0}:
            raise ValueError("XCI base version marker must be v0")
        if role == "update" and versions and (
                len(versions) != 1 or 0 in versions or
                versions.intersection({65536, 327680})):
            raise ValueError("NSP version marker conflicts with requested 1.2.0")
        size = p.stat().st_size
        if role == "base" and not 128 * 1024**2 < size < 24 * 1024**3:
            raise ValueError("XCI base size outside bounded range")
        if role == "update" and not 100 * 1024 < size < 8 * 1024**3:
            raise ValueError("NSP update size outside bounded range")
        with p.open("rb") as stream:
            if role == "base":
                stream.seek(0x100)
                if stream.read(4) != b"HEAD":
                    raise ValueError("XCI HEAD header absent at offset 0x100")
            elif stream.read(4) != b"PFS0":
                raise ValueError("NSP PFS0 header absent")
        result[role] = p
    if set(result) != {"base", "update"}:
        raise ValueError("exactly one XCI base and one NSP update required")
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
    print(f"WONDER_DIAG_V1 source={'ok' if source else 'fail'} "
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
        elif "pfs0" in issue or "head" in issue:
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
    print(f"WONDER_DIAG_V2 source={'ok' if source else 'fail'} "
          f"packages={'ok' if package_ok else 'fail'} "
          f"keys={'ok' if key_ok else 'fail'} reason={reason}")
    return 0


def dispatch(command, parent):
    if command not in ROUTES:
        return 126
    if command == "wonder-diagnose-v1":
        return diagnose()
    if command == "wonder-diagnose-v2":
        return diagnose_detailed()
    if command == "wonder-probe-v1":
        packages()
        private_keys()
        print("WONDER_GATEWAY_V1")
        return 0
    if command == "wonder-manifest-v1":
        pair = packages()
        print(TITLE, VERSION, pair["base"].stat().st_size,
              pair["update"].stat().st_size)
        return 0
    if command in ("wonder-read-base", "wonder-read-update"):
        role = command.removeprefix("wonder-read-")
        parent.send_file(packages()[role])
        return 0
    if command == "wonder-read-keys":
        parent.send_file(private_keys())
        return 0

    previous = parent.CACHE, parent.CONFLICTS, parent.OUTPUT
    try:
        parent.CACHE, parent.CONFLICTS, parent.OUTPUT = CACHE, CONFLICTS, OUTPUT
        if command == "wonder-read-cache":
            parent.read_cache()
        elif command == "wonder-write-cache":
            parent.write_cache()
        elif command == "wonder-write-ipa":
            parent.receive_file("SuperMarioBrosWonder-nxnative.ipa", 16 * 1024**3)
        elif command == "wonder-write-log":
            parent.receive_file("wonder-build.log", 32 * 1024**2)
        elif command == "wonder-write-survey":
            parent.receive_file("wonder-survey.md", 4 * 1024**2)
        elif command == "wonder-write-profile":
            parent.receive_file("wonder-profile.tsv", 2 * 1024**2)
        elif command == "wonder-write-inspection":
            parent.receive_file("wonder-inspection.log", 8 * 1024**2)
        return 0
    finally:
        parent.CACHE, parent.CONFLICTS, parent.OUTPUT = previous
