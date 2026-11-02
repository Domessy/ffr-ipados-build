#!/usr/bin/env bash
# Reversible Mina the Hollower nxnative setup; never changes original NSP files.
set -euo pipefail
ROOT="$HOME/portage-ipados/mina-the-hollower"
SRC="$HOME/Documents/Mina the Hollower"
GATE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/ffr_ssh_gate.py"

# Linux directory names are case-sensitive. Accept only a unique case-variant
# of the exact expected title under ~/Documents; never search other locations.
if [[ ! -d "$SRC" && ! -L "$SRC" ]]; then
  matches=()
  while IFS= read -r -d '' candidate; do
    matches+=("$candidate")
  done < <(find "$HOME/Documents" -mindepth 1 -maxdepth 1 -type d \
    -iname 'mina the hollower' -print0)
  if (( ${#matches[@]} == 1 )); then
    SRC="${matches[0]}"
    echo "MINA: located the game folder using a case-insensitive exact-name match."
  fi
fi
if [[ ! -d "$SRC" || -L "$SRC" ]]; then
  echo "MINA: original game directory unavailable or symbolic link rejected." >&2
  echo "MINA: candidate directories (name only):" >&2
  find "$HOME/Documents" -mindepth 1 -maxdepth 1 -iname '*mina*hollower*' \
    -printf '  %f (%y)\n' >&2 || true
  exit 1
fi
[[ -s "$SRC/prod.keys" && -f "$SRC/prod.keys" && ! -L "$SRC/prod.keys" ]] || {
  echo "MINA: source prod.keys missing or not a regular file" >&2; exit 1
}
[[ ! -L "$ROOT" ]] || { echo "MINA: project root cannot be a symlink" >&2; exit 1; }
mkdir -p "$ROOT/private" "$ROOT/resultats" "$ROOT/shader-cache" "$ROOT/shader-cache-conflicts"
for d in "$ROOT" "$ROOT/private" "$ROOT/resultats" "$ROOT/shader-cache" "$ROOT/shader-cache-conflicts"; do
  [[ ! -L "$d" ]] || { echo "MINA: unexpected private directory symlink" >&2; exit 1; }
  chmod 700 "$d"
done
if [[ ! -e "$ROOT/source" && ! -L "$ROOT/source" ]]; then
  ln -s "$SRC" "$ROOT/source"
fi
[[ -L "$ROOT/source" && "$(readlink -f "$ROOT/source")" == "$(readlink -f "$SRC")" ]] || {
  echo "MINA: unexpected source link" >&2; exit 1
}
if [[ ! -e "$ROOT/private/prod.keys" && ! -L "$ROOT/private/prod.keys" ]]; then
  install -m 600 -- "$SRC/prod.keys" "$ROOT/private/prod.keys"
fi
[[ -f "$ROOT/private/prod.keys" && ! -L "$ROOT/private/prod.keys" ]] || {
  echo "MINA: private keys must be a regular file" >&2; exit 1
}
cmp -s -- "$SRC/prod.keys" "$ROOT/private/prod.keys" || {
  echo "MINA: key mismatch; refusing to overwrite existing private copy" >&2; exit 1
}
chmod 600 "$ROOT/private/prod.keys"

echo "MINA: fixed-code diagnostics (no filenames or key bytes)"
SSH_ORIGINAL_COMMAND=mina-diagnose-v1 python3 "$GATE"
if ! probe="$(SSH_ORIGINAL_COMMAND=mina-probe-v1 python3 "$GATE")"; then
  echo "MINA: source package identities unrecognized; check the NSP base/update filenames, headers and identifiers (no registered nxnative game profile)" >&2
  exit 1
fi
[[ "$probe" == MINA_GATEWAY_V1 ]] || exit 1
manifest="$(SSH_ORIGINAL_COMMAND=mina-manifest-v1 python3 "$GATE")"
read -r title version base_size update_size <<< "$manifest"
[[ "$title" == 0100DCD01F306000 && "$version" == unverified ]] || exit 1
[[ "$base_size" =~ ^[1-9][0-9]*$ && "$update_size" =~ ^[1-9][0-9]*$ ]] || exit 1
echo "MINA_GATEWAY_V1"
echo "MINA packages: base_bytes=$base_size update_bytes=$update_size"
echo "All results and shaders stay inside ~/portage-ipados/mina-the-hollower/"
