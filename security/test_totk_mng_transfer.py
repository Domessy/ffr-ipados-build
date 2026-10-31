#!/usr/bin/env python3
"""Synthetic byte-stream tests for TOTK transfers (no game or key materials)."""
import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from security import totk_mng_transfer as transfer


class FakeSSH:
    def __init__(self, payload, rc=0):
        self.reader, self.writer = os.pipe()
        os.write(self.writer, payload)
        os.close(self.writer)
        self.stdout = os.fdopen(self.reader, "rb", buffering=0)
        self.returncode = rc

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def terminate(self):
        self.returncode = -15

    def kill(self):
        self.returncode = -9


class TOTKTransferTests(unittest.TestCase):
    def test_full_stream_published_atomically(self):
        with tempfile.TemporaryDirectory() as root:
            target_dir = Path(root) / "totk-mng-nsp"
            target_dir.mkdir()
            target = target_dir / "base.nsp"
            with patch.dict(os.environ, {"RUNNER_TEMP": root}), \
                 patch.object(transfer.subprocess, "Popen",
                              return_value=FakeSSH(b"fourteen-bytes")), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                transfer.transfer("base", len(b"fourteen-bytes"), target)
            self.assertEqual(target.read_bytes(), b"fourteen-bytes")
            self.assertIn("100.0%", output.getvalue())
            self.assertNotIn(str(target), output.getvalue())
            self.assertFalse(list(target_dir.glob("*.partial")))

    def test_partial_stream_never_published(self):
        with tempfile.TemporaryDirectory() as root:
            target_dir = Path(root) / "totk-mng-nsp"
            target_dir.mkdir()
            target = target_dir / "update.nsp"
            with patch.dict(os.environ, {"RUNNER_TEMP": root}), \
                 patch.object(transfer.subprocess, "Popen",
                              return_value=FakeSSH(b"partial")), \
                 contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(ValueError):
                    transfer.transfer("update", 100, target)
            self.assertFalse(target.exists())
            self.assertFalse(list(target_dir.glob("*.partial")))

    def test_allowlist_blocks_unrecognized_route(self):
        with tempfile.TemporaryDirectory() as root:
            target_dir = Path(root) / "totk-mng-nsp"
            target_dir.mkdir()
            with patch.dict(os.environ, {"RUNNER_TEMP": root}):
                with self.assertRaises(ValueError):
                    transfer.transfer("exec", 10, target_dir / "base.nsp")


if __name__ == "__main__":
    unittest.main()
