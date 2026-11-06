#!/usr/bin/env python3
"""Synthetic tests for SSH transfer progress, atomicity, and strict output paths."""
import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from security import oot2_transfer as transfer


class DummySSH:
    def __init__(self, data, returncode=0):
        read_fd, write_fd = os.pipe()
        os.write(write_fd, data)
        os.close(write_fd)
        self.stdout = os.fdopen(read_fd, "rb", buffering=0)
        self.returncode = returncode

    def wait(self, timeout=None):
        return self.returncode

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = -15

    def kill(self):
        self.returncode = -9


class OOT2TransferTests(unittest.TestCase):
    def setup_folder(self, root):
        parent = Path(root) / "oot2-nup"
        parent.mkdir()
        return parent

    def test_success_atomic_and_numeric_log(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = self.setup_folder(temp)
            dest = folder / "OcarinaOfTime.nup"
            data = b"NSP-test-payload"
            output = io.StringIO()
            with patch.dict(os.environ, {"RUNNER_TEMP": temp}), \
                 patch.object(transfer.subprocess, "Popen",
                              return_value=DummySSH(data)) as open_ssh, \
                 contextlib.redirect_stdout(output):
                transfer.transfer("nup", len(data), dest)
            self.assertEqual(dest.read_bytes(), data)
            self.assertEqual(list(folder.glob("*.partial")), [])
            self.assertIn("OOT2 nup:", output.getvalue())
            self.assertIn("100.0%", output.getvalue())
            self.assertIn("verified complete", output.getvalue())
            self.assertNotIn(str(dest), output.getvalue())
            self.assertEqual(open_ssh.call_args.args[0][-1], "oot2-read-nup")

    def test_update_route_is_independent(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = self.setup_folder(temp)
            dest = folder / "OcarinaOfTime.nup"
            with patch.dict(os.environ, {"RUNNER_TEMP": temp}), \
                 patch.object(transfer.subprocess, "Popen", return_value=DummySSH(b"nup")), \
                 contextlib.redirect_stdout(io.StringIO()):
                transfer.transfer("nup", 3, dest)
            self.assertEqual(dest.read_bytes(), b"nup")

    def test_mismatch_never_publishes_partial_file(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = self.setup_folder(temp)
            dest = folder / "OcarinaOfTime.nup"
            with patch.dict(os.environ, {"RUNNER_TEMP": temp}), \
                 patch.object(transfer.subprocess, "Popen",
                              return_value=DummySSH(b"underfilled")), \
                 contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(ValueError):
                    transfer.transfer("nup", 500, dest)
            self.assertFalse(dest.exists())
            self.assertEqual(list(folder.glob("*.partial")), [])

    def test_nonzero_ssh_never_publishes_file(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = self.setup_folder(temp)
            dest = folder / "OcarinaOfTime.nup"
            with patch.dict(os.environ, {"RUNNER_TEMP": temp}), \
                 patch.object(transfer.subprocess, "Popen",
                              return_value=DummySSH(b"data", returncode=255)), \
                 contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(RuntimeError):
                    transfer.transfer("nup", 4, dest)
            self.assertFalse(dest.exists())

    def test_reject_external_output_and_unknown_role(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = self.setup_folder(temp)
            with patch.dict(os.environ, {"RUNNER_TEMP": temp}):
                with self.assertRaises(ValueError):
                    transfer.transfer("nup", 3, Path(temp) / "outside.nup")
                with self.assertRaises(ValueError):
                    transfer.transfer("keys", 3, folder / "keys.nup")
                with self.assertRaises(ValueError):
                    transfer.transfer("nup", 0, folder / "OcarinaOfTime.nup")

    def test_reject_wrong_destination_extension(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = self.setup_folder(temp)
            with patch.dict(os.environ, {"RUNNER_TEMP": temp}):
                with self.assertRaisesRegex(ValueError, "filename"):
                    transfer.transfer("nup", 5, folder / "bad.nsp")

    def test_progress_numeric_and_finite_at_start(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            transfer.status("nup", 0, 100, 1.0, 1.0, 0, 1.0)
        self.assertIn("0.0%", output.getvalue())
        self.assertIn("ETA n/a", output.getvalue())


if __name__ == "__main__":
    unittest.main()
