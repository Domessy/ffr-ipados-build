#!/usr/bin/env bash
# Reversible Super Mario Odyssey nxnative setup; never changes original game files.
set -euo pipefail
ROOT="$HOME/portage-ipados/super-mario-odyssey"
SRC="$HOME/Documents/Super Mario Odyssey"
GATE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/ffr_ssh_gate.py"

[[ -d "$SRC" && ! -L "$SRC" ]] || { echo "ODY: original game directory missing" >&2; exit 1; }
[[ -s "$SRC/prod.keys" && -f "$SRC/prod.keys" && ! -L "$SRC/prod.keys" ]] || {
  echo "ODY: source prod.keys missing or not a regular file" >&2; exit 1
}
[[ ! -L "$ROOT" ]] || { echo "ODY: project root cannot be a symlink" >&2; exit 1; }
mkdir -p "$ROOT/private" "$ROOT/resultats" "$ROOT/shader-cache" "$ROOT/shader-cache-conflicts"
for d in "$ROOT" "$ROOT/private" "$ROOT/resultats" "$ROOT/shader-cache" "$ROOT/shader-cache-conflicts"; do
  [[ ! -L "$d" ]] || { echo "ODY: unexpected private directory symlink" >&2; exit 1; }
  chmod 700 "$d"
done
if [[ ! -e "$ROOT/source" && ! -L "$ROOT/source" ]]; then
  ln -s "$SRC" "$ROOT/source"
fi
[[ -L "$ROOT/source" && "$(readlink -f "$ROOT/source")" == "$(readlink -f "$SRC")" ]] || {
  echo "ODY: unexpected source link" >&2; exit 1
}
if [[ ! -e "$ROOT/private/prod.keys" && ! -L "$ROOT/private/prod.keys" ]]; then
  install -m 600 -- "$SRC/prod.keys" "$ROOT/private/prod.keys"
fi
[[ -f "$ROOT/private/prod.keys" && ! -L "$ROOT/private/prod.keys" ]] || {
  echo "ODY: private keys must be a regular file" >&2; exit 1
}
cmp -s -- "$SRC/prod.keys" "$ROOT/private/prod.keys" || {
  echo "ODY: key mismatch; refusing to overwrite existing private copy" >&2; exit 1
}
chmod 600 "$ROOT/private/prod.keys"

echo "ODY: fixed-code diagnostics (no filenames or key bytes)"
SSH_ORIGINAL_COMMAND=ody-diagnose-v1 python3 "$GATE"
if ! probe="$(SSH_ORIGINAL_COMMAND=ody-probe-v1 python3 "$GATE")"; then
  echo "ODY: source package identities unrecognized; check both NSP filenames for base/update version 1.4.1" >&2
  exit 1
fi
[[ "$probe" == ODY_GATEWAY_V1 ]] || exit 1
manifest="$(SSH_ORIGINAL_COMMAND=ody-manifest-v1 python3 "$GATE")"
read -r title version base_size update_size <<< "$manifest"
[[ "$title" == 0100000000010000 && "$version" == 393216 ]] || exit 1
[[ "$base_size" =~ ^[1-9][0-9]*$ && "$update_size" =~ ^[1-9][0-9]*$ ]] || exit 1
echo "ODY_GATEWAY_V1"
echo "ODY packages: base_bytes=$base_size update_bytes=$update_size"
echo "All results and shaders stay inside ~/portage-ipados/super-mario-odyssey/"
