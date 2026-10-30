#!/usr/bin/env python3
"""Small synthetic tests for BOTW fixed four-file SSH routing and isolation."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from security import botw_gateway as botw
from security import ffr_ssh_gate as parent


class BOTWGatewayTests(unittest.TestCase):
    def sources(self, directory):
        names = {
            "base": "BOTW Base [v0].nsp",
            "update": "BOTW [US][Update v1.9.0p].nsp",
            "dlc1": "BOTW [DLC Pack 1] [01007EF00011F001][v196608].nsp",
            "dlc2": "BOTW [DLC Pack 2] [01007EF00011F002][v196608].nsp",
        }
        sizes = {"base": 1024**3 + 128, "update": 2 * 1024**2,
                 "dlc1": 512, "dlc2": 128}
        result = {}
        for role, name in names.items():
            file = directory / name
            with file.open("wb") as out:
                out.write(b"PFS0")
                out.truncate(sizes[role])  # sparse: no gigabyte files written
            result[role] = file
        return result

    def test_four_inputs_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            original = self.sources(folder)
            fake_keys = folder / "keys"  # test placeholder, never a real key
            fake_keys.write_bytes(b"test only")
            with patch.object(botw, "local_source", return_value=folder), \
                 patch.object(parent, "PRIVATE", fake_keys):
                self.assertEqual(botw.inputs(), original)
                with patch("builtins.print") as out:
                    self.assertEqual(botw.dispatch("botw-probe-v1", parent), 0)
                    out.assert_called_once_with("BOTW_GATEWAY_V1")
                with patch("builtins.print") as out:
                    self.assertEqual(botw.dispatch("botw-manifest-v1", parent), 0)
                    out.assert_called_once()
                    tokens = out.call_args.args[0].split()
                    self.assertEqual(tokens[:3], ["01007EF00011E000", "1114112", "196608"])
                    self.assertEqual(list(map(int, tokens[3:])),
                        [original[x].stat().st_size for x in ("base", "update", "dlc1", "dlc2")])
                with patch.object(parent, "send_file") as send:
                    for role in ("base", "update", "dlc1", "dlc2"):
                        self.assertEqual(botw.dispatch("botw-read-" + role, parent), 0)
                        send.assert_called_with(original[role])
                    self.assertEqual(botw.dispatch("botw-read-keys", parent), 0)
                    send.assert_called_with(fake_keys, allow_key_link=True)

    def test_reject_unrelated_or_extra_nsp(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.sources(folder)
            (folder / "other.nsp").write_bytes(b"PFS0")
            with patch.object(botw, "local_source", return_value=folder):
                with self.assertRaises(ValueError):
                    botw.inputs()

    def test_reject_bad_dlc_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            files = self.sources(folder)
            files["dlc2"].rename(folder / "BOTW [DLC Pack 2] [01007EF00011F003][v196608].nsp")
            with patch.object(botw, "local_source", return_value=folder):
                with self.assertRaises(ValueError):
                    botw.inputs()

    def test_reject_symlinked_nsp(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            files = self.sources(folder)
            path = files["dlc2"]
            path.unlink()
            path.symlink_to(files["dlc1"])
            with patch.object(botw, "local_source", return_value=folder):
                with self.assertRaises(ValueError):
                    botw.inputs()

    def test_document_source_link_constraint(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            docs = home / "Documents"
            docs.mkdir()
            game = docs / "one"
            game.mkdir()
            root = home / "botw"
            root.mkdir()
            link = root / "source"
            link.symlink_to(game, target_is_directory=True)
            with patch.object(botw.Path, "home", return_value=home), \
                 patch.object(botw, "SOURCE_LINK", link):
                self.assertEqual(botw.local_source(), game.resolve(strict=True))
                link.unlink()
                link.symlink_to(home, target_is_directory=True)
                with self.assertRaises(ValueError):
                    botw.local_source()

    def test_independent_cache_paths_restored(self):
        before = parent.CACHE, parent.CONFLICTS, parent.OUTPUT
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(botw, "CACHE", root / "cache"), \
                 patch.object(botw, "CONFLICTS", root / "conflicts"), \
                 patch.object(botw, "OUTPUT", root / "results"):
                visited = []
                with patch.object(parent, "read_cache", side_effect=lambda: visited.append(
                    (parent.CACHE, parent.CONFLICTS, parent.OUTPUT))):
                    self.assertEqual(botw.dispatch("botw-read-cache", parent), 0)
                self.assertEqual(visited, [(root / "cache", root / "conflicts", root / "results")])
        self.assertEqual((parent.CACHE, parent.CONFLICTS, parent.OUTPUT), before)


if __name__ == "__main__":
    unittest.main()
