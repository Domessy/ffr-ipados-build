#!/usr/bin/env python3
"""Synthetic-only tests for encrypted NSP CNMT parsing; no actual game assets."""
import unittest
from security.mina_identify_update import validate_metadata, meta_rows

BASE = "content Application 0100dcd01f306000 0\n"
UPDATE = "content Patch 0100dcd01f306800 262144\n"


class MinaContentMetadataTests(unittest.TestCase):
    def test_real_update_version_is_selected(self):
        self.assertEqual(validate_metadata(BASE, UPDATE), 262144)

    def test_wrong_base_or_update_id_rejected(self):
        for base, update in (
            ("content Application 0100dcd01f306001 0\n", UPDATE),
            (BASE, "content Patch 0100dcd01f305800 262144\n"),
            (BASE, "content Patch 0100dcd01f306800 0\n"),
            (BASE, ""),
            (BASE, UPDATE + "content Patch 0100dcd01f306800 131072\n"),
            ("content Patch 0100dcd01f306800 262144\n", UPDATE),
        ):
            with self.subTest(base=base, update=update):
                with self.assertRaises(ValueError):
                    validate_metadata(base, update)

    def test_parser_ignores_untrusted_lines(self):
        self.assertEqual(meta_rows("debug text\n" + UPDATE), [("Patch", "0100DCD01F306800", 262144)])
        self.assertEqual(meta_rows("content Patch 0100dcd01f306800 262144 injected\n"), [])


class MinaPrivateInspectionTests(unittest.TestCase):
    """Private diagnostic regressions; no real NSP, key or .NET tool needed."""

    def test_nonzero_exit_raises_stage_and_retains_private_stderr(self):
        import subprocess
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from security.mina_identify_update import checked, InspectionError

        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "private.log"
            result = subprocess.CompletedProcess(
                ["synthetic"], 5, stdout="stdout sample", stderr="secret filename")
            with patch("security.mina_identify_update.subprocess.run", return_value=result):
                with self.assertRaises(InspectionError) as failure:
                    checked(["synthetic"], "base-contents", log, 10)
            self.assertEqual(failure.exception.stage, "base-contents")
            self.assertEqual(failure.exception.status, "exit-5")
            self.assertIn("secret filename", log.read_text())
            self.assertIn("stage=base-contents; exit_code=5", log.read_text())

    def test_success_returns_stdout_and_diagnostics_remain_private(self):
        import subprocess
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from security.mina_identify_update import checked

        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "private.log"
            result = subprocess.CompletedProcess(
                ["synthetic"], 0, stdout=BASE, stderr="")
            with patch("security.mina_identify_update.subprocess.run", return_value=result):
                self.assertEqual(checked(["synthetic"], "base-contents", log, 10), BASE)
            self.assertIn(BASE, log.read_text())

    def test_timeout_is_redacted_to_stage_and_status(self):
        import subprocess
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from security.mina_identify_update import checked, InspectionError

        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "private.log"
            with patch("security.mina_identify_update.subprocess.run",
                       side_effect=subprocess.TimeoutExpired("private-cmd", 5)):
                with self.assertRaises(InspectionError) as failure:
                    checked(["synthetic"], "update-contents", log, 5)
            self.assertEqual(failure.exception.stage, "update-contents")
            self.assertEqual(failure.exception.status, "timeout")
            self.assertIn("stage=update-contents; timeout", log.read_text())


if __name__ == "__main__":
    unittest.main()
