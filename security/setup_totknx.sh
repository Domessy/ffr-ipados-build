#!/usr/bin/env bash
# One-time, reversible configuration for the separate Zelda TOTK nxnative project.
# Never modifies or deletes the original NSPs or existing MacNativeGames installation.
set -euo pipefail

ROOT="$HOME/portage-ipados/zelda-totk-nxnative"
SRC="$HOME/Documents/The Legend of Zelda Tears of the Kingdom"
GATE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/ffr_ssh_gate.py"

[[ -d "$SRC" && ! -L "$SRC" ]] || { echo "TOTKNX: original source directory unavailable" >&2; exit 1; }
[[ -f "$SRC/prod.keys" && ! -L "$SRC/prod.keys" && -s "$SRC/prod.keys" ]] || {
  echo "TOTKNX: private original prod.keys missing or not a regular file" >&2
  exit 1
}
[[ ! -L "$ROOT" ]] || { echo "TOTKNX: root must not be a symlink" >&2; exit 1; }
mkdir -p "$ROOT/private" "$ROOT/resultats" "$ROOT/shader-cache" "$ROOT/shader-cache-conflicts"
for dir in "$ROOT" "$ROOT/private" "$ROOT/resultats" "$ROOT/shader-cache" "$ROOT/shader-cache-conflicts"; do
  [[ ! -L "$dir" ]] || { echo "TOTKNX: unexpected symlink in private project directory" >&2; exit 1; }
  chmod 700 "$dir"
done
if [[ ! -e "$ROOT/source" && ! -L "$ROOT/source" ]]; then
  ln -s "$SRC" "$ROOT/source"
fi
[[ -L "$ROOT/source" ]] || { echo "TOTKNX: source selection is not a symlink" >&2; exit 1; }
[[ "$(readlink -f "$ROOT/source")" == "$(readlink -f "$SRC")" ]] || {
  echo "TOTKNX: source selection differs from expected original location" >&2
  exit 1
}
if [[ ! -e "$ROOT/private/prod.keys" && ! -L "$ROOT/private/prod.keys" ]]; then
  install -m 600 -- "$SRC/prod.keys" "$ROOT/private/prod.keys"
fi
[[ -f "$ROOT/private/prod.keys" && ! -L "$ROOT/private/prod.keys" ]] || {
  echo "TOTKNX: dedicated key file must be a regular file" >&2; exit 1
}
cmp -s -- "$SRC/prod.keys" "$ROOT/private/prod.keys" || {
  echo "TOTKNX: dedicated keys do not match source; refusing to overwrite" >&2; exit 1
}
chmod 600 "$ROOT/private/prod.keys"

probe="$(SSH_ORIGINAL_COMMAND=totknx-probe-v1 python3 "$GATE")"
[[ "$probe" == 'TOTKNX_GATEWAY_V1' ]] || {
  echo "TOTKNX: gateway probe failed" >&2; exit 1
}
manifest="$(SSH_ORIGINAL_COMMAND=totknx-manifest-v1 python3 "$GATE")"
read -r title update base_bytes update_bytes <<< "$manifest"
[[ "$title" == '0100F2C0115B6000' && "$update" == 720896 ]] || {
  echo "TOTKNX: title/version mismatch" >&2; exit 1
}
[[ "$base_bytes" =~ ^[1-9][0-9]*$ && "$update_bytes" =~ ^[1-9][0-9]*$ ]] || {
  echo "TOTKNX: unexpected source sizes" >&2; exit 1
}
echo "TOTKNX_GATEWAY_V1"
echo "TOTKNX source packages: base_bytes=$base_bytes update_bytes=$update_bytes"
echo "TOTKNX files and keys isolated under ~/portage-ipados/zelda-totk-nxnative/"
echo 'Original NSPs, MacNativeGames IPA and other games left unchanged.'
