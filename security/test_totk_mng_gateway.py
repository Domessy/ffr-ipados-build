#!/usr/bin/env python3
"""Synthetic TOTK gateway tests; no retail game or real Switch keys."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from security import ffr_ssh_gate as parent
from security import totk_mng_gateway as totk


class TOTKGatewayTests(unittest.TestCase):
    def files(self, folder):
        p = {}
        names = {
            "base": "The Legend of Zelda Tears of the Kingdom [0100F2C0115B6000][v0].nsp",
            "update": "The Legend of Zelda Tears of the Kingdom_Update_v720896.nsp",
        }
        sizes = {"base": 10 * 1024**3 + 20, "update": 300 * 1024**2}
        for role, name in names.items():
            p[role] = folder / name
            with p[role].open("wb") as w:
                w.write(b"PFS0")
                w.truncate(sizes[role])  # sparse fake fixtures
        return p

    def test_metadata_and_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            files = self.files(folder)
            with patch.object(totk, "source_folder", return_value=folder), \
                 patch.object(totk, "FONTS", folder / "absent"), \
                 patch.object(parent, "PRIVATE", folder / "test.keys"):
                (folder / "test.keys").write_text("synthetic-only")
                self.assertEqual(totk.sources(), files)
                with patch("builtins.print") as print_mock:
                    self.assertEqual(totk.dispatch("totk-mng-manifest-v1", parent), 0)
                    print_mock.assert_called_once_with(totk.BASE_ID, totk.UPDATE_VERSION,
                        files["base"].stat().st_size, files["update"].stat().st_size, 0)
                with patch.object(parent, "send_file") as send:
                    self.assertEqual(totk.dispatch("totk-mng-read-base", parent), 0)
                    send.assert_called_with(files["base"])
                with patch("builtins.print") as output:
                    self.assertEqual(totk.dispatch("totk-mng-probe-v1", parent), 0)
                    output.assert_called_once_with("TOTK_MNG_GATEWAY_V1")

    def test_reject_unexpected_extra_nsp(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            self.files(folder)
            (folder / "third.nsp").write_bytes(b"PFS0")
            with patch.object(totk, "source_folder", return_value=folder):
                with self.assertRaises(ValueError):
                    totk.sources()

    def test_canonical_documents_only(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            docs = home / "Documents"
            docs.mkdir()
            game = docs / "TOTK"
            game.mkdir()
            work = home / "totk"
            work.mkdir()
            link = work / "source"
            link.symlink_to(game, target_is_directory=True)
            with patch.object(totk.Path, "home", return_value=home), \
                 patch.object(totk, "SOURCE_LINK", link):
                self.assertEqual(totk.source_folder(), game.resolve())
                link.unlink()
                link.symlink_to(home)
                with self.assertRaises(ValueError):
                    totk.source_folder()

    def test_fonts_six_exact_names_and_no_links(self):
        with tempfile.TemporaryDirectory() as temp:
            fonts = Path(temp)
            with patch.object(totk, "FONTS", fonts):
                for name in totk.FONT_NAMES:
                    (fonts / name).write_bytes(b"\x00" * 16)
                self.assertEqual(len(totk.font_files()), 6)
                (fonts / totk.FONT_NAMES[5]).unlink()
                self.assertIsNone(totk.font_files())
                p = fonts / totk.FONT_NAMES[5]
                p.symlink_to(fonts / totk.FONT_NAMES[0])
                self.assertIsNone(totk.font_files())

    def test_no_arbitrary_command(self):
        self.assertEqual(totk.dispatch("totk-mng-exec-shell", parent), 126)


if __name__ == "__main__":
    unittest.main()
