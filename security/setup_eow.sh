#!/usr/bin/env bash
# Reversible The Legend of Zelda Echoes of Wisdom nxnative setup; never changes original XCI/NSP files.
set -euo pipefail
ROOT="$HOME/portage-ipados/zelda-echoes-of-wisdom"
SRC="$HOME/Documents/The Legend of Zelda Echoes of Wisdom"
GATE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/ffr_ssh_gate.py"

[[ -d "$SRC" && ! -L "$SRC" ]] || { echo "EOW: original game directory missing" >&2; exit 1; }
[[ -s "$SRC/prod.keys" && -f "$SRC/prod.keys" && ! -L "$SRC/prod.keys" ]] || {
  echo "EOW: source prod.keys missing or not a regular file" >&2; exit 1
}
[[ ! -L "$ROOT" ]] || { echo "EOW: project root cannot be a symlink" >&2; exit 1; }
mkdir -p "$ROOT/private" "$ROOT/resultats" "$ROOT/shader-cache" "$ROOT/shader-cache-conflicts"
for d in "$ROOT" "$ROOT/private" "$ROOT/resultats" "$ROOT/shader-cache" "$ROOT/shader-cache-conflicts"; do
  [[ ! -L "$d" ]] || { echo "EOW: unexpected private directory symlink" >&2; exit 1; }
  chmod 700 "$d"
done
if [[ ! -e "$ROOT/source" && ! -L "$ROOT/source" ]]; then
  ln -s "$SRC" "$ROOT/source"
fi
[[ -L "$ROOT/source" && "$(readlink -f "$ROOT/source")" == "$(readlink -f "$SRC")" ]] || {
  echo "EOW: unexpected source link" >&2; exit 1
}
if [[ ! -e "$ROOT/private/prod.keys" && ! -L "$ROOT/private/prod.keys" ]]; then
  install -m 600 -- "$SRC/prod.keys" "$ROOT/private/prod.keys"
fi
[[ -f "$ROOT/private/prod.keys" && ! -L "$ROOT/private/prod.keys" ]] || {
  echo "EOW: private keys must be a regular file" >&2; exit 1
}
cmp -s -- "$SRC/prod.keys" "$ROOT/private/prod.keys" || {
  echo "EOW: key mismatch; refusing to overwrite existing private copy" >&2; exit 1
}
chmod 600 "$ROOT/private/prod.keys"

echo "EOW: fixed-code diagnostics (no filenames or key bytes)"
SSH_ORIGINAL_COMMAND=eow-diagnose-v1 python3 "$GATE"
if ! probe="$(SSH_ORIGINAL_COMMAND=eow-probe-v1 python3 "$GATE")"; then
  echo "EOW: source package identities unrecognized; check the base .xci header and update .nsp (profile 1.1.0)" >&2
  exit 1
fi
[[ "$probe" == EOW_GATEWAY_V1 ]] || exit 1
manifest="$(SSH_ORIGINAL_COMMAND=eow-manifest-v1 python3 "$GATE")"
read -r title version base_size update_size <<< "$manifest"
[[ "$title" == 01008CF01BAAC000 && "$version" == 196608 ]] || exit 1
[[ "$base_size" =~ ^[1-9][0-9]*$ && "$update_size" =~ ^[1-9][0-9]*$ ]] || exit 1
echo "EOW_GATEWAY_V1"
echo "EOW packages: base_bytes=$base_size update_bytes=$update_size"
echo "All results and shaders stay inside ~/portage-ipados/zelda-echoes-of-wisdom/"
