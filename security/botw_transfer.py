#!/usr/bin/env python3
"""Receive one BOTW NSP over SSH with numeric-only live progress in public CI.

No NSP bytes, private filenames, credentials, IPs or local paths are logged.
Only fixed, allowlisted forced SSH commands are executed.
"""
import argparse
import os
from pathlib import Path
import select
import subprocess
import tempfile
import time

ROUTES = {
    "base": "botw-read-base",
    "update": "botw-read-update",
    "dlc1": "botw-read-dlc1",
    "dlc2": "botw-read-dlc2",
}
MiB = 1024 ** 2
GiB = 1024 ** 3
MAX_SIZE = 32 * GiB
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
        f"BOTW {role}: {received / GiB:.2f}/{expected / GiB:.2f} GiB "
        f"({100 * received / expected:.1f}%) | "
        f"rate {rate / MiB:.1f} MiB/s | "
        f"avg {avg / MiB:.1f} MiB/s | ETA {eta}",
        flush=True,
    )


def transfer(role, expected, output):
    if role not in ROUTES or not 0 < expected <= MAX_SIZE:
        raise ValueError("invalid BOTW transfer role or declared size")
    runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    folder = runner_temp / "botw-nsp"
    if output.parent.resolve(strict=True) != folder.resolve(strict=True):
        raise ValueError("output must be in the dedicated BOTW NSP directory")
    if output.suffix.lower() != ".nsp" or output.is_symlink():
        raise ValueError("invalid output filename")

    # Progress comes from how many bytes the receiving Mac has written, not
    # the sending CachyOS process's file offset or SSH's buffered bytes.
    print(f"BOTW {role}: transferring {expected / GiB:.2f} GiB", flush=True)
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
        print(f"BOTW {role}: verified complete", flush=True)
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
        print(f"BOTW {args.role}: transfer failed ({type(error).__name__})", flush=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
