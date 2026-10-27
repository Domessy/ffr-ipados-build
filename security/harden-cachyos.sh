#!/usr/bin/env bash
# Apply to CachyOS once before the next FFR build. Reversible.
set -euo pipefail

REPO="Domessy/ffr-ipados-build"
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
GATE="$ROOT/security/ffr_ssh_gate.py"
SSH_DIR="$HOME/.ssh"
AUTH="$SSH_DIR/authorized_keys"
OLDPUB="$SSH_DIR/ffr-gh-actions.pub"
NEWKEY="$SSH_DIR/ffr-gh-actions-restricted"
PUB="$NEWKEY.pub"
PRIVATE_LINK="$HOME/portage-ipados/ff-resonance/private/prod.keys"
NSP_DIR="$HOME/Documents/FF Resonance"

for command in python3 gh; do
  command -v "$command" >/dev/null 2>&1 || { echo "Missing: $command" >&2; exit 1; }
done
test -s "$OLDPUB" || { echo "Original FFR public key is missing: $OLDPUB" >&2; exit 1; }
if [[ ! -e "$NEWKEY" ]]; then
  ssh-keygen -q -t ed25519 -N '' -C 'ffr-github-actions-restricted' -f "$NEWKEY"
fi
chmod 600 "$NEWKEY"
test -s "$PUB" || { echo "New FFR public key is missing: $PUB" >&2; exit 1; }
test -s "$PRIVATE_LINK" || { echo "FFR prod.keys link/file missing: $PRIVATE_LINK" >&2; exit 1; }
test -s "$NSP_DIR/v-final_fantasy_resonance.nsp" || { echo "Base NSP missing" >&2; exit 1; }
test -s "$NSP_DIR/v-final_fantasy_resonance_v65536.nsp" || { echo "Update NSP missing" >&2; exit 1; }
test -s "$GATE" || { echo "Gateway script missing" >&2; exit 1; }

# Fail closed before touching the local SSH configuration.
gh variable set FFR_SECURITY_READY --body false --repo "$REPO"

mkdir -p "$SSH_DIR"
chmod 700 "$SSH_DIR"
touch "$AUTH"
chmod 600 "$AUTH"

# Verify that the local gateway itself accepts only the approved commands.
test "$(SSH_ORIGINAL_COMMAND=probe python3 "$GATE")" = "FFR_GATEWAY_OK"
if SSH_ORIGINAL_COMMAND='id' python3 "$GATE" >/dev/null 2>&1; then
  echo "Gateway validation failed: unexpected unrestricted command" >&2
  exit 1
fi

# Back up authorized_keys without changing other public keys.
BACKUP="$(mktemp "$SSH_DIR/authorized_keys.ffr-before-XXXXXXXX")"
cp -- "$AUTH" "$BACKUP"
chmod 600 "$BACKUP"

python3 - "$AUTH" "$PUB" "$OLDPUB" "$GATE" <<'PY'
import os
import pathlib
import re
import sys
import tempfile

auth, pubfile, oldpubfile, gate = map(pathlib.Path, sys.argv[1:])
oldkey_parts = oldpubfile.read_text(encoding="utf-8").strip().split()
if len(oldkey_parts) < 2 or oldkey_parts[0] != "ssh-ed25519":
    raise SystemExit("Invalid original FFR public key")
oldkey_blob = oldkey_parts[1]
key_parts = pubfile.read_text(encoding="utf-8").strip().split()
if len(key_parts) < 2 or key_parts[0] != "ssh-ed25519":
    raise SystemExit("Invalid dedicated ED25519 public key")
key_blob = key_parts[1]
if not re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", key_blob):
    raise SystemExit("Unexpected public key content")

# OpenSSH authorizes a forced command with a quoted path. Do not let a
# pathological path inject new authorized_keys options.
gate_path = str(gate.resolve(strict=True))
if not re.fullmatch(r"/[A-Za-z0-9_./-]+", gate_path):
    raise SystemExit("Unsupported local gateway path (special characters)")

old = auth.read_text(encoding="utf-8").splitlines()
# Remove every previous entry with this one specific key, including the
# initial unrestricted entry. Leave unrelated SSH keys untouched.
kept = [line for line in old
        if key_blob not in line.split() and oldkey_blob not in line.split()]
forced = f'/usr/bin/python3 {gate_path}'
new_key = (
    f'from="100.64.0.0/10",restrict,command="{forced}" '
    + " ".join(key_parts) + " # ffr-restricted"
)
kept.append(new_key)
fd, tmp = tempfile.mkstemp(prefix=".ffr-authorized-", dir=auth.parent)
try:
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(kept) + "\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, auth)
finally:
    if os.path.exists(tmp):
        os.unlink(tmp)
PY

# The workflow uses these secrets only as environment inputs; the public
# repository does not expose their values.
# Rotate the original general-purpose SSH key so its secret no longer grants access.
gh secret set FFR_SSH_KEY --repo "$REPO" < "$NEWKEY"
printf '%s' "$(id -un)" | gh secret set FFR_SSH_USER --repo "$REPO"
gh variable set FFR_SECURITY_READY --body true --repo "$REPO"

echo "Original FFR SSH key removed from authorized_keys and its GitHub secret rotated."
echo "FFR SSH restricted: 6 allowed operations only."
echo "Backup of previous authorized_keys: $BACKUP"
echo "No NSP or prod.keys was uploaded to GitHub."
echo "The next build is now authorized. No build has been launched."
