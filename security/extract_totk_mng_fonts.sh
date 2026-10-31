#!/usr/bin/env bash
# Extract the six original TOTK system fonts from a user-supplied firmware ZIP.
# All work is confined to ~/portage-ipados/zelda-totk-mng; no key/font material
# is added to GitHub or emitted in the logs.
set -euo pipefail
umask 077

if [ "$#" -ne 1 ]; then
  echo "Usage: bash security/extract_totk_mng_fonts.sh /path/to/own-switch-firmware.zip" >&2
  exit 2
fi

ZIP="$1"
ROOT="$HOME/portage-ipados/zelda-totk-mng"
KEYS="$HOME/portage-ipados/ff-resonance/private/prod.keys"
TOOLS="$ROOT/tooling/MacNativeGames"
VENV="$ROOT/tooling/font-venv"
FINAL="$ROOT/private/shared-fonts"
SHA="933b6a0d1438de160208a0a13eb5e8d7a2cb8094"

test -f "$ZIP" && test -r "$ZIP" || { echo 'Firmware ZIP inaccessible.' >&2; exit 1; }
test -s "$KEYS" || { echo 'Private prod.keys file unavailable.' >&2; exit 1; }
if [ -L "$FINAL" ]; then echo 'Refusing symlinked destination.' >&2; exit 1; fi

mkdir -p "$ROOT/tooling" "$ROOT/private"
if [ -d "$FINAL" ] && [ -n "$(find "$FINAL" -mindepth 1 -maxdepth 1 -print -quit)" ]; then
  echo 'Private shared-fonts directory already contains files; refusing overwrite.' >&2
  exit 1
fi

if [ ! -d "$TOOLS/.git" ]; then
  if [ -e "$TOOLS" ] && [ -n "$(find "$TOOLS" -mindepth 1 -maxdepth 1 -print -quit)" ]; then
    echo 'Tool directory is not a git checkout and is not empty.' >&2
    exit 1
  fi
  mkdir -p "$TOOLS"
  git -C "$TOOLS" init -q
  git -C "$TOOLS" remote add origin https://github.com/ly05010419/MacNativeGames.git
fi
CURRENT="$(git -C "$TOOLS" rev-parse HEAD 2>/dev/null || true)"
if [ "$CURRENT" != "$SHA" ]; then
  git -C "$TOOLS" diff --quiet && git -C "$TOOLS" diff --cached --quiet || {
    echo 'Local MacNativeGames checkout has modifications; refusing overwrite.' >&2; exit 1;
  }
  git -C "$TOOLS" fetch --quiet --depth 1 origin "$SHA"
  git -C "$TOOLS" checkout --quiet --detach FETCH_HEAD
fi
test "$(git -C "$TOOLS" rev-parse HEAD)" = "$SHA"
echo 'MacNativeGames pinned source verified.'

if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
fi
if ! "$VENV/bin/python" -c 'import cryptography' 2>/dev/null; then
  "$VENV/bin/python" -m pip install --disable-pip-version-check --quiet cryptography
fi

TEMP="$(mktemp -d "$ROOT/private/.firmware-extract.XXXXXXXX")"
trap 'rm -rf -- "$TEMP"' EXIT
mkdir "$TEMP/nca"

# Flatten only NCA files; restrict archive traversal and decompression size.
python3 - "$ZIP" "$TEMP/nca" <<'PY'
import re
import shutil
import sys
import zipfile
from pathlib import Path

archive, out = Path(sys.argv[1]), Path(sys.argv[2])
written, total = 0, 0
with zipfile.ZipFile(archive) as z:
    entries = z.infolist()
    if len(entries) > 6000:
        raise SystemExit("Firmware ZIP contains too many entries")
    for entry in entries:
        if entry.is_dir():
            continue
        parts = entry.filename.replace("\\", "/").split("/")
        if not parts or ".." in parts or parts[0] in ("", "."):
            raise SystemExit("Unsafe ZIP member path")
        name = parts[-1]
        if name.lower().endswith(".nca"):
            output_name = name
        elif name == "00" and len(parts) >= 2 and re.fullmatch(r"[a-fA-F0-9]{32}", parts[-2]):
            output_name = parts[-2] + ".nca"
        else:
            continue
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,160}", output_name):
            raise SystemExit("Unexpected NCA filename")
        mode = (entry.external_attr >> 16) & 0o170000
        if mode == 0o120000:
            raise SystemExit("Symlinked ZIP member refused")
        total += entry.file_size
        if entry.file_size < 0xC00 or entry.file_size > 2 * 1024**3 or total > 8 * 1024**3:
            raise SystemExit("Unexpected firmware size")
        with z.open(entry) as stream, (out / output_name).open("xb") as dest:
            shutil.copyfileobj(stream, dest, length=1024 * 1024)
        written += 1
if not written:
    raise SystemExit("No .nca files found in firmware ZIP")
print(f"Firmware unpacked privately: {written} NCA files; {total} bytes.")
PY

"$VENV/bin/python" "$TOOLS/games/totk/scripts/extract_shared_fonts.py" \
  --keys "$KEYS" --firmware "$TEMP/nca" --output "$TEMP/fonts"

"$VENV/bin/python" - "$TEMP/fonts" <<'PY'
import json
import sys
from pathlib import Path
folder = Path(sys.argv[1])
manifest = json.loads((folder / "manifest.json").read_text())
expected = [
    "0-standard.bfttf", "1-chinese-simplified.bfttf",
    "2-chinese-simplified-extension.bfttf", "3-chinese-traditional.bfttf",
    "4-korean.bfttf", "5-nintendo-extension.bfttf",
]
if manifest.get("status") != "pass" or len(manifest.get("fonts", [])) != 6:
    raise SystemExit("Shared-font manifest validation failed")
for name in expected:
    file = folder / name
    if file.is_symlink() or not file.is_file() or file.stat().st_size < 9:
        raise SystemExit("Required shared font missing")
print("Six original system fonts extracted and verified.")
PY

# The previous setup creates an empty output folder; remove only if empty.
if [ -d "$FINAL" ]; then
  rmdir -- "$FINAL" || { echo 'Destination is not empty; refusing overwrite.' >&2; exit 1; }
fi
mv -- "$TEMP/fonts" "$FINAL"
echo 'TOTK shared-fonts installed in private project directory.'
echo 'Run: env SSH_ORIGINAL_COMMAND=totk-mng-manifest-v1 python3 security/ffr_ssh_gate.py'
