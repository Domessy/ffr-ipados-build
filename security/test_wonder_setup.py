#!/usr/bin/env python3
"""No-retail-asset tests for Wonder setup case-variant source discovery."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("setup_wonder.sh")


class WonderSetupTests(unittest.TestCase):
    @staticmethod
    def make_sources(folder):
        folder.mkdir()
        with (folder / "prod.keys").open("w") as key:
            key.write("synthetic test keys; not usable for any Nintendo package\n")
        with (folder / "base [010015100B514000][v0].nsp").open("wb") as stream:
            stream.write(b"PFS0")
            stream.truncate(600 * 1024**2)
        with (folder / "update [010015100B514800][v262144].nsp").open("wb") as stream:
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
            game = documents / "SUPER MARIO BROS WONDER"
            self.make_sources(game)
            result = self.run_setup(home)
            self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
            # On a case-sensitive filesystem the shell must discover the
            # unique spelling variant. On typical macOS APFS the requested
            # "Super Mario Bros Wonder" name already resolves to the same directory.
            if not (documents / "Super Mario Bros Wonder").exists():
                self.assertIn("case-insensitive exact-name match", result.stdout)
            self.assertIn("WONDER_GATEWAY_V1", result.stdout)
            project = home / "portage-ipados/super-mario-bros-wonder"
            self.assertTrue((project / "source").samefile(game))
            self.assertEqual(
                (project / "private/prod.keys").read_bytes(),
                (game / "prod.keys").read_bytes(),
            )
            self.assertTrue((game / "base [010015100B514000][v0].nsp").exists())
            self.assertTrue((game / "update [010015100B514800][v262144].nsp").exists())

    def test_ambiguous_case_variants_are_not_selected(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            documents = home / "Documents"
            documents.mkdir()
            self.make_sources(documents / "SUPER MARIO BROS WONDER")
            # Many macOS runners use case-insensitive APFS. Two distinct
            # directories with only case differences cannot coexist there.
            if (documents / "Super Mario Bros WONDER").exists():
                self.skipTest("filesystem does not distinguish case-only directory names")
            self.make_sources(documents / "Super Mario Bros WONDER")
            result = self.run_setup(home)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("directory unavailable", result.stderr)
            self.assertFalse((home / "portage-ipados/super-mario-bros-wonder").exists())

    def test_mixed_xci_nsp_rejected_before_any_private_transfer(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            docs = home / "Documents"
            docs.mkdir()
            folder = docs / "Super Mario Bros Wonder"
            self.make_sources(folder)
            base = folder / "base [010015100B514000][v0].nsp"
            wrong = folder / "base [010015100B514000][v0].xci"
            base.rename(wrong)
            result = self.run_setup(home)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("WONDER_DIAG_V2 source=ok packages=fail keys=ok reason=count", result.stdout)
            self.assertIn("base [010015100B514000][v0].xci", result.stderr)
            self.assertNotIn("synthetic test keys", result.stderr)
            self.assertTrue(wrong.exists())

    def test_unrelated_similar_title_is_not_selected(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            documents = home / "Documents"
            documents.mkdir()
            self.make_sources(documents / "Super Mario Bros Wonder Definitive")
            result = self.run_setup(home)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("candidate directories", result.stderr)
            self.assertFalse((home / "portage-ipados/super-mario-bros-wonder").exists())


if __name__ == "__main__":
    unittest.main()
