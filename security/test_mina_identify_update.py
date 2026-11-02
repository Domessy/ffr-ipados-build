#!/usr/bin/env python3
"""Synthetic-only tests for encrypted NSP CNMT parsing; no actual game assets."""
import unittest
from security.mina_identify_update import validate_metadata, meta_rows

BASE = "content Application 0100dcd01f306000 0\n"
UPDATE = "content Patch 0100dcd01f306800 262144\n"


class MinaContentMetadataTests(unittest.TestCase):
    def test_real_update_version_is_selected(self):
        self.assertEqual(validate_metadata(BASE, UPDATE), 262144)

    def test_wrong_base_or_update_id_rejected(self):
        for base, update in (
            ("content Application 0100dcd01f306001 0\n", UPDATE),
            (BASE, "content Patch 0100dcd01f305800 262144\n"),
            (BASE, "content Patch 0100dcd01f306800 0\n"),
            (BASE, ""),
            (BASE, UPDATE + "content Patch 0100dcd01f306800 131072\n"),
            ("content Patch 0100dcd01f306800 262144\n", UPDATE),
        ):
            with self.subTest(base=base, update=update):
                with self.assertRaises(ValueError):
                    validate_metadata(base, update)

    def test_parser_ignores_untrusted_lines(self):
        self.assertEqual(meta_rows("debug text\n" + UPDATE), [("Patch", "0100DCD01F306800", 262144)])
        self.assertEqual(meta_rows("content Patch 0100dcd01f306800 262144 injected\n"), [])


if __name__ == "__main__":
    unittest.main()
