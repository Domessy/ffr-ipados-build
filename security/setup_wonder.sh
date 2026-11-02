#!/usr/bin/env bash
# Reversible Super Mario Bros Wonder nxnative setup; never changes original NSP files.
set -euo pipefail
ROOT="$HOME/portage-ipados/super-mario-bros-wonder"
SRC="$HOME/Documents/Super Mario Bros Wonder"
GATE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/ffr_ssh_gate.py"

# Linux directory names are case-sensitive. Accept only a unique case-variant
# of the exact expected title under ~/Documents; never search other locations.
if [[ ! -d "$SRC" && ! -L "$SRC" ]]; then
  matches=()
  while IFS= read -r -d '' candidate; do
    matches+=("$candidate")
  done < <(find "$HOME/Documents" -mindepth 1 -maxdepth 1 -type d \
    -iname 'super mario bros wonder' -print0)
  if (( ${#matches[@]} == 1 )); then
    SRC="${matches[0]}"
    echo "WONDER: located the game folder using a case-insensitive exact-name match."
  fi
fi
if [[ ! -d "$SRC" || -L "$SRC" ]]; then
  echo "WONDER: original game directory unavailable or symbolic link rejected." >&2
  echo "WONDER: candidate directories (name only):" >&2
  find "$HOME/Documents" -mindepth 1 -maxdepth 1 -iname '*super*mario*bros*wonder*' -print0 |
    while IFS= read -r -d '' candidate; do
      printf '  %s\n' "${candidate##*/}" >&2
    done
  exit 1
fi
[[ -s "$SRC/prod.keys" && -f "$SRC/prod.keys" && ! -L "$SRC/prod.keys" ]] || {
  echo "WONDER: source prod.keys missing or not a regular file" >&2; exit 1
}
[[ ! -L "$ROOT" ]] || { echo "WONDER: project root cannot be a symlink" >&2; exit 1; }
mkdir -p "$ROOT/private" "$ROOT/resultats" "$ROOT/shader-cache" "$ROOT/shader-cache-conflicts"
for d in "$ROOT" "$ROOT/private" "$ROOT/resultats" "$ROOT/shader-cache" "$ROOT/shader-cache-conflicts"; do
  [[ ! -L "$d" ]] || { echo "WONDER: unexpected private directory symlink" >&2; exit 1; }
  chmod 700 "$d"
done
if [[ ! -e "$ROOT/source" && ! -L "$ROOT/source" ]]; then
  ln -s "$SRC" "$ROOT/source"
fi
[[ -L "$ROOT/source" && "$(readlink -f "$ROOT/source")" == "$(readlink -f "$SRC")" ]] || {
  echo "WONDER: unexpected source link" >&2; exit 1
}
if [[ ! -e "$ROOT/private/prod.keys" && ! -L "$ROOT/private/prod.keys" ]]; then
  install -m 600 -- "$SRC/prod.keys" "$ROOT/private/prod.keys"
fi
[[ -f "$ROOT/private/prod.keys" && ! -L "$ROOT/private/prod.keys" ]] || {
  echo "WONDER: private keys must be a regular file" >&2; exit 1
}
cmp -s -- "$SRC/prod.keys" "$ROOT/private/prod.keys" || {
  echo "WONDER: key mismatch; refusing to overwrite existing private copy" >&2; exit 1
}
chmod 600 "$ROOT/private/prod.keys"

echo "WONDER: fixed-code diagnostics (no filenames or key bytes)"
SSH_ORIGINAL_COMMAND=wonder-diagnose-v2 python3 "$GATE"
if ! probe="$(SSH_ORIGINAL_COMMAND=wonder-probe-v1 python3 "$GATE")"; then
  echo "WONDER: source validation failed; inspect WONDER_DIAG_V2 reason above." >&2
  echo "WONDER: local game files (names/sizes only; no keys or file contents):" >&2
  python3 - "$SRC" <<'PY' >&2
import sys
from pathlib import Path

root = Path(sys.argv[1])
suffixes = {".nsp", ".xci", ".nsz", ".xcz"}
try:
    entries = sorted(root.iterdir(), key=lambda p: p.name.casefold())
    files = []
    for entry in entries:
        if entry.is_symlink():
            continue
        if entry.is_file():
            files.append(entry)
        elif entry.is_dir():
            files.extend(p for p in entry.iterdir() if p.is_file() and not p.is_symlink())
    for path in sorted(files, key=lambda p: str(p).casefold()):
        if path.suffix.casefold() in suffixes:
            print(f"  {path.relative_to(root)} ({path.stat().st_size} bytes)")
except OSError as exc:
    print(f"  inventory unavailable ({type(exc).__name__})")
PY
  echo "WONDER: originals unchanged. Resolve the source layout before starting GitHub Actions." >&2
  exit 1
fi
[[ "$probe" == WONDER_GATEWAY_V1 ]] || exit 1
manifest="$(SSH_ORIGINAL_COMMAND=wonder-manifest-v1 python3 "$GATE")"
read -r title version base_size update_size <<< "$manifest"
[[ "$title" == 010015100B514000 && "$version" == unverified ]] || exit 1
[[ "$base_size" =~ ^[1-9][0-9]*$ && "$update_size" =~ ^[1-9][0-9]*$ ]] || exit 1
echo "WONDER_GATEWAY_V1"
echo "WONDER packages: base_bytes=$base_size update_bytes=$update_size"
echo "All results and shaders stay inside ~/portage-ipados/super-mario-bros-wonder/"
