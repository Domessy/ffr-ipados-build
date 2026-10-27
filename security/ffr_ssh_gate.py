#!/usr/bin/env python3
"""FFR-only SSH forced command gateway. Python stdlib; no arbitrary shell."""
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path

HOME = Path.home()
SOURCE = HOME / "Documents" / "FF Resonance"
PRIVATE = HOME / "portage-ipados" / "ff-resonance" / "private" / "prod.keys"
OUTPUT = HOME / "portage-ipados" / "ff-resonance" / "resultats"

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


def main() -> int:
    command = os.environ.get("SSH_ORIGINAL_COMMAND", "")
    try:
        if command == "probe":
            print("FFR_GATEWAY_OK")
        elif command in READABLE:
            # The user-selected prod.keys is a symlink created by initial setup.
            send_file(READABLE[command], allow_key_link=(command == "read-keys"))
        elif command in WRITABLE:
            filename, limit = WRITABLE[command]
            receive_file(filename, limit)
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
