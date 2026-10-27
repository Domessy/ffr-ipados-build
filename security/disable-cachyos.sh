#!/usr/bin/env bash
# Disable FFR SSH access without affecting other SSH keys or game data.
set -euo pipefail
REPO="Domessy/ffr-ipados-build"
SSH_DIR="$HOME/.ssh"
AUTH="$SSH_DIR/authorized_keys"

# Disable future CI jobs before changing local access.
gh variable set FFR_SECURITY_READY --body false --repo "$REPO"

python3 - "$AUTH" "$SSH_DIR/ffr-gh-actions.pub" "$SSH_DIR/ffr-gh-actions-restricted.pub" <<'PY'
import os
from pathlib import Path
import sys
import tempfile

auth = Path(sys.argv[1])
if not auth.exists():
    raise SystemExit(0)
blobs = set()
for filename in sys.argv[2:]:
    file = Path(filename)
    if file.is_file():
        data = file.read_text(encoding="utf-8").strip().split()
        if len(data) >= 2:
            blobs.add(data[1])
current = auth.read_text(encoding="utf-8").splitlines()
kept = [line for line in current if not any(blob in line.split() for blob in blobs)]
fd, temporary = tempfile.mkstemp(prefix=".ffr-authorized-", dir=auth.parent)
try:
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write("\n".join(kept) + ("\n" if kept else ""))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, auth)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
PY

echo "FFR GitHub builds disabled and both FFR SSH public keys de-authorized."
echo "Other SSH keys, original NSP files and build results unchanged."
echo "Revoke the CI Tailscale auth key separately in Tailscale admin if finished."
