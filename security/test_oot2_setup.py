#!/usr/bin/env python3
"""Setup tests on Linux/macOS with a sparse synthetic NUP and fake keys."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from security.test_oot2_nup_info import fake_nup

SCRIPT = Path(__file__).with_name("setup_oot2.sh")


class SetupTests(unittest.TestCase):
    def run_setup(self, home):
        return subprocess.run(
            ["bash", str(SCRIPT)], env={**os.environ, "HOME": str(home)},
            capture_output=True, text=True, timeout=35, check=False)

    @staticmethod
    def make_files(path):
        path.mkdir()
        fake_nup(path/"original.nup")
        (path/"prod.keys").write_text("fake sensitive marker: testing only\n")

    def test_exact_mixed_case_folder_and_no_key_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            docs = home/"Documents"
            docs.mkdir()
            game = docs/"The Legend of Zelda Ocarina of TIme"
            self.make_files(game)
            r = self.run_setup(home)
            self.assertEqual(r.returncode, 0, (r.stdout,r.stderr))
            self.assertIn("OOT2_GATEWAY_V1 source=ok", r.stdout)
            self.assertIn("update=v131072", r.stdout)
            project = home/"portage-ipados/oot-switch2"
            self.assertTrue((project/"source").samefile(game))
            self.assertTrue((game/"original.nup").exists())
            self.assertFalse((project/"private").exists())
            self.assertEqual(sorted(p.name for p in project.iterdir()),
                             ["resultats", "shader-cache", "shader-cache-conflicts", "source"])
            self.assertNotIn("fake sensitive marker",r.stdout+r.stderr)

    def test_unique_case_variant_on_case_sensitive_filenames(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            docs = home/"Documents"
            docs.mkdir()
            game = docs/"THE LEGEND OF ZELDA OCARINA OF TIME"
            self.make_files(game)
            r = self.run_setup(home)
            self.assertEqual(r.returncode,0,(r.stdout,r.stderr))
            self.assertTrue((home/"portage-ipados/oot-switch2/source").samefile(game))

    def test_wrong_update_version_stops_before_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp)
            docs=home/"Documents"
            docs.mkdir()
            game=docs/"The Legend of Zelda Ocarina of TIme"
            self.make_files(game)
            fake_nup(game/"original.nup", version=65536)
            r=self.run_setup(home)
            self.assertNotEqual(r.returncode,0)
            self.assertIn("reason=version",r.stdout)
            self.assertTrue((game/"original.nup").exists())

    def test_two_nups_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp)
            docs=home/"Documents"
            docs.mkdir()
            game=docs/"The Legend of Zelda Ocarina of TIme"
            self.make_files(game)
            fake_nup(game/"second.nup")
            r=self.run_setup(home)
            self.assertNotEqual(r.returncode,0)
            self.assertIn("reason=count",r.stdout)
            self.assertIn("source NUP count=2",r.stderr)

    def test_unrelated_similar_folder_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp)
            docs=home/"Documents"
            docs.mkdir()
            self.make_files(docs/"The Legend of Zelda Ocarina of Time Remastered")
            r=self.run_setup(home)
            self.assertNotEqual(r.returncode,0)
            self.assertFalse((home/"portage-ipados/oot-switch2").exists())


if __name__=="__main__":
    unittest.main()
