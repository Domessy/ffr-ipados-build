#!/usr/bin/env python3
"""Synthetic contract tests for removing ONLY the verified runner NUP copy."""
import contextlib
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch as mock_patch

from security import oot2_patch_nup_release as patcher

FIXTURE = '''import os
import shutil
from pathlib import Path

class BuildError(ValueError):
    pass

def scan_nup(path, want=None):
    return None

def extract_aoc(nx, keys, repo, work, app, fam, logs):
    return None

def main(args=None):
    nup = Path(os.environ["OOT2_RELEASE_EPHEMERAL_NUP"])
    work = Path(os.environ["RUNNER_TEMP"])
    platform = "ios"
    app = 0x0400486024DEC000
    pkg_ver = "v131072"
    versions = [pkg_ver]
    nx = keys = repo = logs = None
    g = {"programs": ""}
    class Nup:
        def __init__(self): self.closed = False
        def close(self): self.closed = True
    reader = Nup()
    fam = {"base": None, "updates": [("v131072", True)],
           "dlc": [], "nup": reader}
    dirs = {pkg_ver: work / "oot2-work/extract/v131072"}
    def say(s): pass
    aoc = extract_aoc(nx, keys, repo, work, app, fam, logs)
    return reader.closed
'''


def src(temp):
    path = Path(temp) / "build_ipa_from_nsp.py"
    path.write_text(FIXTURE)
    return path


class RunnerNupReleaseTests(unittest.TestCase):
    def test_injection_is_syntax_valid_and_idempotency_guarded(self):
        with tempfile.TemporaryDirectory() as d:
            path = src(d)
            patcher.patch(path)
            content = path.read_text()
            self.assertEqual(content.count(patcher.MARKER), 1)
            self.assertIn('fam["nup"].close()', content)
            self.assertIn('candidate.unlink()', content)
            compile(content, str(path), "exec")
            with self.assertRaisesRegex(ValueError, "already_patched"):
                patcher.patch(path)

    def test_expected_runner_copy_unlinked_after_extraction(self):
        with tempfile.TemporaryDirectory() as d:
            temp = Path(d)
            nup = temp / "oot2-nup/OcarinaOfTime.nup"
            nup.parent.mkdir()
            with nup.open("wb") as f:
                f.truncate(25020741061)  # sparse synthetic input, no game bytes
            romfs = temp / "oot2-work/extract/v131072/RomFS.img"
            romfs.parent.mkdir(parents=True)
            romfs.write_bytes(b"synthetic RomFS image")
            path = src(d)
            patcher.patch(path)
            namespace = {"__name__": "oot2_fixture"}
            with mock_patch.dict(os.environ, {
                 "RUNNER_TEMP": str(temp),
                 "OOT2_RELEASE_EPHEMERAL_NUP": str(nup)}):
                exec(compile(path.read_text(), str(path), "exec"), namespace)
                self.assertTrue(namespace["main"]())
            self.assertFalse(nup.exists())
            self.assertTrue(romfs.is_file())

    def test_no_release_when_romfs_not_extracted(self):
        with tempfile.TemporaryDirectory() as d:
            temp = Path(d)
            nup = temp / "oot2-nup/OcarinaOfTime.nup"
            nup.parent.mkdir()
            with nup.open("wb") as f:
                f.truncate(25020741061)
            path = src(d)
            patcher.patch(path)
            namespace = {"__name__": "oot2_fixture"}
            with mock_patch.dict(os.environ, {
                 "RUNNER_TEMP": str(temp),
                 "OOT2_RELEASE_EPHEMERAL_NUP": str(nup)}):
                exec(compile(path.read_text(), str(path), "exec"), namespace)
                with self.assertRaisesRegex(ValueError, "safety conditions"):
                    namespace["main"]()
            self.assertTrue(nup.is_file())

    def test_unexpected_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            temp = Path(d)
            nup = temp / "oot2-nup/OcarinaOfTime.nup"
            nup.parent.mkdir()
            nup.write_bytes(b"not the expected size")
            romfs = temp / "oot2-work/extract/v131072/RomFS.img"
            romfs.parent.mkdir(parents=True)
            romfs.write_bytes(b"mock")
            path = src(d)
            patcher.patch(path)
            namespace = {"__name__": "oot2_fixture"}
            with mock_patch.dict(os.environ, {
                 "RUNNER_TEMP": str(temp),
                 "OOT2_RELEASE_EPHEMERAL_NUP": str(nup)}):
                exec(compile(path.read_text(), str(path), "exec"), namespace)
                with self.assertRaisesRegex(ValueError, "safety conditions"):
                    namespace["main"]()
            self.assertTrue(nup.exists())


if __name__ == "__main__":
    unittest.main()
