#!/usr/bin/env python3
"""Verify encrypted Super Mario Bros. Wonder base/update CNMT and tag only the runner's patch NSP.

Private diagnostics go to RUNNER_TEMP/wonder-inspection.log, returned by a fixed
SSH route. Public GitHub logs show only fixed stage labels and numeric statuses.
Never modify the user's CachyOS source NSPs or reveal keys to Actions logs.
"""
import os
from pathlib import Path
import re
import subprocess

TITLE = "010015100B514000"
UPDATE = "010015100B514800"
CONTENT = re.compile(r"^content (Application|Patch|AddOnContent) ([0-9A-Fa-f]{16}) (\d+)$", re.M)
STAGES = frozenset({"build-inspector", "base-contents", "update-contents", "validate-metadata", "rename-update", "prepare"})
MAX_DIAGNOSTIC_BYTES = 1024 * 1024


class InspectionError(RuntimeError):
    def __init__(self, stage, status):
        assert stage in STAGES
        self.stage = stage
        self.status = status
        super().__init__(f"{stage}: {status}")


def meta_rows(stdout):
    return [(kind, title.upper(), int(version))
            for kind, title, version in CONTENT.findall(stdout)]


def validate_metadata(base_stdout, update_stdout):
    base = meta_rows(base_stdout)
    patch = meta_rows(update_stdout)
    if base != [("Application", TITLE, 0)]:
        raise ValueError("base NSP CNMT does not match the expected application")
    if len(patch) != 1 or patch[0][:2] != ("Patch", UPDATE):
        raise ValueError("update NSP CNMT does not match the expected patch title")
    version = patch[0][2]
    # We do not know the source's numeric revision in advance. The displayed
    # version 1.2.0 is independently verified from the extracted NACP.
    # Reject registered 1.0.1/1.2.1 builds: those would not derive profiles.
    if not 0 < version <= 0x7FFFFFFF or version in (65536, 327680):
        raise ValueError("patch revision invalid or registered to a different display version")
    return version


def record(log_path, stage, result):
    """Only this private file gets subprocess output, never the public logs."""
    with log_path.open("ab") as stream:
        stream.write(f"stage={stage}; exit_code={result.returncode}\n".encode("ascii"))
        for label, value in (("stdout", result.stdout), ("stderr", result.stderr)):
            value = (value or "").encode("utf-8", errors="replace")
            stream.write(f"{label}_bytes={len(value)}\n".encode("ascii"))
            stream.write(value[:MAX_DIAGNOSTIC_BYTES])
            stream.write(b"\n")


def checked(command, stage, log_path, timeout):
    """Run inspection and preserve bounded private compiler/LibHac diagnostics."""
    try:
        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        with log_path.open("ab") as stream:
            stream.write(f"stage={stage}; timeout\n".encode("ascii"))
        raise InspectionError(stage, "timeout") from None
    except OSError as exc:
        with log_path.open("ab") as stream:
            stream.write(f"stage={stage}; os_error={type(exc).__name__}\n".encode("ascii"))
        raise InspectionError(stage, "execution-error") from None
    record(log_path, stage, result)
    if result.returncode:
        raise InspectionError(stage, f"exit-{result.returncode}")
    return result.stdout


def main():
    temp = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    folder = temp / "wonder-nsp"
    keys = temp / "wonder-prod.keys"
    base = folder / f"Super Mario Bros. Wonder [{TITLE}][v0].nsp"
    update = folder / f"Super Mario Bros. Wonder update [{UPDATE}].nsp"
    upstream = temp / "nxnative" / "dm" / "tools" / "nx_extract"
    output = temp / "wonder-nsp-inspection"
    log_path = temp / "wonder-inspection.log"
    with log_path.open("wb") as private_log:
        private_log.write(b"WONDER_INSPECTION_V2\n")
    log_path.chmod(0o600)
    output.mkdir(mode=0o700, exist_ok=True)
    for path in (base, update, keys):
        if not path.is_file() or path.is_symlink():
            raise InspectionError("prepare", "expected-file-missing")
    if not (upstream / "nx_extract.csproj").is_file():
        raise InspectionError("prepare", "upstream-project-missing")

    print("WONDER: compiling pinned private NSP inspector.", flush=True)
    checked(["dotnet", "build", str(upstream), "-c", "Release",
             "-o", str(output), "-v", "quiet", "-nologo"],
            "build-inspector", log_path, timeout=300)
    # Homebrew's 'dotnet' CLI knows its runtime location, but a standalone
    # apphost ('nx_extract') can exit 131 when DOTNET_ROOT is not set on macOS.
    # Launch the exact built managed DLL through the proven CLI instead.
    # No globally installed runtime or machine-level configuration is changed.
    managed = output / "nx_extract.dll"
    if not managed.is_file():
        raise InspectionError("build-inspector", "managed-dll-missing")

    print("WONDER: verifying encrypted base and patch metadata.", flush=True)
    base_stdout = checked(["dotnet", str(managed), str(keys), "--contents", str(base)],
                          "base-contents", log_path, timeout=180)
    update_stdout = checked(["dotnet", str(managed), str(keys), "--contents", str(update)],
                            "update-contents", log_path, timeout=180)
    try:
        version = validate_metadata(base_stdout, update_stdout)
    except ValueError:
        raise InspectionError("validate-metadata", "identity-or-version") from None
    renamed = folder / f"Super Mario Bros. Wonder update [{UPDATE}][v{version}].nsp"
    if renamed.exists():
        raise InspectionError("rename-update", "destination-exists")
    update.rename(renamed)
    # This file contains ONLY the verified numeric patch revision.
    # The build runner reads it and passes -p vN, ensuring upstream derives
    # a new profile rather than silently selecting registered 1.2.1.
    version_path = temp / "wonder-verified-patch.version"
    version_path.write_text(str(version) + "\n", encoding="ascii")
    version_path.chmod(0o600)
    print(f"WONDER: base/update CNMT verified; user patch v{version} (derived profile required).", flush=True)


if __name__ == "__main__":
    try:
        main()
    except InspectionError as exc:
        print(f"WONDER: inspection failed at stage={exc.stage}; status={exc.status}; "
              "detailed log remains private.", flush=True)
        raise SystemExit(1)
    except (OSError, ValueError) as exc:
        print(f"WONDER: inspector failed before the build; error_type={type(exc).__name__}; "
              "see private inspection log.", flush=True)
        raise SystemExit(1)
