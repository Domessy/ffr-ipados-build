#!/usr/bin/env python3
"""Synthetic Silksong input-routing and CAS-isolation tests (no real game files)."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from security import ffr_ssh_gate as parent
from security import silksong_gateway as silksong


class SilksongGatewayTests(unittest.TestCase):
    def test_identify_two_nsp_by_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "game.nsp").write_bytes(b"b" * 100)
            (folder / "update.nsp").write_bytes(b"u" * 11)
            (folder / "prod.keys").write_bytes(b"test-only-placeholder")
            with patch.object(silksong, "SOURCE", folder), patch.object(silksong, "KEYS", folder / "prod.keys"):
                base, update = silksong.identify_inputs()
                self.assertEqual((base.name, update.name), ("game.nsp", "update.nsp"))
                self.assertEqual(silksong.dispatch("silksong-probe-v2", parent), 0)

    def test_refuses_other_input_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(silksong, "SOURCE", Path(tmp)):
                with self.assertRaises(ValueError):
                    silksong.identify_inputs()

    def test_private_silksong_keys_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            key = folder / "prod.keys"
            key.write_bytes(b"test-only-placeholder")
            with patch.object(silksong, "SOURCE", folder), patch.object(silksong, "KEYS", key):
                self.assertEqual(silksong.identify_keys(), key)
                with patch.object(parent, "send_file") as sender:
                    self.assertEqual(silksong.dispatch("silksong-read-keys", parent), 0)
                    sender.assert_called_once_with(key)
                key.unlink()
                with self.assertRaises(ValueError):
                    silksong.identify_keys()
                other = folder / "external.keys"
                other.write_bytes(b"fake")
                key.symlink_to(other)
                with self.assertRaises(ValueError):
                    silksong.identify_keys()

    def test_cache_paths_do_not_leak_into_ffr(self):
        with tempfile.TemporaryDirectory() as tmp:
            prior = (parent.CACHE, parent.CONFLICTS, parent.OUTPUT)
            base = Path(tmp)
            with patch.object(silksong, "CACHE", base / "silk-cas"):
                with patch.object(silksong, "CONFLICTS", base / "silk-conflicts"):
                    with patch.object(silksong, "OUTPUT", base / "results"):
                        observed = []

                        def inspect_cache_path():
                            observed.append((parent.CACHE, parent.CONFLICTS, parent.OUTPUT))

                        with patch.object(parent, "read_cache", side_effect=inspect_cache_path) as read:
                            self.assertEqual(silksong.dispatch("silksong-read-cache", parent), 0)
                            read.assert_called_once()
                        self.assertEqual(observed, [(
                            base / "silk-cas",
                            base / "silk-conflicts",
                            base / "results",
                        )])
            # The gateway deliberately restores all FFR paths after dispatch.
            self.assertEqual((parent.CACHE, parent.CONFLICTS, parent.OUTPUT), prior)


if __name__ == "__main__":
    unittest.main()
