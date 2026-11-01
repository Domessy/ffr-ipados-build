#!/usr/bin/env python3
"""Synthetic security tests: fake sparse XCI/NSP, fake keys, no game content."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from security import eow_gateway as gw
from security import ffr_ssh_gate as parent


class EchoesGatewayTests(unittest.TestCase):
    def fixtures(self, folder):
        base = folder / "Echoes of Wisdom [01008CF01BAAC000][v0].xci"
        update = folder / "Echoes of Wisdom [01008CF01BAAC800][v196608].nsp"
        with base.open("wb") as stream:
            stream.seek(0x100)
            stream.write(b"HEAD")
            stream.truncate(3 * 1024**3)
        with update.open("wb") as stream:
            stream.write(b"PFS0")
            stream.truncate(384 * 1024**2)
        return {"base": base, "update": update}

    def test_manifest_and_read_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            pair = self.fixtures(folder)
            keys = folder / "keys"
            keys.write_text("synthetic keys")
            with patch.object(gw, "source_folder", return_value=folder), \
                 patch.object(gw, "KEYS", keys):
                self.assertEqual(gw.packages(), pair)
                with patch("builtins.print") as output:
                    self.assertEqual(gw.dispatch("eow-manifest-v1", parent), 0)
                    output.assert_called_once_with(
                        gw.TITLE, gw.VERSION, pair["base"].stat().st_size,
                        pair["update"].stat().st_size)
                with patch.object(parent, "send_file") as sender:
                    for role in ("base", "update"):
                        self.assertEqual(gw.dispatch("eow-read-" + role, parent), 0)
                        sender.assert_called_with(pair[role])
                    self.assertEqual(gw.dispatch("eow-read-keys", parent), 0)
                    sender.assert_called_with(keys)
                with patch("builtins.print") as output:
                    self.assertEqual(gw.dispatch("eow-probe-v1", parent), 0)
                    output.assert_called_once_with("EOW_GATEWAY_V1")

    def test_plain_filenames_allow_one_xci_one_nsp(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            pair = self.fixtures(folder)
            pair["base"].rename(folder / "base game.xci")
            pair["update"].rename(folder / "update.nsp")
            with patch.object(gw, "source_folder", return_value=folder):
                self.assertEqual(set(gw.packages()), {"base", "update"})

    def test_reject_other_file_roles_and_extra_packages(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            pair = self.fixtures(folder)
            with patch.object(gw, "source_folder", return_value=folder):
                bad = folder / "third.xci"
                bad.write_bytes(b"HEAD")
                with self.assertRaises(ValueError):
                    gw.packages()
                bad.unlink()
                pair["base"].rename(folder / "base.nsp")
                with self.assertRaises(ValueError):
                    gw.packages()

    def test_reject_wrong_magic_and_explicit_version(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            pair = self.fixtures(folder)
            with patch.object(gw, "source_folder", return_value=folder):
                with pair["base"].open("r+b") as stream:
                    stream.seek(0x100)
                    stream.write(b"FAIL")
                with self.assertRaises(ValueError):
                    gw.packages()
                with pair["base"].open("r+b") as stream:
                    stream.seek(0x100)
                    stream.write(b"HEAD")
                pair["update"].rename(folder / "Echoes update [v999999].nsp")
                with self.assertRaises(ValueError):
                    gw.packages()

    def test_reject_symlink_packages_and_keys(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            pair = self.fixtures(folder)
            moved = folder / "moved.xci"
            pair["base"].rename(moved)
            pair["base"].symlink_to(moved)
            with patch.object(gw, "source_folder", return_value=folder):
                with self.assertRaises(ValueError):
                    gw.packages()
            key = folder / "fake.keys"
            key.write_text("only fake keys")
            link = folder / "link.keys"
            link.symlink_to(key)
            with patch.object(gw, "KEYS", link):
                with self.assertRaises(ValueError):
                    gw.private_keys()

    def test_only_direct_documents_child_source(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            docs = home / "Documents"
            docs.mkdir()
            game = docs / "Echoes"
            game.mkdir()
            work = home / "work"
            work.mkdir()
            link = work / "source"
            link.symlink_to(game, target_is_directory=True)
            with patch.object(gw.Path, "home", return_value=home), \
                 patch.object(gw, "SOURCE_LINK", link):
                self.assertEqual(gw.source_folder(), game.resolve())
                link.unlink()
                link.symlink_to(home, target_is_directory=True)
                with self.assertRaises(ValueError):
                    gw.source_folder()

    def test_fixed_diagnostic_never_discloses_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            self.fixtures(folder)
            key = folder / "fake.keys"
            key.write_text("synthetic")
            with patch.object(gw, "source_folder", return_value=folder), \
                 patch.object(gw, "KEYS", key), \
                 patch("builtins.print") as out:
                self.assertEqual(gw.dispatch("eow-diagnose-v1", parent), 0)
                out.assert_called_once_with(
                    "EOW_DIAG_V1 source=ok packages=ok keys=ok")
            with patch.object(gw, "source_folder", side_effect=ValueError("private name")), \
                 patch.object(gw, "KEYS", folder / "nonexistent"), \
                 patch("builtins.print") as out:
                self.assertEqual(gw.dispatch("eow-diagnose-v1", parent), 0)
                out.assert_called_once_with(
                    "EOW_DIAG_V1 source=fail packages=fail keys=fail")

    def test_allowlist_and_isolated_cache_scope(self):
        self.assertEqual(gw.dispatch("eow-shell", parent), 126)
        original = parent.CACHE, parent.CONFLICTS, parent.OUTPUT
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            with patch.object(gw, "CACHE", base / "cache"), \
                 patch.object(gw, "CONFLICTS", base / "conflicts"), \
                 patch.object(gw, "OUTPUT", base / "resultats"):
                with patch.object(parent, "read_cache") as reader:
                    self.assertEqual(gw.dispatch("eow-read-cache", parent), 0)
                    reader.assert_called_once()
                    self.assertEqual((parent.CACHE, parent.CONFLICTS, parent.OUTPUT), original)
                with patch.object(parent, "receive_file") as receiver:
                    self.assertEqual(gw.dispatch("eow-write-ipa", parent), 0)
                    receiver.assert_called_once_with(
                        "ZeldaEchoesOfWisdom-nxnative.ipa", 16 * 1024**3)
        self.assertEqual((parent.CACHE, parent.CONFLICTS, parent.OUTPUT), original)


if __name__ == "__main__":
    unittest.main()
