#!/usr/bin/env python3
"""Synthetic MPR forced-SSH gateway and private cache scope tests."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from security import mpr_gateway as mpr
from security import ffr_ssh_gate as parent


class MPRGatewayTests(unittest.TestCase):
    def make_base(self, folder, name="Metroid Prime Remastered [010012101468C000][v0].nsp"):
        p = folder / name
        with p.open("wb") as f:
            f.write(b"PFS0")
            f.truncate(256 * 1024**2)  # synthetic sparse fixture
        return p

    def test_single_base_and_gateway_commands(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            file = self.make_base(folder)
            fake = folder / "fake.keys"
            fake.write_text("test fixture only")
            with patch.object(mpr, "local_source", return_value=folder), \
                 patch.object(mpr, "KEYS", fake):
                self.assertEqual(mpr.base_file(), (file, 0))
                with patch("builtins.print") as output:
                    self.assertEqual(mpr.dispatch("mpr-manifest-v1", parent), 0)
                    output.assert_called_once_with(f"{mpr.TITLE} 0 {file.stat().st_size} 0")
                with patch.object(parent, "send_file") as send:
                    self.assertEqual(mpr.dispatch("mpr-read-base", parent), 0)
                    send.assert_called_once_with(file)
                with patch("builtins.print") as output:
                    self.assertEqual(mpr.dispatch("mpr-probe-v1", parent), 0)
                    output.assert_called_once_with("MPR_GATEWAY_V1")

    def test_optional_update_count_not_applied(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            p = self.make_base(folder)
            self.make_base(folder, "Metroid Prime Remastered Update [010012101468C800][v65536].nsp")
            with patch.object(mpr, "local_source", return_value=folder):
                self.assertEqual(mpr.base_file(), (p, 1))

    def test_no_other_game_and_symlinks(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            self.make_base(folder)
            self.make_base(folder, "Unrelated [0100F2C0115B6000][v0].nsp")
            with patch.object(mpr, "local_source", return_value=folder):
                with self.assertRaises(ValueError):
                    mpr.base_file()

    def test_source_direct_documents_child_only(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            docs = home / "Documents"
            docs.mkdir()
            game = docs / "Metroid Prime Remastered"
            game.mkdir()
            project = home / "project"
            project.mkdir()
            link = project / "source"
            link.symlink_to(game, target_is_directory=True)
            with patch.object(mpr.Path, "home", return_value=home), \
                 patch.object(mpr, "SOURCE", link):
                self.assertEqual(mpr.local_source(), game.resolve())
                link.unlink()
                link.symlink_to(home)
                with self.assertRaises(ValueError):
                    mpr.local_source()

    def test_diagnostic_reports_only_fixed_status_codes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            game = root / "game"
            game.mkdir()
            self.make_base(game)
            keys = root / "prod.keys"
            keys.write_text("synthetic private test bytes")
            with patch.object(mpr, "local_source", return_value=game), \
                 patch.object(mpr, "KEYS", keys), \
                 patch("builtins.print") as output:
                self.assertEqual(mpr.dispatch("mpr-diagnose-v1", parent), 0)
                output.assert_called_once_with("MPR_DIAG_V1 source=ok base=ok keys=ok")
            keys.unlink()
            with patch.object(mpr, "local_source", side_effect=ValueError("sensitive path")), \
                 patch.object(mpr, "KEYS", keys), \
                 patch("builtins.print") as output:
                self.assertEqual(mpr.dispatch("mpr-diagnose-v1", parent), 0)
                output.assert_called_once_with("MPR_DIAG_V1 source=fail base=fail keys=fail")

    def test_private_key_path_is_independent_of_shared_ffr(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "prod.keys"
            p.write_text("test private")
            with patch.object(mpr, "KEYS", p):
                self.assertEqual(mpr.private_keys(), p)
                with patch.object(parent, "send_file") as send:
                    self.assertEqual(mpr.dispatch("mpr-read-keys", parent), 0)
                    send.assert_called_once_with(p)
                p.unlink()
                with self.assertRaises(ValueError):
                    mpr.private_keys()
                # A symlink is deliberately disallowed to keep the project
                # independent from paths that may be removed later.
                original = Path(d) / "origin.keys"
                original.write_text("origin test")
                p.symlink_to(original)
                with self.assertRaises(ValueError):
                    mpr.private_keys()

    def test_allowlist_and_cache_scope_restoration(self):
        self.assertEqual(mpr.dispatch("mpr-arbitrary-shell", parent), 126)
        previous = parent.CACHE, parent.CONFLICTS, parent.OUTPUT
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with patch.object(mpr, "CACHE", root / "cache"), \
                 patch.object(mpr, "CONFLICTS", root / "conflicts"), \
                 patch.object(mpr, "OUTPUT", root / "results"):
                visited = []
                with patch.object(parent, "read_cache", side_effect=lambda: visited.append(parent.CACHE)):
                    self.assertEqual(mpr.dispatch("mpr-read-cache", parent), 0)
                self.assertEqual(visited, [root / "cache"])
        self.assertEqual((parent.CACHE,parent.CONFLICTS,parent.OUTPUT), previous)


if __name__ == "__main__":
    unittest.main()
