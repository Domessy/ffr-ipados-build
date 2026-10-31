#!/usr/bin/env python3
"""FFR-only SSH forced command gateway. Python stdlib; no arbitrary shell."""
import hashlib
import os
import re
import shutil
import stat
import sys
import tarfile
import tempfile
from pathlib import Path

HOME = Path.home()
SOURCE = HOME / "Documents" / "FF Resonance"
PRIVATE = HOME / "portage-ipados" / "ff-resonance" / "private" / "prod.keys"
OUTPUT = HOME / "portage-ipados" / "ff-resonance" / "resultats"
CACHE = HOME / "portage-ipados" / "ff-resonance" / "shader-cache"
CONFLICTS = HOME / "portage-ipados" / "ff-resonance" / "shader-cache-conflicts"
CAS_ROOTS = frozenset({"index", "shader", "variant", "metallib"})
CAS_PART = re.compile(r"[A-Za-z0-9_.-]{1,180}\Z")
CAS_MAX_BYTES = 120 * 1024**3
CAS_MAX_FILE = 1024**3
CAS_MAX_FILES = 1_000_000

READABLE = {
    "read-base": SOURCE / "v-final_fantasy_resonance.nsp",
    "read-update": SOURCE / "v-final_fantasy_resonance_v65536.nsp",
    "read-keys": PRIVATE,
}
WRITABLE = {
    "write-ipa": ("FFR-iPadOS.ipa", 16 * 1024**3),
    "write-log": ("ffr-build.log", 32 * 1024**2),
}


def send_file(path: Path, allow_key_link: bool = False) -> None:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    if not allow_key_link:
        flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as source:
        if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
            raise ValueError("source is not a regular file")
        shutil.copyfileobj(source, sys.stdout.buffer, length=1024 * 1024)


def receive_file(filename: str, max_bytes: int) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(OUTPUT, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=".ffr-upload-", dir=OUTPUT)
    try:
        os.fchmod(fd, 0o600)
        total = 0
        with os.fdopen(fd, "wb") as destination:
            while True:
                chunk = sys.stdin.buffer.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError("upload exceeds size limit")
                destination.write(chunk)
            if total == 0:
                raise ValueError("empty upload")
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary, OUTPUT / filename)
        print("FFR_UPLOAD_OK", file=sys.stderr)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def safe_cache_parts(name: str):
    # No absolute paths, dot parts, backslashes, unicode controls or long names.
    parts = name.split("/")
    if not (2 <= len(parts) <= 7 and parts[0] in CAS_ROOTS
            and all(p not in (".", "..") and CAS_PART.fullmatch(p) for p in parts)):
        raise ValueError("unrecognized cache name")
    return parts


def cache_file(path: Path):
    # No symlinks anywhere inside the user-owned dedicated shader cache.
    cursor = path
    while cursor != CACHE.parent:
        if cursor.is_symlink():
            raise ValueError("cache symlink")
        cursor = cursor.parent


def read_cache() -> None:
    CACHE.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tarfile.open(fileobj=sys.stdout.buffer, mode="w|gz", compresslevel=1) as archive:
        for rootname in sorted(CAS_ROOTS):
            base = CACHE / rootname
            if not base.is_dir():
                continue
            for folder, dirs, files in os.walk(base, followlinks=False):
                dirs[:] = sorted(d for d in dirs if not os.path.islink(os.path.join(folder, d)))
                for name in sorted(files):
                    path = Path(folder) / name
                    parts = path.relative_to(CACHE).parts
                    try:
                        safe_cache_parts("/".join(parts))
                        metadata = path.lstat()
                    except (ValueError, OSError):
                        continue
                    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > CAS_MAX_FILE:
                        continue
                    try:
                        archive.add(str(path), arcname="/".join(parts), recursive=False)
                    except FileNotFoundError:
                        continue


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for block in iter(lambda: src.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_cache() -> None:
    """Append-only CAS import. Never replace a differing existing file."""
    CACHE.mkdir(mode=0o700, parents=True, exist_ok=True)
    cache_file(CACHE)
    count = total = created = reused = conflicts = 0
    with tarfile.open(fileobj=sys.stdin.buffer, mode="r|gz") as archive:
        for member in archive:
            parts = safe_cache_parts(member.name)
            if not member.isfile() or member.size > CAS_MAX_FILE:
                raise ValueError("cache member is not a regular bounded file")
            count += 1
            total += member.size
            if count > CAS_MAX_FILES or total > CAS_MAX_BYTES:
                raise ValueError("cache upload limit")
            destination = CACHE.joinpath(*parts)
            cache_file(destination)
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            cache_file(destination)
            fd, temporary = tempfile.mkstemp(prefix=".ffr-cas-", dir=destination.parent)
            try:
                os.fchmod(fd, 0o600)
                source = archive.extractfile(member)
                if source is None:
                    raise ValueError("unreadable cache member")
                remaining = member.size
                with os.fdopen(fd, "wb") as output:
                    while remaining:
                        block = source.read(min(1024 * 1024, remaining))
                        if not block:
                            raise ValueError("truncated cache member")
                        output.write(block)
                        remaining -= len(block)
                # Hard-link publishing is atomic and fails if an existing file
                # already owns the path. No os.replace() of cache contents.
                try:
                    os.link(temporary, destination)
                    created += 1
                except FileExistsError:
                    cache_file(destination)
                    if sha256_file(destination) == sha256_file(Path(temporary)):
                        reused += 1
                        continue
                    # Keep BOTH contents. Conflicts are excluded from read-cache
                    # and cannot silently replace an older compiled shader.
                    if CONFLICTS.is_symlink():
                        raise ValueError("conflict root symlink")
                    conflict = CONFLICTS.joinpath(*parts[:-1], parts[-1] + "." + sha256_file(Path(temporary)) + ".conflict")
                    conflict.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    cursor = conflict
                    while cursor != CONFLICTS.parent:
                        if cursor.is_symlink():
                            raise ValueError("conflict path symlink")
                        cursor = cursor.parent
                    try:
                        os.link(temporary, conflict)
                    except FileExistsError:
                        pass
                    conflicts += 1
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
    # Numeric-only response. Safe to expose to the public Actions heartbeat.
    print(f"FFR_CACHE_NEW={created} FFR_CACHE_REUSED={reused} FFR_CACHE_CONFLICTS={conflicts}")



def main() -> int:
    command = os.environ.get("SSH_ORIGINAL_COMMAND", "")
    try:
        if command == "probe":
            print("FFR_GATEWAY_OK")
        elif command == "probe-cache-v2":
            print("FFR_GATEWAY_CACHE_V2")
        elif command.startswith("silksong-"):
            import silksong_gateway
            return silksong_gateway.dispatch(command, sys.modules[__name__])
        elif command.startswith("tales-"):
            import tales_gateway
            return tales_gateway.dispatch(command, sys.modules[__name__])
        elif command.startswith("botw-"):
            import botw_gateway
            return botw_gateway.dispatch(command, sys.modules[__name__])
        elif command.startswith("totk-mng-"):
            import totk_mng_gateway
            return totk_mng_gateway.dispatch(command, sys.modules[__name__])
        elif command.startswith("mpr-"):
            import mpr_gateway
            return mpr_gateway.dispatch(command, sys.modules[__name__])
        elif command in READABLE:
            # The user-selected prod.keys is a symlink created by initial setup.
            send_file(READABLE[command], allow_key_link=(command == "read-keys"))
        elif command in WRITABLE:
            filename, limit = WRITABLE[command]
            receive_file(filename, limit)
        elif command == "read-cache":
            read_cache()
        elif command == "write-cache":
            write_cache()
        else:
            print("FFR: command not permitted", file=sys.stderr)
            return 126
    except (OSError, ValueError) as exc:
        # Do not echo paths or sensitive file contents into public CI logs.
        print(f"FFR gateway failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
