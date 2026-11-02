#!/usr/bin/env python3
"""Synthetic-only tests for encrypted NSP CNMT parsing; no actual game assets."""
import unittest
from security.dread_identify_update import validate_metadata, meta_rows

BASE = "content Application 010093801237c000 0\n"
UPDATE = "content Patch 010093801237c800 327680\n"


class MetroidContentMetadataTests(unittest.TestCase):
    def test_real_update_version_is_selected(self):
        self.assertEqual(validate_metadata(BASE, UPDATE), 327680)

    def test_wrong_base_or_update_id_rejected(self):
        for base, update in (
            ("content Application 010093801237c001 0\n", UPDATE),
            (BASE, "content Patch 010093801237b800 327680\n"),
            (BASE, "content Patch 010093801237c800 0\n"),
            (BASE, "content Patch 010093801237c800 196608\n"),
            (BASE, ""),
            (BASE, UPDATE + "content Patch 010093801237c800 327680\n"),
            ("content Patch 010093801237c800 327680\n", UPDATE),
        ):
            with self.subTest(base=base, update=update):
                with self.assertRaises(ValueError):
                    validate_metadata(base, update)

    def test_parser_ignores_untrusted_lines(self):
        self.assertEqual(meta_rows("debug text\n" + UPDATE), [("Patch", "010093801237C800", 327680)])
        self.assertEqual(meta_rows("content Patch 010093801237c800 327680 injected\n"), [])


class MetroidPrivateInspectionTests(unittest.TestCase):
    """Private diagnostic regressions; no real NSP, key or .NET tool needed."""

    def test_nonzero_exit_raises_stage_and_retains_private_stderr(self):
        import subprocess
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from security.dread_identify_update import checked, InspectionError

        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "private.log"
            result = subprocess.CompletedProcess(
                ["synthetic"], 5, stdout="stdout sample", stderr="secret filename")
            with patch("security.dread_identify_update.subprocess.run", return_value=result):
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
        from security.dread_identify_update import checked

        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "private.log"
            result = subprocess.CompletedProcess(
                ["synthetic"], 0, stdout=BASE, stderr="")
            with patch("security.dread_identify_update.subprocess.run", return_value=result):
                self.assertEqual(checked(["synthetic"], "base-contents", log, 10), BASE)
            self.assertIn(BASE, log.read_text())

    def test_timeout_is_redacted_to_stage_and_status(self):
        import subprocess
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from security.dread_identify_update import checked, InspectionError

        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "private.log"
            with patch("security.dread_identify_update.subprocess.run",
                       side_effect=subprocess.TimeoutExpired("private-cmd", 5)):
                with self.assertRaises(InspectionError) as failure:
                    checked(["synthetic"], "update-contents", log, 5)
            self.assertEqual(failure.exception.stage, "update-contents")
            self.assertEqual(failure.exception.status, "timeout")
            self.assertIn("stage=update-contents; timeout", log.read_text())


class MetroidDotnetHostRegressionTests(unittest.TestCase):
    def test_inspector_runs_managed_dll_via_dotnet_not_standalone_apphost(self):
        import os
        from contextlib import redirect_stdout
        from io import StringIO
        from pathlib import Path
        import tempfile
        from unittest.mock import patch
        from security import dread_identify_update as mod

        with tempfile.TemporaryDirectory() as home:
            temp = Path(home)
            pkg = temp / "dread-nsp"
            pkg.mkdir()
            base = pkg / f"Metroid Dread [{mod.TITLE}][v0].xci"
            update = pkg / f"Metroid Dread update [{mod.UPDATE}].nsp"
            base.write_bytes(b"\\0" * 0x100 + b"HEAD")
            update.write_bytes(b"PFS0")
            (temp / "dread-prod.keys").write_text("synthetic - no actual keys")
            upstream = temp / "nxnative/dm/tools/nx_extract"
            upstream.mkdir(parents=True)
            (upstream / "nx_extract.csproj").write_text("<Project/>")

            invocations = []

            def fake_checked(command, stage, log_path, timeout):
                invocations.append((command, stage))
                if stage == "build-inspector":
                    (temp / "dread-nsp-inspection/nx_extract.dll").write_bytes(b"synthetic")
                    return ""
                if stage == "base-contents":
                    return BASE
                if stage == "update-contents":
                    return UPDATE
                self.fail(f"unexpected stage: {stage}")

            fake_console = StringIO()
            # Avoid printing a fake "CNMT verified; v327680" in the real
            # GitHub Actions build log during this synthetic unit test.
            with patch.dict(os.environ, {"RUNNER_TEMP": str(temp)}), \
                 patch.object(mod, "checked", side_effect=fake_checked), \
                 redirect_stdout(fake_console):
                mod.main()
            self.assertIn("patch v327680", fake_console.getvalue())

            self.assertEqual([stage for _, stage in invocations],
                             ["build-inspector", "base-contents", "update-contents"])
            # On macOS, /var resolves to /private/var. The runner resolves
            # RUNNER_TEMP, so compare canonical paths rather than spellings.
            managed_path = (temp / "dread-nsp-inspection/nx_extract.dll").resolve(strict=True)
            for command, _ in invocations[1:]:
                self.assertEqual(command[0], "dotnet")
                self.assertEqual(Path(command[1]).resolve(strict=True), managed_path)
                self.assertEqual(command[3], "--contents")
            self.assertFalse(update.exists())
            self.assertTrue((pkg / f"Metroid Dread update [{mod.UPDATE}][v327680].nsp").exists())
            self.assertTrue((temp / "dread-inspection.log").exists())


class MetroidCanonicalPathsTest(unittest.TestCase):
    def test_symlink_and_realpath_denote_identical_dll(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            real = root / "real"
            real.mkdir()
            dll = real / "nx_extract.dll"
            dll.write_bytes(b"synthetic")
            alias = root / "alias"
            alias.symlink_to(real, target_is_directory=True)
            # A structural regression for macOS /var -> /private/var.
            self.assertEqual((alias / "nx_extract.dll").resolve(strict=True),
                             dll.resolve(strict=True))


if __name__ == "__main__":
    unittest.main()
