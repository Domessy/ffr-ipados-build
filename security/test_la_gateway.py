#!/usr/bin/env python3
"""TOTK nxnative gateway tests: fake sparse NSPs, fake keys, no retail assets."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from security import la_gateway as gw
from security import ffr_ssh_gate as parent


class ZLAGatewayTests(unittest.TestCase):
    def fixtures(self, folder):
        names = {
            "base": "The Legend of Zelda Links Awakening [01006BB00C6F0000][v0].nsp",
            "update": "The Legend of Zelda Links Awakening_Update_v131072.nsp",
        }
        sizes = {"base": 5 * 1024**3, "update": 500 * 1024**2}
        result = {}
        for role in names:
            p = folder / names[role]
            with p.open("wb") as file:
                file.write(b"PFS0")
                file.truncate(sizes[role])
            result[role] = p
        return result

    def test_title_roles_manifest_and_keys(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            sources = self.fixtures(folder)
            keys = folder / "dedicated.keys"
            keys.write_text("synthetic only")
            with patch.object(gw, "source_folder", return_value=folder), \
                 patch.object(gw, "KEYS", keys):
                self.assertEqual(gw.packages(), sources)
                with patch("builtins.print") as output:
                    self.assertEqual(gw.dispatch("zla-manifest-v1", parent), 0)
                    output.assert_called_once_with(
                        gw.TITLE, gw.VERSION, sources["base"].stat().st_size,
                        sources["update"].stat().st_size,
                    )
                with patch.object(parent, "send_file") as sender:
                    self.assertEqual(gw.dispatch("zla-read-base", parent), 0)
                    sender.assert_called_with(sources["base"])
                    self.assertEqual(gw.dispatch("zla-read-update", parent), 0)
                    sender.assert_called_with(sources["update"])
                    self.assertEqual(gw.dispatch("zla-read-keys", parent), 0)
                    sender.assert_called_with(keys)
                with patch("builtins.print") as output:
                    self.assertEqual(gw.dispatch("zla-probe-v1", parent), 0)
                    output.assert_called_once_with("ZLA_GATEWAY_V1")

    def test_reject_additional_or_unrelated_package(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            sources = self.fixtures(folder)
            with patch.object(gw, "source_folder", return_value=folder):
                (folder / "Other.nsp").write_bytes(b"PFS0")
                with self.assertRaises(ValueError):
                    gw.packages()
                (folder / "Other.nsp").unlink()
                sources["update"].rename(folder / "Unknown Update.nsp")
                with self.assertRaises(ValueError):
                    gw.packages()

    def test_reject_symlink_package_and_private_key(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            sources = self.fixtures(folder)
            temp_file = folder / "saved.nsp"
            sources["update"].rename(temp_file)
            sources["update"].symlink_to(temp_file)
            with patch.object(gw, "source_folder", return_value=folder):
                with self.assertRaises(ValueError):
                    gw.packages()
            key = folder / "keys"
            key.write_text("fake test key")
            link = folder / "symlink.keys"
            link.symlink_to(key)
            with patch.object(gw, "KEYS", link):
                with self.assertRaises(ValueError):
                    gw.private_keys()

    def test_source_must_be_selected_immediate_documents_folder(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            docs = home / "Documents"
            docs.mkdir()
            game = docs / "TOTK"
            game.mkdir()
            project = home / "project"
            project.mkdir()
            selected = project / "source"
            selected.symlink_to(game, target_is_directory=True)
            with patch.object(gw.Path, "home", return_value=home), \
                 patch.object(gw, "SOURCE_LINK", selected):
                self.assertEqual(gw.source_folder(), game.resolve())
                selected.unlink()
                selected.symlink_to(home, target_is_directory=True)
                with self.assertRaises(ValueError):
                    gw.source_folder()

    def test_diagnostic_fixed_codes_never_reveals_paths(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            self.fixtures(folder)
            keys = folder / "keys"
            keys.write_text("synthetic")
            with patch.object(gw, "source_folder", return_value=folder), \
                 patch.object(gw, "KEYS", keys), \
                 patch("builtins.print") as output:
                self.assertEqual(gw.dispatch("zla-diagnose-v1", parent), 0)
                output.assert_called_once_with(
                    "ZLA_DIAG_V1 source=ok packages=ok keys=ok"
                )
            with patch.object(gw, "source_folder", side_effect=ValueError("hidden path")), \
                 patch.object(gw, "KEYS", folder / "missing.keys"), \
                 patch("builtins.print") as output:
                self.assertEqual(gw.dispatch("zla-diagnose-v1", parent), 0)
                output.assert_called_once_with(
                    "ZLA_DIAG_V1 source=fail packages=fail keys=fail"
                )

    def test_command_allowlist_and_separate_cache_scope(self):
        self.assertEqual(gw.dispatch("zla-shell", parent), 126)
        original = parent.CACHE, parent.CONFLICTS, parent.OUTPUT
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with patch.object(gw, "CACHE", root / "cache"), \
                 patch.object(gw, "CONFLICTS", root / "conflicts"), \
                 patch.object(gw, "OUTPUT", root / "resultats"):
                with patch.object(parent, "read_cache") as reader:
                    self.assertEqual(gw.dispatch("zla-read-cache", parent), 0)
                    reader.assert_called_once()
                    self.assertEqual((parent.CACHE, parent.CONFLICTS, parent.OUTPUT), original)
                with patch.object(parent, "receive_file") as receiver:
                    self.assertEqual(gw.dispatch("zla-write-ipa", parent), 0)
                    receiver.assert_called_once_with("ZeldaLinksAwakening-nxnative.ipa", 16 * 1024**3)
        self.assertEqual((parent.CACHE, parent.CONFLICTS, parent.OUTPUT), original)


if __name__ == "__main__":
    unittest.main()
