#!/usr/bin/env python3
"""Test the pinned fail-closed TOTK low-disk MacNativeGames adapter."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from security import totk_mng_compact as compact


class CompactTests(unittest.TestCase):
    def test_exact_anchor_patch_compiles_and_is_single_use(self):
        with tempfile.TemporaryDirectory() as root:
            tree = Path(root)
            f = tree / "build_app.py"
            sample = (
                "def budget():\n"
                "    if device_app:\n"
                + compact.DISK_CHECK + "\n"
                + "def build():\n" + compact.BEFORE_MERGE + "\n"
            )
            f.write_text(sample)
            with patch.object(compact.subprocess, "check_output",
                              return_value=compact.PIN):
                compact.apply(f, check=True)
                self.assertEqual(f.read_text(), sample)
                compact.apply(f, check=False)
                after = f.read_text()
                self.assertIn("old_base.unlink()", after)
                self.assertIn("candidate.unlink()", after)
                self.assertIn("required=34", after)
                self.assertIn("step_update_data", after)
                compile(after, str(f), "exec")
                with self.assertRaises(ValueError):
                    compact.apply(f, check=False)

    def test_wrong_upstream_ref_is_refused(self):
        with tempfile.TemporaryDirectory() as root:
            f = Path(root) / "build_app.py"
            f.write_text(compact.DISK_CHECK + compact.BEFORE_MERGE)
            with patch.object(compact.subprocess, "check_output",
                              return_value="unrecognized-ref"):
                with self.assertRaises(ValueError):
                    compact.apply(f, check=False)

    def test_ambiguous_anchors_are_refused_without_write(self):
        with tempfile.TemporaryDirectory() as root:
            f = Path(root) / "build_app.py"
            before = compact.DISK_CHECK + "\n" + compact.DISK_CHECK + "\n" + compact.BEFORE_MERGE
            f.write_text(before)
            with patch.object(compact.subprocess, "check_output",
                              return_value=compact.PIN):
                with self.assertRaises(ValueError):
                    compact.apply(f, check=False)
            self.assertEqual(f.read_text(), before)


if __name__ == "__main__":
    unittest.main()
