#!/usr/bin/env python3
"""Bounded MacNativeGames TOTK build. Public CI contains only numeric status."""
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

TEMP = Path(os.environ["RUNNER_TEMP"])
REPO = TEMP / "macnativegames"
NSPS = TEMP / "totk-mng-nsp"
KEYS = TEMP / "totk-mng-prod.keys"
FONTS = TEMP / "totk-mng-fonts"
WORK = TEMP / "totk-mng-work"
OUT = TEMP / "ZeldaTOTK-MacNativeGames.ipa"
LOG = TEMP / "totk-mng-build.log"
PY = "/opt/homebrew/bin/python3.14"
MAX_BUILD_S = 180 * 60
MIN_FREE = 7 * 1024**3
STEP = re.compile(rb"(?m)^\[[0-9:]+\]\s*([1-4])/4 (?:code|data|shaders|app):")
active = None


def stop(proc):
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGINT)
        proc.wait(timeout=30)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=20)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait(timeout=10)


def handler(_sig, _frame):
    if active is not None:
        stop(active)
    raise KeyboardInterrupt


def current_step():
    if not LOG.exists():
        return "starting"
    with LOG.open("rb") as stream:
        stream.seek(max(0, LOG.stat().st_size - 128000))
        matches = list(STEP.finditer(stream.read()))
    return matches[-1].group(1).decode("ascii") + "/4" if matches else "setup"


def main():
    global active
    package = os.environ.get("TOTK_MNG_PACKAGE", "full")
    if package not in {"full", "slim"}:
        print("TOTK invalid packaging mode", flush=True)
        return 2
    if not all(p.is_file() for p in [KEYS, NSPS / "base.nsp", NSPS / "update.nsp"]):
        print("TOTK required private source inputs are absent", flush=True)
        return 2
    if not all(FONTS.joinpath(f).is_file() for f in (
        "0-standard.bfttf",
        "1-chinese-simplified.bfttf",
        "2-chinese-simplified-extension.bfttf",
        "3-chinese-traditional.bfttf",
        "4-korean.bfttf",
        "5-nintendo-extension.bfttf",
    )):
        print("TOTK system-font set is incomplete", flush=True)
        return 2
    cmd = [
        PY, str(REPO / "build_app.py"), str(NSPS / "base.nsp"),
        "-k", str(KEYS), "--update", str(NSPS / "update.nsp"),
        "--shared-fonts", str(FONTS),
        "--platform", "ios", "--ios-game-data", "app" if package == "full" else "documents",
        "--no-shader-reminder",
        "--work", str(WORK), "-o", str(OUT),
    ]
    # GPU architecture is not guessed from device name: only an explicitly
    # verified architecture is used for the optional offline pipeline archive.
    gpu = os.environ.get("TOTK_MNG_DEVICE_GPU", "").strip()
    if gpu:
        if not re.fullmatch(r"applegpu_g[a-z0-9]+", gpu):
            print("TOTK GPU architecture is not in accepted form", flush=True)
            return 2
        cmd.extend(["--device-gpu", gpu])
    LOG.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    planned_stop = False
    print(f"TOTK MacNativeGames starting: package={package}; GPU-specific archive={'yes' if gpu else 'no'}", flush=True)
    with LOG.open("wb") as logfile:
        active = subprocess.Popen(cmd, cwd=REPO, stdin=subprocess.DEVNULL,
                                  stdout=logfile, stderr=subprocess.STDOUT,
                                  start_new_session=True)
        try:
            while active.poll() is None:
                time.sleep(30)
                elapsed = int((time.monotonic() - started) // 60)
                available = shutil.disk_usage(TEMP).free
                print(f"TOTK build: stage={current_step()}; elapsed={elapsed} min; "
                      f"free={available / 1024**3:.1f} GiB; log={LOG.stat().st_size} bytes", flush=True)
                if available < MIN_FREE or time.monotonic() - started > MAX_BUILD_S:
                    planned_stop = True
                    print("TOTK runner safeguard reached; stopping; see private diagnostic.", flush=True)
                    stop(active)
                    break
            rc = active.wait()
        except KeyboardInterrupt:
            planned_stop = True
            stop(active)
            rc = active.wait()
    active = None
    if planned_stop:
        return 75
    if rc or not OUT.is_file() or OUT.stat().st_size <= 0:
        print("TOTK build did not produce an IPA; see private diagnostic.", flush=True)
        return rc or 1
    print(f"TOTK IPA created: {OUT.stat().st_size} bytes; packaging={package}.", flush=True)
    if package == "slim":
        romfs = WORK / "totk" / "extracted" / "v143" / "romfs" / "romfs.bin"
        if not romfs.is_file() or not romfs.stat().st_size:
            print("TOTK separate game-data image missing", flush=True)
            return 2
        print(f"TOTK external game-data image created: {romfs.stat().st_size} bytes.", flush=True)
    return 0


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)
    sys.exit(main())
