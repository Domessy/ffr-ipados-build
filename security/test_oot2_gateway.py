#!/usr/bin/env python3
"""Fixed SSH gateway unit tests using synthetic sparse NUP only."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from security import oot2_gateway as gw
from security import ffr_ssh_gate as parent
from security.test_oot2_nup_info import fake_nup, SIZE


class Oot2GatewayTests(unittest.TestCase):
    @staticmethod
    def fixture(home):
        docs = home / "Documents"
        docs.mkdir()
        folder = docs / "The Legend of Zelda Ocarina of TIme"
        folder.mkdir()
        nup = folder / "MyDump.nup"
        fake_nup(nup)
        project = home / "portage-ipados/oot-switch2"
        project.mkdir(parents=True)
        (project / "source").symlink_to(folder, target_is_directory=True)
        return nup, project

    def test_probes_manifest_transfer_and_no_keys(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            nup, project = self.fixture(home)
            with patch.object(gw, "HOME", home), patch.object(gw, "SOURCE_LINK", project/"source"):
                self.assertEqual(gw.nup_file(), nup)
                with patch("builtins.print") as emit:
                    self.assertEqual(gw.dispatch("oot2-probe-v1", parent), 0)
                    emit.assert_called_once_with("OOT2_GATEWAY_V1")
                with patch("builtins.print") as emit:
                    gw.dispatch("oot2-manifest-v1", parent)
                    emit.assert_called_once_with(
                        "0400486024DEC000", "v131072", SIZE, 1, 1, 2)
                with patch.object(parent, "send_file") as send:
                    self.assertEqual(gw.dispatch("oot2-read-nup", parent), 0)
                    send.assert_called_once_with(nup)
                self.assertEqual(gw.dispatch("oot2-read-keys", parent), 126)
                self.assertEqual(gw.dispatch("oot2-shell", parent), 126)

    def test_one_container_only_and_bad_version(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            nup, project = self.fixture(home)
            with patch.object(gw, "HOME", home), patch.object(gw, "SOURCE_LINK", project/"source"):
                other = nup.with_name("another.nup")
                fake_nup(other)
                with self.assertRaisesRegex(ValueError, "count"):
                    gw.nup_file()
                other.unlink()
                fake_nup(nup, version=196608)
                with self.assertRaisesRegex(ValueError, "version"):
                    gw.nup_file()
                with patch("builtins.print") as emit:
                    self.assertEqual(gw.dispatch("oot2-diagnose-v1", parent), 0)
                    self.assertIn("reason=version", emit.call_args.args[0])

    def test_reject_source_outside_direct_documents_child(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            nup, project = self.fixture(home)
            outside = home / "other"
            outside.mkdir()
            link = project / "source"
            link.unlink()
            link.symlink_to(outside, target_is_directory=True)
            with patch.object(gw, "HOME", home), patch.object(gw, "SOURCE_LINK", link):
                with self.assertRaisesRegex(ValueError, "source"):
                    gw.nup_file()

    def test_private_cache_and_ipa_outputs_isolated(self):
        orig = parent.CACHE, parent.CONFLICTS, parent.OUTPUT
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with patch.object(gw, "CACHE", root/"cache"), \
                 patch.object(gw, "CONFLICTS", root/"conflicts"), \
                 patch.object(gw, "OUTPUT", root/"resultats"):
                with patch.object(parent, "receive_file") as receive:
                    gw.dispatch("oot2-write-ipa", parent)
                    receive.assert_called_once_with("ZeldaOcarinaOfTime.ipa", 50*1024**3)
                    receive.reset_mock()
                    gw.dispatch("oot2-write-log", parent)
                    receive.assert_called_once_with("oot2-build.log", 32*1024**2)
                with patch.object(parent, "read_cache") as reader:
                    gw.dispatch("oot2-read-cache", parent)
                    reader.assert_called_once()
                with patch.object(parent, "write_cache") as writer:
                    gw.dispatch("oot2-write-cache", parent)
                    writer.assert_called_once()
        self.assertEqual((parent.CACHE,parent.CONFLICTS,parent.OUTPUT), orig)


if __name__ == "__main__":
    unittest.main()
