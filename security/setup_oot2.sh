#!/usr/bin/env bash
# CachyOS setup for original Switch 2 NUP; reversible and non-destructive.
set -euo pipefail
ROOT="$HOME/portage-ipados/oot-switch2"
SRC="$HOME/Documents/The Legend of Zelda Ocarina of TIme"
GATE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/ffr_ssh_gate.py"

if [[ ! -d "$SRC" && ! -L "$SRC" ]]; then
  matches=()
  while IFS= read -r -d '' candidate; do
    matches+=("$candidate")
  done < <(find "$HOME/Documents" -mindepth 1 -maxdepth 1 -type d \
    -iname 'the legend of zelda ocarina of time' -print0)
  if (( ${#matches[@]} == 1 )); then
    SRC="${matches[0]}"
    echo "OOT2: exact case-insensitive game folder selected."
  fi
fi
if [[ ! -d "$SRC" || -L "$SRC" ]]; then
  echo "OOT2: original game directory missing or symbolic link rejected." >&2
  exit 1
fi
[[ ! -L "$ROOT" ]] || { echo "OOT2: workspace symlink rejected" >&2; exit 1; }
mkdir -p "$ROOT" "$ROOT/resultats" "$ROOT/shader-cache" "$ROOT/shader-cache-conflicts"
for d in "$ROOT" "$ROOT/resultats" "$ROOT/shader-cache" "$ROOT/shader-cache-conflicts"; do
  [[ ! -L "$d" ]] || { echo "OOT2: workspace directory symlink rejected" >&2; exit 1; }
  chmod 700 "$d"
done
if [[ ! -e "$ROOT/source" && ! -L "$ROOT/source" ]]; then
  ln -s "$SRC" "$ROOT/source"
fi
[[ -L "$ROOT/source" && "$(readlink -f "$ROOT/source")" == "$(readlink -f "$SRC")" ]] || {
  echo "OOT2: source link points elsewhere; refusing overwrite." >&2
  exit 1
}
echo "OOT2: NUP only; any prod.keys stay in Documents and are not copied."
SSH_ORIGINAL_COMMAND=oot2-diagnose-v1 python3 "$GATE"
if ! probe="$(SSH_ORIGINAL_COMMAND=oot2-probe-v1 python3 "$GATE")"; then
  echo "OOT2: NUP preflight failed; inspect OOT2_DIAG_V1. No original modified." >&2
  python3 - "$SRC" <<'PY' >&2
from pathlib import Path
import sys
p = Path(sys.argv[1])
items = sorted(x for x in p.iterdir() if x.suffix.casefold() == ".nup")
print(f"OOT2: source NUP count={len(items)}")
for file in items:
    try:
        print(f"  bytes={file.stat().st_size}")
    except OSError:
        pass
PY
  exit 1
fi
[[ "$probe" == OOT2_GATEWAY_V1 ]] || exit 1
read -r tid ver size bases patches count <<< "$(
  SSH_ORIGINAL_COMMAND=oot2-manifest-v1 python3 "$GATE"
)"
[[ "$tid" == 0400486024DEC000 && "$ver" == v131072 ]] || exit 1
[[ "$bases" =~ ^[01]$ && "$patches" == 1 ]] || exit 1
[[ "$size" =~ ^[1-9][0-9]*$ ]] || exit 1
echo "OOT2_GATEWAY_V1 source=ok base=$bases update=v131072 packages=$count bytes=$size"
echo "OOT2: originals unchanged; private workspace ~/portage-ipados/oot-switch2/"
