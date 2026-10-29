#!/usr/bin/env python3
"""Offline tests for Tales' restricted source handling and cache isolation."""
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

from security import ffr_ssh_gate as parent
from security import tales_gateway as tales

GAME = 0x0100300012345000


class TalesGatewayTests(unittest.TestCase):
    def make_inputs(self, folder):
        base = folder / f"Tales [{GAME:016X}][v0].nsp"
        update = folder / f"Tales [{GAME + 0x800:016X}][v131072].nsp"
        base.write_bytes(b"PFS0-game-placeholder")
        update.write_bytes(b"PFS0-update-placeholder")
        keys = folder / "prod.keys"
        keys.write_bytes(b"fake-test-keys-not-a-real-secret")
        return base, update, keys

    def test_valid_pair_and_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            base, update, keys = self.make_inputs(folder)
            with patch.object(tales, "local_source", return_value=folder):
                self.assertEqual(tales.identify_inputs(), (base, update))
                self.assertEqual(tales.identify_keys(), keys)
                with patch("builtins.print") as printed:
                    self.assertEqual(tales.dispatch("tales-probe-v1", parent), 0)
                    printed.assert_called_once_with("TALES_GATEWAY_V1")
                with patch.object(parent, "send_file") as sender:
                    self.assertEqual(tales.dispatch("tales-read-keys", parent), 0)
                    sender.assert_called_once_with(keys)
                with patch("builtins.print") as printed:
                    self.assertEqual(tales.dispatch("tales-metadata-v1", parent), 0)
                    printed.assert_called_once_with(
                        f"{GAME:016X} {GAME + 0x800:016X} 131072")

    def test_reject_wrong_update_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            _, update, _ = self.make_inputs(folder)
            update.rename(folder / f"Tales [{GAME + 0x1800:016X}][v131072].nsp")
            with patch.object(tales, "local_source", return_value=folder):
                with self.assertRaises(ValueError):
                    tales.identify_inputs()

    def test_reject_extra_nsp(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.make_inputs(folder)
            (folder / "extra.nsp").write_bytes(b"other")
            with patch.object(tales, "local_source", return_value=folder):
                with self.assertRaises(ValueError):
                    tales.identify_inputs()

    def test_reject_symlinked_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            _, _, keys = self.make_inputs(folder)
            keys.unlink()
            target = folder / "other.keys"
            target.write_bytes(b"not-a-secret")
            keys.symlink_to(target)
            with patch.object(tales, "local_source", return_value=folder):
                with self.assertRaises(ValueError):
                    tales.identify_keys()

    def test_cache_path_restored(self):
        original = parent.CACHE, parent.CONFLICTS, parent.OUTPUT
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(tales, "CACHE", root / "cache"), \
                 patch.object(tales, "CONFLICTS", root / "conflicts"), \
                 patch.object(tales, "OUTPUT", root / "results"):
                observed = []
                with patch.object(parent, "read_cache", side_effect=lambda: observed.append(
                        (parent.CACHE, parent.CONFLICTS, parent.OUTPUT))):
                    self.assertEqual(tales.dispatch("tales-read-cache", parent), 0)
                self.assertEqual(observed, [(root / "cache", root / "conflicts",
                                              root / "results")])
        self.assertEqual((parent.CACHE, parent.CONFLICTS, parent.OUTPUT), original)

    def test_local_source_must_be_documents_direct_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            documents = home / "Documents"
            documents.mkdir()
            permitted = documents / "sample"
            permitted.mkdir()
            root = home / "tales"
            root.mkdir()
            link = root / "source"
            link.symlink_to(permitted, target_is_directory=True)
            with patch.object(tales.Path, "home", return_value=home), \
                 patch.object(tales, "SOURCE_LINK", link):
                # macOS resolves /var to /private/var; compare canonical paths.
                self.assertEqual(tales.local_source(), permitted.resolve(strict=True))
                link.unlink()
                link.symlink_to(home, target_is_directory=True)
                with self.assertRaises(ValueError):
                    tales.local_source()


if __name__ == "__main__":
    unittest.main()
