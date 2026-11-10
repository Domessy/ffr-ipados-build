#!/usr/bin/env python3
"""Run nxnative with independent OOT2 shader checkpoints and private diagnostics.

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
try:
    from security.oot2_nup_info import release_identity
except ImportError:
    from oot2_nup_info import release_identity

TEMP = Path(os.environ["RUNNER_TEMP"])
WORKSPACE = Path(os.environ["GITHUB_WORKSPACE"])
CACHE = TEMP / "oot2-shader-cas"
CAS_DB = CACHE / "cas.db"
LOG = TEMP / "oot2-build.log"
OUTPUT = TEMP / "ZeldaOcarinaOfTime.ipa"
NUP_FOLDER = TEMP / "oot2-nup"
NUP = NUP_FOLDER / "OcarinaOfTime.nup"
PYTHON = TEMP / "oot2-venv" / "bin" / "python"
NATIVE = TEMP / "nxnative"
EXPORT = WORKSPACE / "security" / "oot2_sqlite_cas.py"
# Cap one shader build to 265 min and retain time for checkpoint/IPA upload on a 345 min job; subsequent runs reuse the shader CAS.
MAX_BUILD_SECONDS = 265 * 60
MIN_DISK_BYTES = 7 * (1024 ** 3)
SNAPSHOT_SECONDS = 12 * 60
active = None


def checkpoint(since_ns, final=False):
    """Stream only changed CAS files to the fixed SSH cache gateway."""
    threshold = time.time_ns() if final else time.time_ns() - 10_000_000_000
    print("Saving private shader-cache checkpoint to CachyOS...", flush=True)
    recv = subprocess.Popen(
        ["ssh", "-o", "ConnectTimeout=20", "-o", "ServerAliveInterval=30",
         "-o", "ServerAliveCountMax=6", "ffr-cachyos", "oot2-write-cache"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    sender = subprocess.Popen(
        [sys.executable, str(EXPORT), "export", str(CACHE),
         str(since_ns), str(threshold)],
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


def sync_private_diagnostic():
    """Send a bounded snapshot privately; never echo the logfile in public CI."""
    if not LOG.is_file():
        return
    # Last 8 MiB only; gateway atomically replaces the previous diagnostic.
    with LOG.open("rb") as f:
        f.seek(max(0, LOG.stat().st_size - 8 * 1024**2))
        data = f.read(8 * 1024**2)
    if not data:
        return
    try:
        proc = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=20", "-o", "ServerAliveInterval=30",
             "-o", "ServerAliveCountMax=6", "ffr-cachyos", "oot2-write-log"],
            input=data, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            check=False, timeout=90,
        )
        print(f"OOT2 private log snapshot: bytes={len(data)}, status={'saved' if proc.returncode == 0 else 'failed'}", flush=True)
    except (OSError, subprocess.TimeoutExpired):
        print("OOT2 private diagnostic sync unavailable; build continues.", flush=True)


def reclaim_runner_input_after_build():
    """Delete only ephemeral runner copy, never original CachyOS NUP."""
    if NUP.is_file() and not NUP.is_symlink():
        NUP.unlink()


# Strictly numeric shader progress: no game-specific logs, paths, secrets,
# filenames or compiler diagnostics reach public GitHub Actions.
PROGRESS = re.compile(
    rb"\[\d+/\d+\] iOS shaders[^\n]*? (cache check|compiling): "
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
    layout = os.environ.get("OOT2_IPA_LAYOUT", "bundle")
    if layout not in ("bundle", "separate", "local-bundle"):
        print("OOT2: invalid IPA layout; refusing build.", flush=True)
        return 1
    # Upstream's separate mode needs the extracted RomFS to stay available
    # after packaging for its one-time device transfer. This is runner-local;
    # it does not make an ephemeral runner persistent or skip shader builds.
    layout_args = (["--romfs", "separate", "--keep-extracted"]
                   if layout in ("separate", "local-bundle") else ["--no-keep-extracted"])
    CACHE.mkdir(parents=True, exist_ok=True, mode=0o700)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    if not CAS_DB.is_file():
        print("OOT2: SQLite shader cache not initialized; refusing build.", flush=True)
        return 1
    env = dict(os.environ, DMSH_CAS=str(CAS_DB),
               OOT2_RELEASE_EPHEMERAL_NUP=str(NUP))
    # Preserve the restore's older mtimes; do not re-upload already stored files.
    since_ns = time.time_ns()
    last_sync = time.monotonic()
    started = time.monotonic()
    if not NUP.is_file() or NUP.is_symlink():
        print("OOT2: private NUP missing; no build started.", flush=True)
        return 1
    try:
        identity = release_identity(NUP)
        if identity != os.environ.get("OOT2_NUP_ID"):
            raise ValueError("source identity changed")
    except (OSError, ValueError):
        print("OOT2: runner NUP does not match the source release preflight; no build started.", flush=True)
        return 1
    env["OOT2_RELEASE_EPHEMERAL_NUP_ID"] = identity
    cmd = [str(PYTHON), str(NATIVE / "scripts" / "build_ipa_from_nsp.py"),
           str(NUP), "-o", str(OUTPUT), "-p", "v131072",
           "--platform", "ios", "--work-dir", str(TEMP / "oot2-work"),
           "--show-fps", "--gpu", "none", *layout_args]
    if os.environ.get("OOT2_RUNTIME_VARIANT") in ("upstream-v4", "ipad-v5", "ipad-v6", "ipad-v7"):
        # Bake the proven setting into this diagnostic IPA so deleting a data
        # container cannot silently restore anonymous guest memory. The host
        # reads Documents/env.txt first, so an explicit device override wins.
        filename = ("oot2_ipad_v7_defaults.env" if os.environ.get("OOT2_RUNTIME_VARIANT") == "ipad-v7" else "oot2_ipad_v6_defaults.env" if os.environ.get("OOT2_RUNTIME_VARIANT") == "ipad-v6" else "oot2_ipad_v5_defaults.env" if os.environ.get("OOT2_RUNTIME_VARIANT") == "ipad-v5"
                    else "oot2_ipados_defaults.env")
        defaults = WORKSPACE / "security" / filename
        if not defaults.is_file() or defaults.is_symlink():
            print("OOT2: iPadOS defaults missing; refusing build.", flush=True)
            return 1
        cmd += ["--env-file", str(defaults)]
    print(f"OOT2 IPA layout: {layout}.", flush=True)
    if layout == "separate":
        print("Slim IPA requires the matching RomFS in the existing OOT2 device container; no device transfer is performed by this build.", flush=True)
    print("nxnative started; full diagnostic remains private.", flush=True)
    planned_stop = False
    rc = 1
    with LOG.open("wb") as log:
        active = subprocess.Popen(cmd, cwd=NATIVE, env=env, stdout=log,
                                  stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while active.poll() is None:
                time.sleep(10)
                elapsed = int((time.monotonic() - started) / 60)
                log_bytes = LOG.stat().st_size if LOG.exists() else 0
                free_gib = shutil.disk_usage(TEMP).free / 1024**3
                if int(time.monotonic() - started) % 60 < 10:
                    print(f"nxnative: {elapsed} min; private log {log_bytes} bytes; "
                          f"free disk {free_gib:.1f} GiB.", flush=True)
                if elapsed % 5 == 0:
                    public_shader_progress()
                if time.monotonic() - last_sync >= SNAPSHOT_SECONDS:
                    since_ns = checkpoint(since_ns)
                    sync_private_diagnostic()
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
    sync_private_diagnostic()
    if planned_stop:
        print("Shader work checkpointed; relaunch a NEW run to resume from CAS.", flush=True)
        return 75
    if rc != 0:
        print("nxnative returned non-zero; see private log on CachyOS.", flush=True)
        return rc or 1
    if not OUTPUT.is_file() or OUTPUT.stat().st_size == 0:
        print("nxnative returned zero but produced no IPA.", flush=True)
        return 1
    print("nxnative built an IPA successfully; iPad gameplay unverified.", flush=True)
    return 0


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)
    sys.exit(compile_ipa())
