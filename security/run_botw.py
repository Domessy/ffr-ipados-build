#!/usr/bin/env python3
"""Run nxnative with independent BOTW shader checkpoints and private diagnostics.

The public Actions log only receives elapsed time and aggregate diagnostic
size. Never forward nxnative's private output, keys, or game file contents.
"""
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

TEMP = Path(os.environ["RUNNER_TEMP"])
WORKSPACE = Path(os.environ["GITHUB_WORKSPACE"])
CACHE = TEMP / "botw-shader-cas"
LOG = TEMP / "botw-build.log"
OUTPUT = TEMP / "ZeldaBreathOfTheWild-iPadOS.ipa"
NSPS = TEMP / "botw-nsp"
KEYS = TEMP / "botw-prod.keys"
PYTHON = TEMP / "botw-venv" / "bin" / "python"
NATIVE = TEMP / "nxnative"
EXPORT = WORKSPACE / "security" / "cache_export.py"
# 210 min for build; leave sufficient margin for large NSP and IPA SSH transfers.
MAX_BUILD_SECONDS = 210 * 60
MIN_DISK_BYTES = 7 * (1024 ** 3)
SNAPSHOT_SECONDS = 15 * 60
active = None


def checkpoint(since_ns, final=False):
    """Stream only changed CAS files to the fixed SSH cache gateway."""
    threshold = time.time_ns() if final else time.time_ns() - 10_000_000_000
    print("Saving private shader-cache checkpoint to CachyOS...", flush=True)
    recv = subprocess.Popen(
        ["ssh", "-o", "ConnectTimeout=20", "-o", "ServerAliveInterval=30",
         "-o", "ServerAliveCountMax=6", "ffr-cachyos", "botw-write-cache"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    sender = subprocess.Popen(
        [sys.executable, str(EXPORT), str(CACHE), str(since_ns), str(threshold)],
        stdout=recv.stdin, stderr=subprocess.DEVNULL,
    )
    recv.stdin.close()
    # communicate() must not attempt to flush a stream that was closed after
    # handing the pipe to the exporter subprocess.
    recv.stdin = None
    try:
        sender_rc = sender.wait(timeout=30 * 60)
        response, _ = recv.communicate(timeout=45)
        recv_rc = recv.returncode
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
    # The trusted CachyOS gateway returns integers only; never copy its
    # arbitrary text into the public log.
    match = re.search(rb"FFR_CACHE_NEW=(\d+) FFR_CACHE_REUSED=(\d+) FFR_CACHE_CONFLICTS=(\d+)", response)
    if match:
        created, reused, conflicts = map(int, match.groups())
        print(f"Private cache checkpoint saved: new={created}, "
              f"identical={reused}, conflicts={conflicts}.", flush=True)
        if conflicts:
            print("WARNING: differing versions preserved separately on CachyOS; "
                  "existing CAS never overwritten.", flush=True)
    else:
        print("Private cache checkpoint saved; import summary unavailable.", flush=True)
    return threshold


def reclaim_runner_nsps():
    """Delete runner-only NSP copies once nxnative reports its iOS shader stage.

    At that stage nxnative has completed base, update and both DLC extractions and reads the
    extracted RomFS/ExeFS files. Never touch the user's original NSPs.
    """
    if not LOG.is_file():
        return False
    with LOG.open("rb") as stream:
        stream.seek(max(0, LOG.stat().st_size - 65536))
        tail = stream.read()
    # Exact stage marker; do not reclaim files during extraction or survey.
    if b"iOS shaders" not in tail:
        return False
    freed = 0
    for path in sorted(NSPS.glob("*.nsp")):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            size = path.stat().st_size
            path.unlink()
            freed += size
        except OSError:
            pass
    if freed:
        print(
            f"Reclaimed {freed / 1024**3:.2f} GiB: removed only runner NSP "
            "copies after the iOS shader stage began.",
            flush=True,
        )
    return freed > 0


# Strictly numeric shader progress: no game-specific logs, paths, secrets,
# filenames or compiler diagnostics reach public GitHub Actions.
PROGRESS = re.compile(
    rb"\[6/8\] iOS shaders[^\n]*? (cache check|compiling): "
    rb"(\d+)%, ([\d,]+)/([\d,]+) shaders, ([\d,]+) (cached|not cached)"
)


def public_shader_progress():
    if not LOG.is_file():
        return
    with LOG.open("rb") as source:
        source.seek(max(0, LOG.stat().st_size - 32768))
        data = source.read()
    matches = list(PROGRESS.finditer(data))
    if not matches:
        return
    phase, pct, done, total, count, kind = matches[-1].groups()
    print(
        f"shaders: phase={phase.decode('ascii')}; "
        f"progress={int(pct)}%; processed={int(done.replace(b',', b''))}/"
        f"{int(total.replace(b',', b''))}; "
        f"{kind.decode('ascii')}={int(count.replace(b',', b''))}.",
        flush=True,
    )


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


def compile_ipa():
    global active
    CACHE.mkdir(parents=True, exist_ok=True, mode=0o700)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, DMSH_CAS=str(CACHE))
    # Preserve the restore's older mtimes; do not re-upload already stored files.
    since_ns = time.time_ns()
    last_sync = time.monotonic()
    started = time.monotonic()
    nsps_reclaimed = False
    cmd = [str(PYTHON), str(NATIVE / "scripts" / "build_ipa_from_nsp.py"),
           str(NSPS), "-k", str(KEYS), "-o", str(OUTPUT),
           "--no-keep-extracted", "--show-fps", "--gpu", "none"]
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
                if not nsps_reclaimed:
                    nsps_reclaimed = reclaim_runner_nsps()
                free_gib = shutil.disk_usage(TEMP).free / 1024**3
                print(f"nxnative: {elapsed} min; private log {log_bytes} bytes; "
                      f"free disk {free_gib:.1f} GiB.", flush=True)
                if elapsed % 5 == 0:
                    public_shader_progress()
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
    public_shader_progress()
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
    sys.exit(compile_ipa())
