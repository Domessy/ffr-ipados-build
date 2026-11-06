#!/usr/bin/env python3
"""Production-workflow contracts; no secrets or game files required."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT/".github/workflows/build-oot2.yml"
REFERENCE = ROOT/".github/workflows/build-dread.yml"
REF = re.compile(r"\$\{\{\s*secrets\.([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
EXPECTED = {"FFR_TS_AUTHKEY","FFR_SSH_KEY","FFR_SSH_KNOWN_HOSTS",
            "FFR_TS_HOST","FFR_SSH_USER"}


class WorkflowContractTests(unittest.TestCase):
    def test_network_secret_names_match_working_dread(self):
        workflow=BUILD.read_text()
        known=REFERENCE.read_text()
        self.assertEqual(set(REF.findall(workflow)),EXPECTED)
        self.assertEqual(set(REF.findall(workflow)),set(REF.findall(known)))
        self.assertIn("TS_AUTHKEY: ${{ secrets.FFR_TS_AUTHKEY }}",workflow)
        self.assertIn('--authkey="$TS_AUTHKEY"',workflow)
        self.assertNotIn("AUTWONDEREY",workflow)

    def test_preflight_before_any_private_transfer(self):
        workflow=BUILD.read_text()
        check=workflow.index("Verifier les secrets reseau avant toute installation couteuse")
        install=workflow.index("Installer les dependances nxnative")
        network=workflow.index("Connecter Tailscale")
        meta=workflow.index("Verifier le NUP et la capacite disque")
        transfer=workflow.index("Transferer uniquement le NUP")
        self.assertTrue(check < install < network < meta < transfer)
        self.assertIn("OOT2_GATEWAY_V1",workflow)
        self.assertIn("required=$(( 2 * NUP_BYTES + 32 * 1024**3 ))",workflow)
        self.assertIn("source_bytes=$NUP_BYTES",workflow)

    def test_one_nup_without_keys(self):
        workflow=BUILD.read_text()
        self.assertIn("security/oot2_transfer.py nup",workflow)
        self.assertIn("security/oot2_nup_info.py",workflow)
        self.assertIn("OcarinaOfTime.nup",workflow)
        self.assertIn("security/run_oot2.py",workflow)
        for forbidden in ("oot2-read-keys","oot2-prod.keys","NSPS","FFR_TS_AUTWONDEREY"):
            self.assertNotIn(forbidden,workflow)

    def test_pin_and_metal_chain(self):
        workflow=BUILD.read_text()
        m=re.search(r'NXNATIVE_SHA="([^"]+)"',workflow)
        self.assertIsNotNone(m)
        self.assertRegex(m.group(1),r"^[0-9a-f]{40}$")
        self.assertEqual(m.group(1),"c229bd7d52e30f072362e31c7b1e3206d107d4cd")
        self.assertIn("Xcode 27.2",workflow)
        self.assertIn("Apple metal version 32023.922 (metalfe-32023.922.4)",workflow)
        self.assertIn("--check-metal",workflow)
        script=(ROOT/"security/run_oot2.py").read_text()
        self.assertIn('"--platform", "ios"',script)
        self.assertIn('"-p", "v131072"',script)
        self.assertIn('ZeldaOcarinaOfTime.ipa',script)
        self.assertNotIn('"--platform", "mac-app"',script)


if __name__=="__main__":
    unittest.main()
