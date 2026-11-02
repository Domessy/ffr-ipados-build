#!/usr/bin/env python3
"""Synthetic contract checks for Wonder Actions. No secret values or game data."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent
WONDER = ROOT / ".github/workflows/build-wonder.yml"
DREAD = ROOT / ".github/workflows/build-dread.yml"
EXPECTED = {
    "FFR_TS_AUTHKEY", "FFR_SSH_KEY", "FFR_SSH_KNOWN_HOSTS",
    "FFR_TS_HOST", "FFR_SSH_USER",
}
REF = re.compile(r"\$\{\{\s*secrets\.([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
ENV = re.compile(r"(?m)^\s*([A-Z_]+):\s+\$\{\{\s*secrets\.([A-Z_][A-Z0-9_]*)\s*\}\}")


class WonderWorkflowContracts(unittest.TestCase):
    def test_secret_names_match_known_working_dread_pipeline(self):
        wonder = WONDER.read_text()
        dread = DREAD.read_text()
        self.assertEqual(set(REF.findall(wonder)), EXPECTED)
        self.assertEqual(set(REF.findall(wonder)), set(REF.findall(dread)))
        self.assertNotIn("AUTWONDEREY", wonder)

    def test_tailscale_auth_var_and_private_inputs(self):
        workflow = WONDER.read_text()
        bindings = ENV.findall(workflow)
        for mapping in (
            ("TS_AUTHKEY", "FFR_TS_AUTHKEY"),
            ("SSH_KEY", "FFR_SSH_KEY"),
            ("SSH_KNOWN_HOSTS", "FFR_SSH_KNOWN_HOSTS"),
            ("TS_HOST", "FFR_TS_HOST"),
            ("SSH_USER", "FFR_SSH_USER"),
        ):
            self.assertIn(mapping, bindings)
        self.assertIn('test -n "$TS_AUTHKEY"', workflow)
        self.assertIn('--authkey="$TS_AUTHKEY"', workflow)
        self.assertIn("--accept-dns=false", workflow)
        self.assertNotIn('echo "$TS_AUTHKEY"', workflow)

    def test_fail_fast_precedes_xcode_and_brew(self):
        workflow = WONDER.read_text()
        early = workflow.index("Verifier les secrets reseau avant toute installation couteuse")
        self.assertLess(early, workflow.index("Selectionner Xcode 27.2"))
        self.assertLess(early, workflow.index("Installer les dependances nxnative"))
        self.assertLess(early, workflow.index("Connecter Tailscale"))
        self.assertIn('if [ -z "', workflow)
        self.assertIn('missing required network secret:', workflow)

    def test_game_paths_and_sha_remain_consistent(self):
        workflow = WONDER.read_text()
        self.assertIn("Super Mario Bros. Wonder [010015100B514000][v0].xci", workflow)
        self.assertIn("Super Mario Bros. Wonder update [010015100B514800].nsp", workflow)
        self.assertIn("security/run_wonder.py", workflow)
        self.assertIn("security/wonder_identify_update.py", workflow)
        for foreign in ("security/run_hk.py", "security/setup_hk.sh",
                        "security/run_dread.py", "security/setup_dread.sh"):
            self.assertNotIn(foreign, workflow)
        pin = re.search(r'NXNATIVE_SHA="([^"]+)"', workflow)
        self.assertIsNotNone(pin)
        self.assertRegex(pin.group(1), r"^[0-9a-f]{40}$")
        self.assertEqual(pin.group(1), "65501fbbaf8526f7aab0a1edd028135888590f8e")


if __name__ == "__main__":
    unittest.main()
