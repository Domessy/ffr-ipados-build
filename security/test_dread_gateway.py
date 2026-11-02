#!/usr/bin/env python3
"""Metroid Dread nxnative gateway tests: fake sparse NSPs, fake keys, no retail assets."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from security import dread_gateway as gw
from security import ffr_ssh_gate as parent


class DREADGatewayTests(unittest.TestCase):
    def fixtures(self, folder):
        names = {
            "base": "Metroid Dread [010093801237C000][v0].nsp",
            "update": "Metroid Dread_Update_v327680.nsp",
        }
        sizes = {"base": 5 * 1024**3, "update": 500 * 1024**2}
        result = {}
        for role in names:
            p = folder / names[role]
            with p.open("wb") as file:
                file.write(b"PFS0")
                file.truncate(sizes[role])
            result[role] = p
        return result

    def test_title_roles_manifest_and_keys(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            sources = self.fixtures(folder)
            keys = folder / "dedicated.keys"
            keys.write_text("synthetic only")
            with patch.object(gw, "source_folder", return_value=folder), \
                 patch.object(gw, "KEYS", keys):
                self.assertEqual(gw.packages(), sources)
                with patch("builtins.print") as output:
                    self.assertEqual(gw.dispatch("dread-manifest-v1", parent), 0)
                    output.assert_called_once_with(
                        gw.TITLE, gw.VERSION, sources["base"].stat().st_size,
                        sources["update"].stat().st_size,
                    )
                with patch.object(parent, "send_file") as sender:
                    self.assertEqual(gw.dispatch("dread-read-base", parent), 0)
                    sender.assert_called_with(sources["base"])
                    self.assertEqual(gw.dispatch("dread-read-update", parent), 0)
                    sender.assert_called_with(sources["update"])
                    self.assertEqual(gw.dispatch("dread-read-keys", parent), 0)
                    sender.assert_called_with(keys)
                with patch("builtins.print") as output:
                    self.assertEqual(gw.dispatch("dread-probe-v1", parent), 0)
                    output.assert_called_once_with("DREAD_GATEWAY_V1")

    def test_plain_base_title_and_update_filename(self):
        from pathlib import Path
        with self.assertRaises(ValueError):
            gw.classify(Path("Unrelated [0100999999990000][v0].nsp"))
        self.assertEqual(gw.classify(Path("Metroid Dread.nsp")), "base")
        self.assertEqual(gw.classify(Path("Metroid Dread update 2.1.0.nsp")), "update")
        self.assertEqual(gw.classify(Path("Metroid Dread [010093801237C800][v999999].nsp")), "update")
        with self.assertRaises(ValueError):
            gw.classify(Path("Metroid Dread [010093801237C800][v0].nsp"))

    def test_actual_dread_v105_filenames_and_sparse_sizes(self):
        """Synthetic title and semver naming; no user NSP contents."""
        with tempfile.TemporaryDirectory() as folder_name:
            folder = Path(folder_name)
            base = folder / "Metroid Dread [010093801237C000][v0].nsp"
            update = folder / "Metroid Dread v2.1.0.nsp"
            for file, size in (
                (base, 3322222222),
                (update, 155555555),
            ):
                with file.open("wb") as stream:
                    stream.write(b"PFS0")
                    stream.truncate(size)
            self.assertEqual(gw.classify(base), "base")
            self.assertEqual(gw.classify(update), "update")
            with patch.object(gw, "source_folder", return_value=folder):
                self.assertEqual(gw.packages(), {"base": base, "update": update})
            self.assertEqual(gw.VERSION, "unverified")

    def test_retail_version_markers_and_conflicting_explicit_title(self):
        self.assertEqual(gw.classify(Path("Metroid Dread 1.0.0.nsp")), "base")
        self.assertEqual(gw.classify(Path("Metroid Dread v2.1.0.nsp")), "update")
        self.assertEqual(gw.classify(Path("Metroid Dread 2.2.0.nsp")), "update")
        with self.assertRaisesRegex(ValueError, "update marked as base"):
            gw.classify(Path("Metroid Dread [010093801237C000] v2.1.0.nsp")
            )
        with self.assertRaisesRegex(ValueError, "conflicting displayed"):
            gw.classify(Path("Metroid 2.1.0 2.1.1.nsp"))

    def test_fallback_for_two_unidentified_nsp_names(self):
        # Unknown filenames are permitted when their sizes are unambiguous;
        # nx_extract performs the definitive encrypted CNMT identity check.
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            sources = self.fixtures(folder)
            base = folder / "game dump.nsp"
            update = folder / "additional content.nsp"
            sources["base"].rename(base)
            sources["update"].rename(update)
            with patch.object(gw, "source_folder", return_value=folder):
                self.assertEqual(gw.packages(), {"base": base, "update": update})

    def test_fallback_for_one_unidentified_update(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            sources = self.fixtures(folder)
            update = folder / "Unknown package.nsp"
            sources["update"].rename(update)
            with patch.object(gw, "source_folder", return_value=folder):
                self.assertEqual(gw.packages(), {"base": sources["base"], "update": update})

    def test_reject_additional_or_unrelated_package(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            sources = self.fixtures(folder)
            with patch.object(gw, "source_folder", return_value=folder):
                (folder / "Other.nsp").write_bytes(b"PFS0")
                with self.assertRaises(ValueError):
                    gw.packages()
                (folder / "Other.nsp").unlink()
                wrong = folder / "wrong [0100123456789000][v123].nsp"
                sources["update"].rename(wrong)
                with self.assertRaises(ValueError):
                    gw.packages()

    def test_reject_ambiguous_size_heuristic(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            sources = self.fixtures(folder)
            base = folder / "unknown A.nsp"
            update = folder / "unknown B.nsp"
            sources["base"].rename(base)
            sources["update"].rename(update)
            with update.open("r+b") as stream:
                stream.truncate(4 * 1024**3)
            with patch.object(gw, "source_folder", return_value=folder):
                with self.assertRaisesRegex(ValueError, "ambiguous"):
                    gw.packages()

    def test_reject_explicit_role_conflicting_with_size(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            sources = self.fixtures(folder)
            # Explicit role says the larger file is the update, contrary to
            # the only feasible size-based assignment.
            large = folder / "Metroid update [010093801237C800].nsp"
            small = folder / "ambiguous.nsp"
            sources["base"].rename(large)
            sources["update"].rename(small)
            with patch.object(gw, "source_folder", return_value=folder):
                with self.assertRaisesRegex(ValueError, "contradicts"):
                    gw.packages()

    def test_reason_coded_diagnostic_does_not_print_filenames(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            keys = folder / "keys"
            keys.write_text("synthetic")
            with patch.object(gw, "source_folder", return_value=folder), \
                 patch.object(gw, "KEYS", keys), \
                 patch("builtins.print") as output:
                self.assertEqual(gw.dispatch("dread-diagnose-v2", parent), 0)
                output.assert_called_once_with(
                    "DREAD_DIAG_V2 source=ok packages=fail keys=ok reason=count"
                )

    def test_reject_symlink_package_and_private_key(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            sources = self.fixtures(folder)
            temp_file = folder / "saved.nsp"
            sources["update"].rename(temp_file)
            sources["update"].symlink_to(temp_file)
            with patch.object(gw, "source_folder", return_value=folder):
                with self.assertRaises(ValueError):
                    gw.packages()
            key = folder / "keys"
            key.write_text("fake test key")
            link = folder / "symlink.keys"
            link.symlink_to(key)
            with patch.object(gw, "KEYS", link):
                with self.assertRaises(ValueError):
                    gw.private_keys()

    def test_source_must_be_selected_immediate_documents_folder(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            docs = home / "Documents"
            docs.mkdir()
            game = docs / "Metroid"
            game.mkdir()
            project = home / "project"
            project.mkdir()
            selected = project / "source"
            selected.symlink_to(game, target_is_directory=True)
            with patch.object(gw.Path, "home", return_value=home), \
                 patch.object(gw, "SOURCE_LINK", selected):
                self.assertEqual(gw.source_folder(), game.resolve())
                selected.unlink()
                selected.symlink_to(home, target_is_directory=True)
                with self.assertRaises(ValueError):
                    gw.source_folder()

    def test_diagnostic_fixed_codes_never_reveals_paths(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            self.fixtures(folder)
            keys = folder / "keys"
            keys.write_text("synthetic")
            with patch.object(gw, "source_folder", return_value=folder), \
                 patch.object(gw, "KEYS", keys), \
                 patch("builtins.print") as output:
                self.assertEqual(gw.dispatch("dread-diagnose-v1", parent), 0)
                output.assert_called_once_with(
                    "DREAD_DIAG_V1 source=ok packages=ok keys=ok"
                )
            with patch.object(gw, "source_folder", side_effect=ValueError("hidden path")), \
                 patch.object(gw, "KEYS", folder / "missing.keys"), \
                 patch("builtins.print") as output:
                self.assertEqual(gw.dispatch("dread-diagnose-v1", parent), 0)
                output.assert_called_once_with(
                    "DREAD_DIAG_V1 source=fail packages=fail keys=fail"
                )

    def test_command_allowlist_and_separate_cache_scope(self):
        self.assertEqual(gw.dispatch("dread-shell", parent), 126)
        original = parent.CACHE, parent.CONFLICTS, parent.OUTPUT
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with patch.object(gw, "CACHE", root / "cache"), \
                 patch.object(gw, "CONFLICTS", root / "conflicts"), \
                 patch.object(gw, "OUTPUT", root / "resultats"):
                with patch.object(parent, "read_cache") as reader:
                    self.assertEqual(gw.dispatch("dread-read-cache", parent), 0)
                    reader.assert_called_once()
                    self.assertEqual((parent.CACHE, parent.CONFLICTS, parent.OUTPUT), original)
                with patch.object(parent, "receive_file") as receiver:
                    self.assertEqual(gw.dispatch("dread-write-ipa", parent), 0)
                    receiver.assert_called_once_with("MetroidDread-nxnative.ipa", 16 * 1024**3)
                    receiver.reset_mock()
                    self.assertEqual(gw.dispatch("dread-write-survey", parent), 0)
                    receiver.assert_called_once_with("dread-survey.md", 4 * 1024**2)
                    receiver.reset_mock()
                    self.assertEqual(gw.dispatch("dread-write-profile", parent), 0)
                    receiver.assert_called_once_with("dread-profile.tsv", 2 * 1024**2)
                    receiver.reset_mock()
                    self.assertEqual(gw.dispatch("dread-write-inspection", parent), 0)
                    receiver.assert_called_once_with("dread-inspection.log", 8 * 1024**2)
        self.assertEqual((parent.CACHE, parent.CONFLICTS, parent.OUTPUT), original)


if __name__ == "__main__":
    unittest.main()
