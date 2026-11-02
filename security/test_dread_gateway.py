#!/usr/bin/env python3
"""Metroid Dread fixed gateway tests: sparse fake XCI/NSP only, never game data."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from security import dread_gateway as gw
from security import ffr_ssh_gate as parent


class DreadGatewayTests(unittest.TestCase):
    @staticmethod
    def fixtures(folder):
        base = folder / "Metroid Dread [010093801237C000][v0].xci"
        update = folder / "Metroid Dread update [010093801237C800][v327680].nsp"
        with base.open("wb") as file:
            file.seek(0x100)
            file.write(b"HEAD")
            file.truncate(3 * 1024**3)
        with update.open("wb") as file:
            file.write(b"PFS0")
            file.truncate(200 * 1024**2)
        return {"base": base, "update": update}

    def test_manifest_routes_and_keys(self):
        with tempfile.TemporaryDirectory() as folder_name:
            folder = Path(folder_name)
            pair = self.fixtures(folder)
            keys = folder / "keys"
            keys.write_text("synthetic only")
            with patch.object(gw, "source_folder", return_value=folder), \
                 patch.object(gw, "KEYS", keys):
                self.assertEqual(gw.packages(), pair)
                with patch("builtins.print") as out:
                    self.assertEqual(gw.dispatch("dread-manifest-v1", parent), 0)
                    out.assert_called_once_with(
                        gw.TITLE, gw.VERSION,
                        pair["base"].stat().st_size, pair["update"].stat().st_size)
                with patch.object(parent, "send_file") as sender:
                    for role in ("base", "update"):
                        self.assertEqual(gw.dispatch(f"dread-read-{role}", parent), 0)
                        sender.assert_called_with(pair[role])
                    self.assertEqual(gw.dispatch("dread-read-keys", parent), 0)
                    sender.assert_called_with(keys)
                with patch("builtins.print") as out:
                    self.assertEqual(gw.dispatch("dread-probe-v1", parent), 0)
                    out.assert_called_once_with("DREAD_GATEWAY_V1")

    def test_plain_xci_nsp_filenames_accepted(self):
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            pair = self.fixtures(folder)
            base = folder / "cartridge.xci"
            update = folder / "patch.nsp"
            pair["base"].rename(base)
            pair["update"].rename(update)
            with patch.object(gw, "source_folder", return_value=folder):
                self.assertEqual(gw.packages(), {"base": base, "update": update})

    def test_reject_wrong_magic_or_explicit_ids_and_version(self):
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            pair = self.fixtures(folder)
            with patch.object(gw, "source_folder", return_value=folder):
                with pair["base"].open("r+b") as file:
                    file.seek(0x100)
                    file.write(b"FAIL")
                with self.assertRaisesRegex(ValueError, "header"):
                    gw.packages()
                with pair["base"].open("r+b") as file:
                    file.seek(0x100)
                    file.write(b"HEAD")
                with pair["update"].open("r+b") as file:
                    file.seek(0)
                    file.write(b"FAIL")
                with self.assertRaisesRegex(ValueError, "PFS0"):
                    gw.packages()
                with pair["update"].open("r+b") as file:
                    file.seek(0)
                    file.write(b"PFS0")
                bad = folder / "update [010093801237C800][v999999].nsp"
                pair["update"].rename(bad)
                with self.assertRaisesRegex(ValueError, "version"):
                    gw.packages()
                wrong = folder / "unrelated [0100999999990000][v327680].nsp"
                bad.rename(wrong)
                with self.assertRaisesRegex(ValueError, "title"):
                    gw.packages()

    def test_count_and_wrong_extensions_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            pair = self.fixtures(folder)
            with patch.object(gw, "source_folder", return_value=folder):
                third = folder / "third.nsp"
                third.write_bytes(b"PFS0")
                with self.assertRaisesRegex(ValueError, "exactly two"):
                    gw.packages()
                third.unlink()
                pair["base"].rename(folder / "cartridge.nsp")
                with self.assertRaisesRegex(ValueError, "duplicate"):
                    gw.packages()

    def test_reject_symlink_package_and_keys(self):
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            pair = self.fixtures(folder)
            moved = folder / "archive" / "moved.xci"
            moved.parent.mkdir()
            pair["base"].rename(moved)
            pair["base"].symlink_to(moved)
            with patch.object(gw, "source_folder", return_value=folder):
                with self.assertRaisesRegex(ValueError, "regular"):
                    gw.packages()
            keys = folder / "keyfile"
            keys.write_text("fake")
            link = folder / "linked.keys"
            link.symlink_to(keys)
            with patch.object(gw, "KEYS", link):
                with self.assertRaises(ValueError):
                    gw.private_keys()

    def test_v3_diagnostic_reports_xci_and_nsp_counts(self):
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            pair = self.fixtures(folder)
            keys = folder / "keys"
            keys.write_text("fake")
            with patch.object(gw, "source_folder", return_value=folder), \
                 patch.object(gw, "KEYS", keys), patch("builtins.print") as out:
                self.assertEqual(gw.dispatch("dread-diagnose-v3", parent), 0)
                out.assert_called_once_with(
                    "DREAD_DIAG_V3 source=ok packages=ok keys=ok reason=none "
                    "top_nsp=1 nested_nsp=0 top_nsz=0 top_xci=1"
                )
            pair["base"].unlink()
            nested = folder / "archive"
            nested.mkdir()
            with (nested / "base.xci").open("wb") as file:
                file.seek(0x100)
                file.write(b"HEAD")
            with patch.object(gw, "source_folder", return_value=folder), \
                 patch.object(gw, "KEYS", keys), patch("builtins.print") as out:
                self.assertEqual(gw.dispatch("dread-diagnose-v3", parent), 0)
                out.assert_called_once()
                self.assertIn("packages=fail", out.call_args.args[0])
                self.assertIn("reason=count", out.call_args.args[0])
                self.assertIn("top_nsp=1", out.call_args.args[0])
                self.assertIn("top_xci=0", out.call_args.args[0])

    def test_route_isolation_private_output_and_cache(self):
        self.assertEqual(gw.dispatch("dread-shell", parent), 126)
        original = parent.CACHE, parent.CONFLICTS, parent.OUTPUT
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            with patch.object(gw, "CACHE", folder / "cache"), \
                 patch.object(gw, "CONFLICTS", folder / "conflicts"), \
                 patch.object(gw, "OUTPUT", folder / "resultats"):
                with patch.object(parent, "receive_file") as receive:
                    self.assertEqual(gw.dispatch("dread-write-ipa", parent), 0)
                    receive.assert_called_once_with("MetroidDread-nxnative.ipa", 16 * 1024**3)
                    receive.reset_mock()
                    self.assertEqual(gw.dispatch("dread-write-inspection", parent), 0)
                    receive.assert_called_once_with("dread-inspection.log", 8 * 1024**2)
                with patch.object(parent, "read_cache") as reader:
                    self.assertEqual(gw.dispatch("dread-read-cache", parent), 0)
                    reader.assert_called_once()
        self.assertEqual((parent.CACHE, parent.CONFLICTS, parent.OUTPUT), original)

    def test_source_is_only_direct_documents_subdirectory(self):
        with tempfile.TemporaryDirectory() as name:
            home = Path(name)
            docs = home / "Documents"
            docs.mkdir()
            src = docs / "Metroid Dread"
            src.mkdir()
            other = home / "wrong"
            other.mkdir()
            link = other / "source"
            link.symlink_to(src, target_is_directory=True)
            with patch.object(gw.Path, "home", return_value=home), \
                 patch.object(gw, "SOURCE_LINK", link):
                self.assertEqual(gw.source_folder(), src.resolve())
                link.unlink()
                link.symlink_to(other, target_is_directory=True)
                with self.assertRaises(ValueError):
                    gw.source_folder()


if __name__ == "__main__":
    unittest.main()
