#!/usr/bin/env python3
"""Non-sensitive, synthetic unit tests for the forced-command CAS importer."""
import contextlib
import io
from pathlib import Path
import tarfile
import tempfile
import types
import unittest
from unittest.mock import patch

from security import ffr_ssh_gate as gateway


def make_archive(relative_path, payload):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w:gz") as archive:
        info = tarfile.TarInfo(relative_path)
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    return data.getvalue()


class CacheImporterTests(unittest.TestCase):
    def test_same_shader_can_be_reimported_but_not_replaced(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            cache = base / "shader-cache"
            conflicts = base / "shader-cache-conflicts"
            rel = "shader/a1b2/ios/example_b.metallib"
            dest = cache / rel
            saved = []
            with patch.object(gateway, "CACHE", cache), patch.object(gateway, "CONFLICTS", conflicts):
                for payload in (b"first-version", b"first-version", b"different-version"):
                    inp = types.SimpleNamespace(buffer=io.BytesIO(make_archive(rel, payload)))
                    out = io.StringIO()
                    with patch.object(gateway.sys, "stdin", inp), contextlib.redirect_stdout(out):
                        gateway.write_cache()
                    saved.append(out.getvalue().strip())
                    self.assertEqual(dest.read_bytes(), b"first-version")

            self.assertIn("FFR_CACHE_NEW=1", saved[0])
            self.assertIn("FFR_CACHE_REUSED=1", saved[1])
            self.assertIn("FFR_CACHE_CONFLICTS=1", saved[2])
            self.assertEqual(len(list(conflicts.rglob("*.conflict"))), 1)
            self.assertEqual(next(conflicts.rglob("*.conflict")).read_bytes(), b"different-version")

    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.object(gateway, "CACHE", Path(root) / "cache"):
                inp = types.SimpleNamespace(
                    buffer=io.BytesIO(make_archive("shader/../../private", b"no"))
                )
                with patch.object(gateway.sys, "stdin", inp):
                    with self.assertRaises(ValueError):
                        gateway.write_cache()


if __name__ == "__main__":
    unittest.main()
