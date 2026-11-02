#!/usr/bin/env python3
"""No-retail-asset tests for Dark Souls setup case-variant source discovery."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("setup_dsr.sh")


class DarkSoulsSetupTests(unittest.TestCase):
    @staticmethod
    def make_sources(folder):
        folder.mkdir()
        with (folder / "prod.keys").open("w") as key:
            key.write("synthetic test keys; not usable for any Nintendo package\n")
        with (folder / "base [01004AB00A260000][v0].nsp").open("wb") as stream:
            stream.write(b"PFS0")
            stream.truncate(600 * 1024**2)
        with (folder / "update [01004AB00A260800][v196608].nsp").open("wb") as stream:
            stream.write(b"PFS0")
            stream.truncate(8 * 1024**2)

    @staticmethod
    def run_setup(home):
        return subprocess.run(
            ["bash", str(SCRIPT)], env={**os.environ, "HOME": str(home)},
            capture_output=True, text=True, timeout=30, check=False,
        )

    def test_case_variant_resolves_and_preserves_original(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            documents = home / "Documents"
            documents.mkdir()
            game = documents / "DARK SOULS REMASTERED"
            self.make_sources(game)
            result = self.run_setup(home)
            self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
            self.assertIn("case-insensitive exact-name match", result.stdout)
            self.assertIn("DSR_GATEWAY_V1", result.stdout)
            project = home / "portage-ipados/dark-souls-remastered"
            self.assertEqual((project / "source").resolve(), game)
            self.assertEqual(
                (project / "private/prod.keys").read_bytes(),
                (game / "prod.keys").read_bytes(),
            )
            self.assertTrue((game / "base [01004AB00A260000][v0].nsp").exists())
            self.assertTrue((game / "update [01004AB00A260800][v196608].nsp").exists())

    def test_ambiguous_case_variants_are_not_selected(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            documents = home / "Documents"
            documents.mkdir()
            self.make_sources(documents / "DARK SOULS REMASTERED")
            self.make_sources(documents / "Dark Souls REMASTERED")
            result = self.run_setup(home)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("directory unavailable", result.stderr)
            self.assertFalse((home / "portage-ipados/dark-souls-remastered").exists())

    def test_unrelated_similar_title_is_not_selected(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            documents = home / "Documents"
            documents.mkdir()
            self.make_sources(documents / "Dark Souls Remastered Definitive")
            result = self.run_setup(home)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("candidate directories", result.stderr)
            self.assertFalse((home / "portage-ipados/dark-souls-remastered").exists())


if __name__ == "__main__":
    unittest.main()
