import json
from pathlib import Path
import plistlib
import tempfile
import unittest
import zipfile
from security.oot2_v9_recover import recover, CHAIN
from security.oot2_ipad_aot import TABLES

class RecoverTests(unittest.TestCase):
    def fixture(self,root,chain=CHAIN):
        source=root/'partial.ipa';pre='Payload/Game.app/'
        with zipfile.ZipFile(source,'w',compression=zipfile.ZIP_DEFLATED) as z:
            with z.open(pre+f'msl/b-{chain}.img','w',force_zip64=True) as f:f.write(b'library fixture'*100)
            z.writestr(pre+'Game',bytes.fromhex('cffaedfe0c000001')+b'host')
            z.writestr(pre+'Info.plist',plistlib.dumps({'CFBundleIdentifier':'org.nxnative.0400486024dec000','CFBundleExecutable':'Game'}))
            for table in TABLES:z.writestr(pre+'dm/'+table,b'profile fixture')
            last=zipfile.ZipInfo(pre+'pso/unfinished.mtl4a');last.compress_type=zipfile.ZIP_STORED;z.writestr(last,b'archive fixture'*100)
        with zipfile.ZipFile(source) as z:
            originals={n:z.read(n) for n in z.namelist() if 'unfinished' not in n}
            item=z.getinfo(pre+'pso/unfinished.mtl4a');end=item.header_offset+30+len(item.filename.encode())+5
        raw=source.read_bytes()[:end];source.write_bytes(raw)
        return source,originals
    def test_all_complete_entries_are_exact_and_truncated_archive_is_excluded(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source,originals=self.fixture(root);before=source.read_bytes();out=root/'checkpoint.ipa'
            report=recover(source,out)
            self.assertFalse(report['fullwarm_validated']);self.assertEqual(source.read_bytes(),before)
            with zipfile.ZipFile(out) as z:
                self.assertIsNone(z.testzip());self.assertEqual(set(z.namelist()),set(originals))
                for name,data in originals.items():self.assertEqual(z.read(name),data)
                self.assertTrue((z.getinfo('Payload/Game.app/Game').external_attr>>16)&0o111)
    def test_wrong_chain_is_not_published(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source,_=self.fixture(root,'d24f05cf9d78');out=root/'checkpoint.ipa'
            with self.assertRaises((ValueError,KeyError)):recover(source,out)
            self.assertFalse(out.exists())
    def test_crc_corruption_is_not_published(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source,_=self.fixture(root);data=bytearray(source.read_bytes())
            # The CRC in the first complete local header is authoritative.
            data[14]^=1;source.write_bytes(data);out=root/'checkpoint.ipa'
            with self.assertRaisesRegex(ValueError,'CRC'):recover(source,out)
            self.assertFalse(out.exists())
