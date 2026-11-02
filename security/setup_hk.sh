#!/usr/bin/env bash
# Reversible Hollow Knight nxnative setup; never changes original NSP files.
set -euo pipefail
ROOT="$HOME/portage-ipados/hollow-knight"
SRC="$HOME/Documents/Hollow Knight"
GATE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/ffr_ssh_gate.py"

# Linux directory names are case-sensitive. Accept only a unique case-variant
# of the exact expected title under ~/Documents; never search other locations.
if [[ ! -d "$SRC" && ! -L "$SRC" ]]; then
  matches=()
  while IFS= read -r -d '' candidate; do
    matches+=("$candidate")
  done < <(find "$HOME/Documents" -mindepth 1 -maxdepth 1 -type d \
    -iname 'hollow knight' -print0)
  if (( ${#matches[@]} == 1 )); then
    SRC="${matches[0]}"
    echo "HK: located the game folder using a case-insensitive exact-name match."
  fi
fi
if [[ ! -d "$SRC" || -L "$SRC" ]]; then
  echo "HK: original game directory unavailable or symbolic link rejected." >&2
  echo "HK: candidate directories (name only):" >&2
  find "$HOME/Documents" -mindepth 1 -maxdepth 1 -iname '*hollow*knight*' \
    -printf '  %f (%y)\n' >&2 || true
  exit 1
fi
[[ -s "$SRC/prod.keys" && -f "$SRC/prod.keys" && ! -L "$SRC/prod.keys" ]] || {
  echo "HK: source prod.keys missing or not a regular file" >&2; exit 1
}
[[ ! -L "$ROOT" ]] || { echo "HK: project root cannot be a symlink" >&2; exit 1; }
mkdir -p "$ROOT/private" "$ROOT/resultats" "$ROOT/shader-cache" "$ROOT/shader-cache-conflicts"
for d in "$ROOT" "$ROOT/private" "$ROOT/resultats" "$ROOT/shader-cache" "$ROOT/shader-cache-conflicts"; do
  [[ ! -L "$d" ]] || { echo "HK: unexpected private directory symlink" >&2; exit 1; }
  chmod 700 "$d"
done
if [[ ! -e "$ROOT/source" && ! -L "$ROOT/source" ]]; then
  ln -s "$SRC" "$ROOT/source"
fi
[[ -L "$ROOT/source" && "$(readlink -f "$ROOT/source")" == "$(readlink -f "$SRC")" ]] || {
  echo "HK: unexpected source link" >&2; exit 1
}
if [[ ! -e "$ROOT/private/prod.keys" && ! -L "$ROOT/private/prod.keys" ]]; then
  install -m 600 -- "$SRC/prod.keys" "$ROOT/private/prod.keys"
fi
[[ -f "$ROOT/private/prod.keys" && ! -L "$ROOT/private/prod.keys" ]] || {
  echo "HK: private keys must be a regular file" >&2; exit 1
}
cmp -s -- "$SRC/prod.keys" "$ROOT/private/prod.keys" || {
  echo "HK: key mismatch; refusing to overwrite existing private copy" >&2; exit 1
}
chmod 600 "$ROOT/private/prod.keys"

echo "HK: fixed-code diagnostics (no filenames or key bytes)"
SSH_ORIGINAL_COMMAND=hk-diagnose-v2 python3 "$GATE"
if ! probe="$(SSH_ORIGINAL_COMMAND=hk-probe-v1 python3 "$GATE")"; then
  echo "HK: source validation failed; inspect HK_DIAG_V2 reason above." >&2
  echo "HK: local game files (names/sizes only; no keys or file contents):" >&2
  find "$SRC" -mindepth 1 -maxdepth 2 -type f \
    \( -iname '*.nsp' -o -iname '*.xci' -o -iname '*.nsz' \) \
    -printf '  %P (%s bytes)\n' >&2 || true
  echo "HK: originals unchanged. Resolve the source layout before starting GitHub Actions." >&2
  exit 1
fi
[[ "$probe" == HK_GATEWAY_V1 ]] || exit 1
manifest="$(SSH_ORIGINAL_COMMAND=hk-manifest-v1 python3 "$GATE")"
read -r title version base_size update_size <<< "$manifest"
[[ "$title" == 0100633007D48000 && "$version" == unverified ]] || exit 1
[[ "$base_size" =~ ^[1-9][0-9]*$ && "$update_size" =~ ^[1-9][0-9]*$ ]] || exit 1
echo "HK_GATEWAY_V1"
echo "HK packages: base_bytes=$base_size update_bytes=$update_size"
echo "All results and shaders stay inside ~/portage-ipados/hollow-knight/"
