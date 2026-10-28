#!/usr/bin/env python3
"""Run nxnative and checkpoint its content-addressed shader cache to CachyOS.

The public Actions log only receives elapsed time and aggregate diagnostic
size. Never forward nxnative's private output, keys, or game file contents.
"""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

TEMP = Path(os.environ["RUNNER_TEMP"])
WORKSPACE = Path(os.environ["GITHUB_WORKSPACE"])
CACHE = TEMP / "ffr-shader-cas"
LOG = TEMP / "ffr-build.log"
OUTPUT = TEMP / "FFR-iPadOS.ipa"
NSPS = TEMP / "ffr-nsp"
KEYS = TEMP / "ffr-prod.keys"
PYTHON = TEMP / "ffr-venv" / "bin" / "python"
NATIVE = TEMP / "nxnative"
EXPORT = WORKSPACE / "security" / "cache_export.py"
# 240 min max of actual build work; leave time in the 345 min job for transfers.
MAX_BUILD_SECONDS = 240 * 60
MIN_DISK_BYTES = 5 * (1024 ** 3)
SNAPSHOT_SECONDS = 15 * 60
active = None


def checkpoint(since_ns, final=False):
    """Stream only changed CAS files to the fixed SSH cache gateway."""
    threshold = time.time_ns() if final else time.time_ns() - 10_000_000_000
    print("Saving private shader-cache checkpoint to CachyOS...", flush=True)
    recv = subprocess.Popen(
        ["ssh", "-o", "ConnectTimeout=20", "-o", "ServerAliveInterval=30",
         "-o", "ServerAliveCountMax=6", "ffr-cachyos", "write-cache"],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    sender = subprocess.Popen(
        [sys.executable, str(EXPORT), str(CACHE), str(since_ns), str(threshold)],
        stdout=recv.stdin, stderr=subprocess.DEVNULL,
    )
    recv.stdin.close()
    try:
        sender_rc = sender.wait(timeout=30 * 60)
        recv_rc = recv.wait(timeout=45)
    except subprocess.TimeoutExpired:
        sender.kill()
        recv.kill()
        sender.wait()
        recv.wait()
        print("Checkpoint transfer timed out; prior checkpoints remain.", flush=True)
        return since_ns
    if sender_rc != 0 or recv_rc != 0:
        print("Checkpoint transfer failed; prior checkpoints remain.", flush=True)
        return since_ns
    print("Private cache checkpoint saved.", flush=True)
    return threshold


def stop_build(proc):
    """Stop the game tool and all its compiler children in their own session."""
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGINT)
        proc.wait(timeout=40)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=20)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait(timeout=10)


def handler(_signum, _frame):
    if active is not None:
        stop_build(active)
    raise KeyboardInterrupt


def main():
    global active
    CACHE.mkdir(parents=True, exist_ok=True, mode=0o700)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, DMSH_CAS=str(CACHE))
    # Preserve the restore's older mtimes; do not re-upload already stored files.
    since_ns = time.time_ns()
    last_sync = time.monotonic()
    started = time.monotonic()
    cmd = [str(PYTHON), str(NATIVE / "scripts" / "build_ipa_from_nsp.py"),
           str(NSPS), "-k", str(KEYS), "-o", str(OUTPUT),
           "--no-keep-extracted", "--show-fps"]
    print("nxnative started; full diagnostic remains private.", flush=True)
    planned_stop = False
    rc = 1
    with LOG.open("wb") as log:
        active = subprocess.Popen(cmd, cwd=NATIVE, env=env, stdout=log,
                                  stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while active.poll() is None:
                time.sleep(60)
                elapsed = int((time.monotonic() - started) / 60)
                log_bytes = LOG.stat().st_size if LOG.exists() else 0
                free_gib = shutil.disk_usage(TEMP).free / 1024**3
                print(f"nxnative: {elapsed} min; private log {log_bytes} bytes; "
                      f"free disk {free_gib:.1f} GiB.", flush=True)
                if time.monotonic() - last_sync >= SNAPSHOT_SECONDS:
                    since_ns = checkpoint(since_ns)
                    last_sync = time.monotonic()
                if (time.monotonic() - started >= MAX_BUILD_SECONDS
                        or shutil.disk_usage(TEMP).free < MIN_DISK_BYTES):
                    planned_stop = True
                    print("Pausing build to protect runner limit/disk; saving CAS.", flush=True)
                    stop_build(active)
                    break
            rc = active.wait()
        except KeyboardInterrupt:
            planned_stop = True
            stop_build(active)
            rc = active.wait()
    active = None
    checkpoint(since_ns, final=True)
    if planned_stop:
        print("Shader work checkpointed; relaunch a NEW run to resume from CAS.", flush=True)
        return 75
    if rc != 0:
        print("nxnative returned non-zero; see private log on CachyOS.", flush=True)
        return rc or 1
    if not OUTPUT.is_file() or OUTPUT.stat().st_size == 0:
        print("nxnative returned zero but produced no IPA.", flush=True)
        return 1
    print("nxnative built an IPA successfully.", flush=True)
    return 0


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)
    sys.exit(main())
