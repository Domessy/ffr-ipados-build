#!/usr/bin/env python3
"""Synthetic checks for Wonder's 1.2.0 profile derivation; no retail assets."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

# GitHub Actions already sets these. Supply harmless values for local tests.
with patch.dict(os.environ, {
    "RUNNER_TEMP": os.environ.get("RUNNER_TEMP", "/tmp"),
    "GITHUB_WORKSPACE": os.environ.get("GITHUB_WORKSPACE", "/tmp"),
}):
    from security import run_wonder as app


class WonderDerivedProfileTests(unittest.TestCase):
    def test_verified_revision_selects_user_version_not_registered_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            filename = Path(folder) / "version"
            filename.write_text("262144\n")
            with patch.object(app, "VERIFIED_PATCH", filename):
                self.assertEqual(app.read_verified_patch(), 262144)
                filename.write_text("196608\n")
                self.assertEqual(app.read_verified_patch(), 196608)
            for untrusted in ("327680\n", "65536\n", "0\n", "v262144\n", "../262144\n", ""):
                filename.write_text(untrusted)
                with patch.object(app, "VERIFIED_PATCH", filename):
                    with self.assertRaises(ValueError):
                        app.read_verified_patch()

    def test_only_requested_nacp_display_version_is_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            filename = Path(folder) / "private.log"
            for v in ("1.2.0", "1.2.1", "1.1.0"):
                filename.write_text(
                    "[14:01] app name: Super Mario Bros. Wonder; "
                    "version: " + v + "; bundle ID: org.nxnative.010015100b514000\n")
                with patch.object(app, "LOG", filename):
                    self.assertEqual(app.confirmed_display_version(), v)
            filename.write_text("app name: Other; version: 1.2.0; "
                                "bundle ID: org.nxnative.0100deadbeef0000\n")
            with patch.object(app, "LOG", filename):
                self.assertIsNone(app.confirmed_display_version())

    def test_missing_verified_update_stops_before_any_subprocess(self):
        with tempfile.TemporaryDirectory() as folder:
            missing = Path(folder) / "nonexistent"
            with patch.object(app, "VERIFIED_PATCH", missing), \
                 patch.object(app, "CACHE", Path(folder) / "cache"), \
                 patch.object(app, "LOG", Path(folder) / "log"), \
                 patch.object(app.subprocess, "Popen") as start:
                self.assertNotEqual(app.compile_ipa(), 0)
                start.assert_not_called()


if __name__ == "__main__":
    unittest.main()
