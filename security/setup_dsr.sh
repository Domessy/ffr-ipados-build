#!/usr/bin/env bash
# Reversible Dark Souls Remastered nxnative setup; never changes original NSP files.
set -euo pipefail
ROOT="$HOME/portage-ipados/dark-souls-remastered"
SRC="$HOME/Documents/Dark Souls Remastered"
GATE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/ffr_ssh_gate.py"

# Linux directory names are case-sensitive. Accept only a unique case-variant
# of the exact expected title under ~/Documents; never search other locations.
if [[ ! -d "$SRC" && ! -L "$SRC" ]]; then
  matches=()
  while IFS= read -r -d '' candidate; do
    matches+=("$candidate")
  done < <(find "$HOME/Documents" -mindepth 1 -maxdepth 1 -type d \
    -iname 'dark souls remastered' -print0)
  if (( ${#matches[@]} == 1 )); then
    SRC="${matches[0]}"
    echo "DSR: located the game folder using a case-insensitive exact-name match."
  fi
fi
if [[ ! -d "$SRC" || -L "$SRC" ]]; then
  echo "DSR: original game directory unavailable or symbolic link rejected." >&2
  echo "DSR: candidate directories (name only):" >&2
  find "$HOME/Documents" -mindepth 1 -maxdepth 1 -iname '*dark*souls*' \
    -printf '  %f (%y)\n' >&2 || true
  exit 1
fi
[[ -s "$SRC/prod.keys" && -f "$SRC/prod.keys" && ! -L "$SRC/prod.keys" ]] || {
  echo "DSR: source prod.keys missing or not a regular file" >&2; exit 1
}
[[ ! -L "$ROOT" ]] || { echo "DSR: project root cannot be a symlink" >&2; exit 1; }
mkdir -p "$ROOT/private" "$ROOT/resultats" "$ROOT/shader-cache" "$ROOT/shader-cache-conflicts"
for d in "$ROOT" "$ROOT/private" "$ROOT/resultats" "$ROOT/shader-cache" "$ROOT/shader-cache-conflicts"; do
  [[ ! -L "$d" ]] || { echo "DSR: unexpected private directory symlink" >&2; exit 1; }
  chmod 700 "$d"
done
if [[ ! -e "$ROOT/source" && ! -L "$ROOT/source" ]]; then
  ln -s "$SRC" "$ROOT/source"
fi
[[ -L "$ROOT/source" && "$(readlink -f "$ROOT/source")" == "$(readlink -f "$SRC")" ]] || {
  echo "DSR: unexpected source link" >&2; exit 1
}
if [[ ! -e "$ROOT/private/prod.keys" && ! -L "$ROOT/private/prod.keys" ]]; then
  install -m 600 -- "$SRC/prod.keys" "$ROOT/private/prod.keys"
fi
[[ -f "$ROOT/private/prod.keys" && ! -L "$ROOT/private/prod.keys" ]] || {
  echo "DSR: private keys must be a regular file" >&2; exit 1
}
cmp -s -- "$SRC/prod.keys" "$ROOT/private/prod.keys" || {
  echo "DSR: key mismatch; refusing to overwrite existing private copy" >&2; exit 1
}
chmod 600 "$ROOT/private/prod.keys"

echo "DSR: fixed-code diagnostics (no filenames or key bytes)"
SSH_ORIGINAL_COMMAND=dsr-diagnose-v1 python3 "$GATE"
if ! probe="$(SSH_ORIGINAL_COMMAND=dsr-probe-v1 python3 "$GATE")"; then
  echo "DSR: source package identities unrecognized; check the base .nsp and update .nsp (profile 1.0.3)" >&2
  exit 1
fi
[[ "$probe" == DSR_GATEWAY_V1 ]] || exit 1
manifest="$(SSH_ORIGINAL_COMMAND=dsr-manifest-v1 python3 "$GATE")"
read -r title version base_size update_size <<< "$manifest"
[[ "$title" == 01004AB00A260000 && "$version" == 196608 ]] || exit 1
[[ "$base_size" =~ ^[1-9][0-9]*$ && "$update_size" =~ ^[1-9][0-9]*$ ]] || exit 1
echo "DSR_GATEWAY_V1"
echo "DSR packages: base_bytes=$base_size update_bytes=$update_size"
echo "All results and shaders stay inside ~/portage-ipados/dark-souls-remastered/"
