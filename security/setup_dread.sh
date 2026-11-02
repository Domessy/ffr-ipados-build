#!/usr/bin/env bash
# Reversible Metroid Dread nxnative setup; never changes original NSP files.
set -euo pipefail
ROOT="$HOME/portage-ipados/metroid-dread"
SRC="$HOME/Documents/Metroid Dread"
GATE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/ffr_ssh_gate.py"

# Linux directory names are case-sensitive. Accept only a unique case-variant
# of the exact expected title under ~/Documents; never search other locations.
if [[ ! -d "$SRC" && ! -L "$SRC" ]]; then
  matches=()
  while IFS= read -r -d '' candidate; do
    matches+=("$candidate")
  done < <(find "$HOME/Documents" -mindepth 1 -maxdepth 1 -type d \
    -iname 'metroid dread' -print0)
  if (( ${#matches[@]} == 1 )); then
    SRC="${matches[0]}"
    echo "DREAD: located the game folder using a case-insensitive exact-name match."
  fi
fi
if [[ ! -d "$SRC" || -L "$SRC" ]]; then
  echo "DREAD: original game directory unavailable or symbolic link rejected." >&2
  echo "DREAD: candidate directories (name only):" >&2
  find "$HOME/Documents" -mindepth 1 -maxdepth 1 -iname '*metroid*dread*' \
    -printf '  %f (%y)\n' >&2 || true
  exit 1
fi
[[ -s "$SRC/prod.keys" && -f "$SRC/prod.keys" && ! -L "$SRC/prod.keys" ]] || {
  echo "DREAD: source prod.keys missing or not a regular file" >&2; exit 1
}
[[ ! -L "$ROOT" ]] || { echo "DREAD: project root cannot be a symlink" >&2; exit 1; }
mkdir -p "$ROOT/private" "$ROOT/resultats" "$ROOT/shader-cache" "$ROOT/shader-cache-conflicts"
for d in "$ROOT" "$ROOT/private" "$ROOT/resultats" "$ROOT/shader-cache" "$ROOT/shader-cache-conflicts"; do
  [[ ! -L "$d" ]] || { echo "DREAD: unexpected private directory symlink" >&2; exit 1; }
  chmod 700 "$d"
done
if [[ ! -e "$ROOT/source" && ! -L "$ROOT/source" ]]; then
  ln -s "$SRC" "$ROOT/source"
fi
[[ -L "$ROOT/source" && "$(readlink -f "$ROOT/source")" == "$(readlink -f "$SRC")" ]] || {
  echo "DREAD: unexpected source link" >&2; exit 1
}
if [[ ! -e "$ROOT/private/prod.keys" && ! -L "$ROOT/private/prod.keys" ]]; then
  install -m 600 -- "$SRC/prod.keys" "$ROOT/private/prod.keys"
fi
[[ -f "$ROOT/private/prod.keys" && ! -L "$ROOT/private/prod.keys" ]] || {
  echo "DREAD: private keys must be a regular file" >&2; exit 1
}
cmp -s -- "$SRC/prod.keys" "$ROOT/private/prod.keys" || {
  echo "DREAD: key mismatch; refusing to overwrite existing private copy" >&2; exit 1
}
chmod 600 "$ROOT/private/prod.keys"

echo "DREAD: fixed-code diagnostics with package counts (no filenames or key bytes)"
SSH_ORIGINAL_COMMAND=dread-diagnose-v3 python3 "$GATE"
if ! probe="$(SSH_ORIGINAL_COMMAND=dread-probe-v1 python3 "$GATE")"; then
  echo "DREAD: source validation failed; see DREAD_DIAG_V3 counts above." >&2
  echo "DREAD: local package inventory (names/sizes only, no keys or content):" >&2
  find "$SRC" -mindepth 1 -maxdepth 2 -type f \
    \\( -iname '*.nsp' -o -iname '*.nsz' -o -iname '*.xci' -o -iname '*.xcz' \\) \
    -printf '  %P (%s bytes)\\n' >&2 || true
  echo "DREAD: no source files were changed. Resolve source layout before a new GitHub build." >&2
  exit 1
fi
[[ "$probe" == DREAD_GATEWAY_V1 ]] || exit 1
manifest="$(SSH_ORIGINAL_COMMAND=dread-manifest-v1 python3 "$GATE")"
read -r title version base_size update_size <<< "$manifest"
[[ "$title" == 010093801237C000 && "$version" == unverified ]] || exit 1
[[ "$base_size" =~ ^[1-9][0-9]*$ && "$update_size" =~ ^[1-9][0-9]*$ ]] || exit 1
echo "DREAD_GATEWAY_V1"
echo "DREAD packages: base_bytes=$base_size update_bytes=$update_size"
echo "All results and shaders stay inside ~/portage-ipados/metroid-dread/"
