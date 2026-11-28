#!/usr/bin/env python3
"""Receive ONE original Switch 2 NUP via title-scoped SSH, numeric progress only.

No NUP bytes, private filenames, credentials, IPs or local paths are logged.
Only fixed, allowlisted forced SSH commands are executed.
"""
import argparse
import os
from pathlib import Path
import select
import subprocess
import tempfile
import time

ROUTES = {"v16-cache": "oot2-read-cache-v16", "v16-checkpoint": "oot2-read-checkpoint-v16", "v15-cache": "oot2-read-cache-v15", "v15-checkpoint": "oot2-read-checkpoint-v15", "v14-cache": "oot2-read-cache-v14", "v14-checkpoint": "oot2-read-checkpoint-v14", "v13-cache": "oot2-read-cache-v13", "v13-checkpoint": "oot2-read-checkpoint-v13", "v12-cache": "oot2-read-cache-v12", "v12-checkpoint": "oot2-read-checkpoint-v12", "resume-v11": "oot2-read-resume-v11", "v11-checkpoint": "oot2-read-checkpoint-v11", "v10-checkpoint": "oot2-read-checkpoint-v10", "v9-checkpoint": "oot2-read-checkpoint-v9", "resume-v9": "oot2-read-resume-v9", "resume-v8": "oot2-read-resume-v8", "resume-v6": "oot2-read-resume-v6", "resume-v5": "oot2-read-resume-v5", "nup": "oot2-read-nup", "metal-snapshot": "oot2-read-metal-snapshot-v1"}
ROUTES.update({'aot-input': 'oot2-aot-v8-read-input', 'aot-cache': 'oot2-aot-v8-read-cache'})
DESTINATIONS = {"v16-cache": ("oot2-shader-cas", "metal-snapshot.zst"), "v16-checkpoint": ("oot2-v16", "input.ipa"), "v15-cache": ("oot2-shader-cas", "metal-snapshot.zst"), "v15-checkpoint": ("oot2-v15", "input.ipa"), "v14-cache": ("oot2-shader-cas", "metal-snapshot.zst"), "v14-checkpoint": ("oot2-v14", "input.ipa"), "v13-cache": ("oot2-shader-cas", "metal-snapshot.zst"), "v13-checkpoint": ("oot2-v13", "input.ipa"), "v12-cache": ("oot2-shader-cas", "metal-snapshot.zst"), "v12-checkpoint": ("oot2-v12", "input.ipa"), "resume-v11": ("oot2-shader-cas", "metal-snapshot.zst"), "v11-checkpoint": ("oot2-v11", "input.ipa"), "v10-checkpoint": ("oot2-v10", "input.ipa"), "v9-checkpoint": ("oot2-v9", "input.ipa"), "resume-v9": ("oot2-shader-cas", "metal-snapshot.zst"), "resume-v8": ("oot2-shader-cas", "metal-snapshot.zst"), "resume-v6": ("oot2-shader-cas", "metal-snapshot.zst"), "resume-v5": ("oot2-shader-cas", "metal-snapshot.zst"), "nup": ("oot2-nup", "OcarinaOfTime.nup"),
                "metal-snapshot": ("oot2-shader-cas", "metal-snapshot.zst")}
MiB = 1024 ** 2
DESTINATIONS.update({'aot-input': ('oot2-aot', 'input.ipa'), 'aot-cache': ('oot2-aot', 'cache.tar.gz')})
ROUTES.update({'fullwarm-kit': 'oot2-fullwarm-v8-read-kit', 'fullwarm-cache': 'oot2-fullwarm-v8-read-cache'})
DESTINATIONS.update({'fullwarm-kit': ('oot2-fullwarm', 'hostkit.tar.zst'), 'fullwarm-cache': ('oot2-fullwarm', 'cache.tar.gz')})
GiB = 1024 ** 3
MAX_SIZE = 80 * GiB
REPORT_EVERY = 10.0


def status(role, received, expected, started, previous_at, previous_bytes, now):
    elapsed = max(0.001, now - started)
    duration = max(0.001, now - previous_at)
    rate = max(0.0, (received - previous_bytes) / duration)
    avg = received / elapsed
    remaining = max(0, expected - received)
    eta_seconds = remaining / avg if avg > 0 else None
    eta = f"{eta_seconds / 60:.1f} min" if eta_seconds is not None else "n/a"
    print(
        f"OOT2 {role}: {received / GiB:.2f}/{expected / GiB:.2f} GiB "
        f"({100 * received / expected:.1f}%) | "
        f"rate {rate / MiB:.1f} MiB/s | "
        f"avg {avg / MiB:.1f} MiB/s | ETA {eta}",
        flush=True,
    )


def transfer(role, expected, output):
    if role not in ROUTES or not 0 < expected <= MAX_SIZE:
        raise ValueError("invalid OOT2 transfer role or declared size")
    runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    folder_name, filename = DESTINATIONS[role]
    folder = runner_temp / folder_name
    if output.parent.resolve(strict=True) != folder.resolve(strict=True):
        raise ValueError("output must be in the dedicated OOT2 transfer directory")
    if output.name != filename or output.is_symlink():
        raise ValueError("invalid output filename")

    # Progress comes from how many bytes the receiving Mac has written, not
    # the sending CachyOS process's file offset or SSH's buffered bytes.
    print(f"OOT2 {role}: transferring {expected / GiB:.2f} GiB", flush=True)
    ssh = None
    fd = None
    temporary = None
    received = 0
    start = previous_at = time.monotonic()
    previous_bytes = 0
    try:
        fd, temporary = tempfile.mkstemp(prefix=f".{role}-", suffix=".partial", dir=folder)
        os.fchmod(fd, 0o600)
        ssh = subprocess.Popen(
            ["ssh", "-o", "ConnectTimeout=20",
             "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=6",
             "ffr-cachyos", ROUTES[role]],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, bufsize=0,
        )
        with os.fdopen(fd, "wb", buffering=0) as dest:
            fd = None
            while True:
                ready, _, _ = select.select([ssh.stdout], [], [], 1.0)
                if ready:
                    chunk = os.read(ssh.stdout.fileno(), MiB)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > expected:
                        raise ValueError("received more data than declared")
                    dest.write(chunk)
                now = time.monotonic()
                if now - previous_at >= REPORT_EVERY:
                    status(role, received, expected, start, previous_at, previous_bytes, now)
                    previous_at, previous_bytes = now, received
            dest.flush()
            os.fsync(dest.fileno())

        rc = ssh.wait(timeout=30)
        if rc != 0:
            raise RuntimeError(f"SSH transfer failed (exit {rc})")
        if received != expected:
            raise ValueError("incomplete transfer")
        os.replace(temporary, output)
        temporary = None
        now = time.monotonic()
        status(role, received, expected, start, previous_at, previous_bytes, now)
        print(f"OOT2 {role}: verified complete", flush=True)
    finally:
        if fd is not None:
            os.close(fd)
        if ssh is not None:
            if ssh.stdout:
                ssh.stdout.close()
            if ssh.poll() is None:
                ssh.terminate()
                try:
                    ssh.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    ssh.kill()
                    ssh.wait()
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=tuple(ROUTES))
    parser.add_argument("expected_bytes", type=int)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        transfer(args.role, args.expected_bytes, args.output)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        # No path or tool-generated message from private data reaches public logs.
        print(f"OOT2 {args.role}: transfer failed ({type(error).__name__})", flush=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
