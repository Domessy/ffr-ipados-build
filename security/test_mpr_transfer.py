#!/usr/bin/env python3
"""Synthetic tests for SSH transfer progress, atomicity, and strict output paths."""
import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from security import mpr_transfer as transfer


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


class MPRTransferTests(unittest.TestCase):
    def setup_folder(self, root):
        parent = Path(root) / "mpr-nsp"
        parent.mkdir()
        return parent

    def test_success_atomic_and_numeric_log(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = self.setup_folder(temp)
            dest = folder / "MPR [01007EF00011E000][v0].nsp"
            data = b"NSP-test-payload"
            output = io.StringIO()
            with patch.dict(os.environ, {"RUNNER_TEMP": temp}), \
                 patch.object(transfer.subprocess, "Popen",
                              return_value=DummySSH(data)) as open_ssh, \
                 contextlib.redirect_stdout(output):
                transfer.transfer("base", len(data), dest)
            self.assertEqual(dest.read_bytes(), data)
            self.assertEqual(list(folder.glob("*.partial")), [])
            self.assertIn("MPR base:", output.getvalue())
            self.assertIn("100.0%", output.getvalue())
            self.assertIn("verified complete", output.getvalue())
            self.assertNotIn(str(dest), output.getvalue())
            self.assertEqual(open_ssh.call_args.args[0][-1], "mpr-read-base")

    def test_mismatch_never_publishes_partial_file(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = self.setup_folder(temp)
            dest = folder / "MPR [01007EF00011E800][v1114112].nsp"
            with patch.dict(os.environ, {"RUNNER_TEMP": temp}), \
                 patch.object(transfer.subprocess, "Popen",
                              return_value=DummySSH(b"underfilled")), \
                 contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(ValueError):
                    transfer.transfer("base", 500, dest)
            self.assertFalse(dest.exists())
            self.assertEqual(list(folder.glob("*.partial")), [])

    def test_nonzero_ssh_never_publishes_file(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = self.setup_folder(temp)
            dest = folder / "MPR [01007EF00011F001][v196608].nsp"
            with patch.dict(os.environ, {"RUNNER_TEMP": temp}), \
                 patch.object(transfer.subprocess, "Popen",
                              return_value=DummySSH(b"data", returncode=255)), \
                 contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(RuntimeError):
                    transfer.transfer("base", 4, dest)
            self.assertFalse(dest.exists())

    def test_reject_external_output_and_unknown_role(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = self.setup_folder(temp)
            with patch.dict(os.environ, {"RUNNER_TEMP": temp}):
                with self.assertRaises(ValueError):
                    transfer.transfer("base", 3, Path(temp) / "outside.nsp")
                with self.assertRaises(ValueError):
                    transfer.transfer("keys", 3, folder / "keys.nsp")
                with self.assertRaises(ValueError):
                    transfer.transfer("base", 0, folder / "base.nsp")

    def test_progress_numeric_and_finite_at_start(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            transfer.status("base", 0, 100, 1.0, 1.0, 0, 1.0)
        self.assertIn("0.0%", output.getvalue())
        self.assertIn("ETA n/a", output.getvalue())


if __name__ == "__main__":
    unittest.main()
