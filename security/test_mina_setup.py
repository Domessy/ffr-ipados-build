#!/usr/bin/env python3
"""No-retail-asset tests for Mina setup case-variant source discovery."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("setup_mina.sh")


class MinaSetupTests(unittest.TestCase):
    @staticmethod
    def make_sources(folder):
        folder.mkdir()
        with (folder / "prod.keys").open("w") as key:
            key.write("synthetic test keys; not usable for any Nintendo package\n")
        with (folder / "base [0100DCD01F306000][v0].nsp").open("wb") as stream:
            stream.write(b"PFS0")
            stream.truncate(600 * 1024**2)
        with (folder / "update [0100DCD01F306800][v131072].nsp").open("wb") as stream:
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
            game = documents / "Mina The HOLLowER"
            self.make_sources(game)
            result = self.run_setup(home)
            self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
            self.assertIn("case-insensitive exact-name match", result.stdout)
            self.assertIn("MINA_GATEWAY_V1", result.stdout)
            project = home / "portage-ipados/mina-the-hollower"
            self.assertEqual((project / "source").resolve(), game)
            self.assertEqual(
                (project / "private/prod.keys").read_bytes(),
                (game / "prod.keys").read_bytes(),
            )
            self.assertTrue((game / "base [0100DCD01F306000][v0].nsp").exists())
            self.assertTrue((game / "update [0100DCD01F306800][v131072].nsp").exists())

    def test_ambiguous_case_variants_are_not_selected(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            documents = home / "Documents"
            documents.mkdir()
            self.make_sources(documents / "Mina The HOLLowER")
            self.make_sources(documents / "MINA THE HOLLOWER")
            result = self.run_setup(home)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("directory unavailable", result.stderr)
            self.assertFalse((home / "portage-ipados/mina-the-hollower").exists())

    def test_unrelated_similar_title_is_not_selected(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            documents = home / "Documents"
            documents.mkdir()
            self.make_sources(documents / "Mina the Hollower Definitive")
            result = self.run_setup(home)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("candidate directories", result.stderr)
            self.assertFalse((home / "portage-ipados/mina-the-hollower").exists())


if __name__ == "__main__":
    unittest.main()
