#!/usr/bin/env python3
"""Synthetic Wonder XCI+NSP gateway tests. Sparse files; no retail content."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from security import wonder_gateway as gw
from security import ffr_ssh_gate as parent


class WONDERGatewayTests(unittest.TestCase):
    @staticmethod
    def fixtures(folder, actual_sizes=False):
        base = folder / "Super Mario Bros Wonder.xci"
        update = folder / "Super Mario Bros Wonder v1.2.0.nsp"
        base_size = 7985954816 if actual_sizes else 600 * 1024**2
        update_size = 146680088 if actual_sizes else 150 * 1024**2
        with base.open("wb") as out:
            out.seek(0x100)
            out.write(b"HEAD")
            out.truncate(base_size)
        with update.open("wb") as out:
            out.write(b"PFS0")
            out.truncate(update_size)
        return {"base": base, "update": update}

    def test_actual_names_and_sparse_byte_lengths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pair = self.fixtures(root, actual_sizes=True)
            with patch.object(gw, "source_folder", return_value=root):
                self.assertEqual(gw.packages(), pair)
            self.assertEqual(pair["base"].stat().st_size, 7985954816)
            self.assertEqual(pair["update"].stat().st_size, 146680088)
            self.assertEqual(gw.VERSION, "unverified")

    def test_manifest_routing_and_keys(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pair = self.fixtures(root)
            keys = root / "keys"
            keys.write_text("synthetic only")
            with patch.object(gw, "source_folder", return_value=root), \
                 patch.object(gw, "KEYS", keys):
                with patch("builtins.print") as output:
                    self.assertEqual(gw.dispatch("wonder-probe-v1", parent), 0)
                    output.assert_called_once_with("WONDER_GATEWAY_V1")
                with patch("builtins.print") as output:
                    self.assertEqual(gw.dispatch("wonder-manifest-v1", parent), 0)
                    output.assert_called_once_with(
                        gw.TITLE, "unverified",
                        pair["base"].stat().st_size, pair["update"].stat().st_size)
                with patch.object(parent, "send_file") as sender:
                    for role in ("base", "update"):
                        self.assertEqual(gw.dispatch(f"wonder-read-{role}", parent), 0)
                        sender.assert_called_with(pair[role])
                    self.assertEqual(gw.dispatch("wonder-read-keys", parent), 0)
                    sender.assert_called_with(keys)

    def test_roles_are_from_formats_not_names_or_sizes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pair = self.fixtures(root)
            base = root / "cartridge.xci"
            update = root / "patch.nsp"
            pair["base"].rename(base)
            pair["update"].rename(update)
            # Do not let the earlier two-NSP size heuristic dictate roles.
            with update.open("r+b") as stream:
                stream.truncate(800 * 1024**2)
            with patch.object(gw, "source_folder", return_value=root):
                self.assertEqual(gw.packages(), {"base": base, "update": update})

    def test_reject_missing_or_extra_and_wrong_extension(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pair = self.fixtures(root)
            with patch.object(gw, "source_folder", return_value=root):
                third = root / "extra.nsp"
                third.write_bytes(b"PFS0")
                with self.assertRaisesRegex(ValueError, "exactly one XCI"):
                    gw.packages()
                third.unlink()
                base_nsp = root / "wrong format.nsp"
                pair["base"].rename(base_nsp)
                with self.assertRaisesRegex(ValueError, "exactly one XCI"):
                    gw.packages()

    def test_reject_wrong_headers(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pair = self.fixtures(root)
            with patch.object(gw, "source_folder", return_value=root):
                with pair["base"].open("r+b") as stream:
                    stream.seek(0x100)
                    stream.write(b"FAIL")
                with self.assertRaisesRegex(ValueError, "XCI HEAD"):
                    gw.packages()
                with pair["base"].open("r+b") as stream:
                    stream.seek(0x100)
                    stream.write(b"HEAD")
                with pair["update"].open("r+b") as stream:
                    stream.write(b"FAIL")
                with self.assertRaisesRegex(ValueError, "NSP PFS0"):
                    gw.packages()

    def test_reject_conflicting_title_and_revision_markers(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pair = self.fixtures(root)
            with patch.object(gw, "source_folder", return_value=root):
                for role, wrong_name in (
                    ("base", "base [010015100B514800][v0].xci"),
                    ("update", "update [010015100B514000][v262144].nsp"),
                    ("update", "update [0100999999990000].nsp"),
                ):
                    current = pair[role]
                    wrong = root / wrong_name
                    current.rename(wrong)
                    with self.assertRaisesRegex(ValueError, "title ID"):
                        gw.packages()
                    wrong.rename(current)
                for wrong_name in ("update [v0].nsp", "update [v327680].nsp",
                                   "update [v65536].nsp"):
                    current = pair["update"]
                    wrong = root / wrong_name
                    current.rename(wrong)
                    with self.assertRaisesRegex(ValueError, "version"):
                        gw.packages()
                    wrong.rename(current)

    def test_reject_symlink_source_and_keys(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pair = self.fixtures(root)
            store = root / "archive"
            store.mkdir()
            real = store / "original.xci"
            pair["base"].rename(real)
            pair["base"].symlink_to(real)
            with patch.object(gw, "source_folder", return_value=root):
                with self.assertRaisesRegex(ValueError, "regular"):
                    gw.packages()
            keys = root / "keys"
            keys.write_text("synthetic")
            alias = root / "symlink.keys"
            alias.symlink_to(keys)
            with patch.object(gw, "KEYS", alias):
                with self.assertRaises(ValueError):
                    gw.private_keys()

    def test_diagnostics_do_not_disclose_game_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pair = self.fixtures(root)
            keys = root / "keys"
            keys.write_text("synthetic")
            with patch.object(gw, "source_folder", return_value=root), \
                 patch.object(gw, "KEYS", keys), patch("builtins.print") as output:
                self.assertEqual(gw.dispatch("wonder-diagnose-v2", parent), 0)
                output.assert_called_once_with(
                    "WONDER_DIAG_V2 source=ok packages=ok keys=ok reason=none")
                pair["base"].unlink()
                output.reset_mock()
                self.assertEqual(gw.dispatch("wonder-diagnose-v2", parent), 0)
                output.assert_called_once_with(
                    "WONDER_DIAG_V2 source=ok packages=fail keys=ok reason=count")

    def test_source_link_must_target_direct_documents_child(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            docs = home / "Documents"
            docs.mkdir()
            game = docs / "Super Mario Bros Wonder"
            game.mkdir()
            root = home / "project"
            root.mkdir()
            link = root / "source"
            link.symlink_to(game, target_is_directory=True)
            with patch.object(gw.Path, "home", return_value=home), \
                 patch.object(gw, "SOURCE_LINK", link):
                self.assertEqual(gw.source_folder(), game.resolve())
                link.unlink()
                link.symlink_to(home, target_is_directory=True)
                with self.assertRaises(ValueError):
                    gw.source_folder()

    def test_command_allowlist_and_private_cache_isolation(self):
        self.assertEqual(gw.dispatch("wonder-shell", parent), 126)
        orig = parent.CACHE, parent.CONFLICTS, parent.OUTPUT
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(gw, "CACHE", root / "cache"), \
                 patch.object(gw, "CONFLICTS", root / "conflicts"), \
                 patch.object(gw, "OUTPUT", root / "resultats"):
                with patch.object(parent, "receive_file") as receiver:
                    self.assertEqual(gw.dispatch("wonder-write-ipa", parent), 0)
                    receiver.assert_called_once_with(
                        "SuperMarioBrosWonder-nxnative.ipa", 16 * 1024**3)
                    receiver.reset_mock()
                    self.assertEqual(gw.dispatch("wonder-write-inspection", parent), 0)
                    receiver.assert_called_once_with("wonder-inspection.log", 8 * 1024**2)
                with patch.object(parent, "read_cache") as reader:
                    self.assertEqual(gw.dispatch("wonder-read-cache", parent), 0)
                    reader.assert_called_once()
        self.assertEqual((parent.CACHE, parent.CONFLICTS, parent.OUTPUT), orig)


if __name__ == "__main__":
    unittest.main()
